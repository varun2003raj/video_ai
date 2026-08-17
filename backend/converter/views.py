#import textwrap
import uuid
from pathlib import Path
#import math
#import pdfplumber
#import pypdfium2 as pdfium
#from PIL import Image, ImageDraw, ImageFont
#if not hasattr(Image, "ANTIALIAS"): 
#    Image.ANTIALIAS = Image.Resampling.LANCZOS  
#from docx import Document
#from moviepy.editor import AudioFileClip
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework.views import APIView
from django.conf import settings
from .tasks import process_conversion
from django.http import FileResponse

#import asyncio
#import edge_tts
#import subprocess

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt"}
MAX_FILE_SIZE_MB = 5
MAX_PAGES = 10
VIDEO_SIZE = (854, 480)
SCROLL_PX_PER_SEC = 140 
MIN_PAGE_DURATION = 4.0
PAGE_GAP = 0
TTS_RATE = 170
TTS_VOICE = None  

def save_upload(file_obj, dest_path: Path) -> Path:
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    with dest_path.open("wb+") as destination:
        for chunk in file_obj.chunks():
            destination.write(chunk)
    return dest_path

def extract_text(src_path: Path) -> str:
    suffix = src_path.suffix.lower()
    if suffix == ".txt":
        return src_path.read_text(encoding="utf-8", errors="ignore")
    if suffix == ".docx":
        doc = Document(src_path)
        return "\n".join(p.text for p in doc.paragraphs)
    if suffix == ".pdf":
        text_parts = []
        with pdfplumber.open(src_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                text_parts.append(page_text)
        return "\n".join(text_parts)
    raise ValueError(f"Unsupported file extension: {suffix}")













class HealthView(APIView):
    def get(self, _request):
        return Response({"status": "ok"})

class VideoStreamView(APIView):

    def get(self, request, job_id):
        video_path = (
            Path(settings.MEDIA_ROOT)
            / "jobs"
            / job_id
            / "video.mp4"
        )

        if not video_path.exists():
            return Response(
                {"detail": "Video not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        file_size = video_path.stat().st_size
        range_header = request.headers.get("Range")

        if not range_header:
            response = FileResponse(
                open(video_path, "rb"),
                content_type="video/mp4",
            )
            response["Content-Length"] = str(file_size)
            response["Accept-Ranges"] = "bytes"
            response["Content-Disposition"] = (
                'inline; filename="video.mp4"'
            )

            response["Access-Control-Allow-Origin"] = "*"
            
            return response

        try:
            range_value = range_header.strip().lower()

            if not range_value.startswith("bytes="):
                raise ValueError

            range_value = range_value.replace("bytes=", "", 1)
            start_str, end_str = range_value.split("-", 1)

            if start_str:
                start = int(start_str)
            else:
                start = 0

            if end_str:
                end = int(end_str)
            else:
                end = file_size - 1

            end = min(end, file_size - 1)

            if start > end or start >= file_size:
                return Response(
                    status=416,
                    headers={
                        "Content-Range": f"bytes */{file_size}"
                    },
                )

        except (ValueError, IndexError):
            return Response(
                {"detail": "Invalid Range header."},
                status=416,
                headers={
                    "Content-Range": f"bytes */{file_size}"
                },
            )

        length = end - start + 1

        video_file = open(video_path, "rb")
        video_file.seek(start)

        response = FileResponse(
            video_file,
            status=206,
            content_type="video/mp4",
        )

        response["Content-Length"] = str(length)
        response["Content-Range"] = (
            f"bytes {start}-{end}/{file_size}"
        )
        response["Accept-Ranges"] = "bytes"
        response["Content-Disposition"] = (
            'inline; filename="video.mp4"'
        )

        return response

class DocumentToVideoView(APIView):
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request):
        upload = request.FILES.get("file")
        title = request.data.get("title") or ""
        narration_enabled = request.data.get("narration") == "true"

        if not upload:
            return Response(
                {"detail": "Attach a document file as 'file'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if upload.size > MAX_FILE_SIZE_MB * 1024 * 1024:
            return Response(
                {
                    "detail": (
                        f"File too large. Limit is "
                        f"{MAX_FILE_SIZE_MB} MB."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        ext = Path(upload.name).suffix.lower()

        if ext not in SUPPORTED_EXTENSIONS:
            return Response(
                {
                    "detail": (
                        f"Unsupported format '{ext}'. "
                        "Use .pdf, .docx, or .txt."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Create job
        job_id = uuid.uuid4().hex

        workdir = (
            Path(settings.MEDIA_ROOT)
            / "jobs"
            / job_id
        )

        workdir.mkdir(parents=True, exist_ok=True)

        # Save uploaded document
        src_path = workdir / f"source{ext}"
        save_upload(upload, src_path)

        # Send the job to the background worker
        process_conversion.delay(
            job_id=job_id,
            src_path=str(src_path),
            ext=ext,
            narration_enabled=narration_enabled,
            title=title,
        )

        return Response(
            {
                "job_id": job_id,
                "status": "queued",
            },
            status=status.HTTP_202_ACCEPTED,
        )

class JobStatusView(APIView):

    def get(self, request, job_id):
        workdir = Path(settings.MEDIA_ROOT) / "jobs" / job_id
        video_path = workdir / "video.mp4"

        if video_path.exists():
            video_url = (
                f"http://127.0.0.1:8000/api/jobs/{job_id}/video/"
            )

            return Response({
                "job_id": job_id,
                "status": "completed",
                "video_url": video_url,
            })

        return Response({
            "job_id": job_id,
            "status": "processing",
        })