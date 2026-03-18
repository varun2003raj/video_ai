import textwrap
import uuid
from pathlib import Path
import math
import pdfplumber
import pypdfium2 as pdfium
from PIL import Image, ImageDraw, ImageFont
if not hasattr(Image, "ANTIALIAS"): 
    Image.ANTIALIAS = Image.Resampling.LANCZOS  
from docx import Document
from moviepy.editor import AudioFileClip, ImageClip, CompositeVideoClip, concatenate_videoclips
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework.views import APIView
from django.conf import settings

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt"}
MAX_FILE_SIZE_MB = 20
VIDEO_SIZE = (1280, 720)
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

def chunk_text(text: str, max_chars: int = 320) -> list[str]:
    cleaned = " ".join(text.split())
    if not cleaned:
        return []
    return textwrap.wrap(cleaned, width=max_chars, break_long_words=False, break_on_hyphens=False)

def render_slide_image(text: str, width=VIDEO_SIZE[0], margin=80, background=(16, 22, 37), font_size=32) -> Image.Image:
    """Render text into a tall image to scroll through."""
    draw_font = None
    try:
        draw_font = ImageFont.truetype("arial.ttf", font_size)
    except OSError:
        draw_font = ImageFont.load_default()

    wrapper = textwrap.TextWrapper(width=90)
    lines = []
    for paragraph in text.splitlines() or [""]:
        wrapped = wrapper.wrap(paragraph) or [""]
        lines.extend(wrapped)
        lines.append("")
    if lines:
        lines.pop() 

    line_height = draw_font.size + 8
    height = max(VIDEO_SIZE[1], (len(lines) + 2) * line_height + margin * 2)
    img = Image.new("RGB", (width, height), background)
    draw = ImageDraw.Draw(img)
    y = margin
    for ln in lines:
        draw.text((margin, y), ln, font=draw_font, fill=(240, 243, 248))
        y += line_height
    return img

def generate_audio(text: str, audio_path: Path):
    import pyttsx3

    engine = pyttsx3.init()
    if TTS_VOICE:
        try:
            engine.setProperty("voice", TTS_VOICE)
        except Exception:
            pass
    engine.setProperty("rate", TTS_RATE)
    engine.save_to_file(text, str(audio_path))
    engine.runAndWait()
    return AudioFileClip(str(audio_path))

def render_pdf_pages(src_path: Path, workdir: Path) -> list[Path]:
    doc = pdfium.PdfDocument(str(src_path))
    image_paths: list[Path] = []
    target_width = VIDEO_SIZE[0]
    for i, page in enumerate(doc):
        scale = target_width / page.get_width()
        pil_image = page.render(scale=scale).to_pil()
        out = workdir / f"page_{i}.png"
        pil_image.save(out)
        image_paths.append(out)
    return image_paths

def render_text_doc(src_path: Path, workdir: Path, ext: str, narration_enabled) -> list[Path]:
    if ext == ".txt":
        text = src_path.read_text(encoding="utf-8", errors="ignore")
    else: 
        doc = Document(src_path)
        text = "\n".join(p.text for p in doc.paragraphs)
    image_paths = []

    img = render_slide_image(text)
    out = workdir / "page_0.png"
    img.save(out)

    image_paths.append(out)

    return image_paths

def build_video_from_pages(image_paths: list[Path], output_path: Path, audio_clip: AudioFileClip | None = None):
    clips = []
    base_durations = []
    scroll_distances = []

    for img_path in image_paths:
        img_clip = ImageClip(str(img_path)).resize(width=VIDEO_SIZE[0])
        scroll_distance = max(0, img_clip.h - VIDEO_SIZE[1])
        base_duration = max(MIN_PAGE_DURATION, scroll_distance / SCROLL_PX_PER_SEC if scroll_distance else MIN_PAGE_DURATION)
        base_durations.append(base_duration)
        scroll_distances.append(scroll_distance)
        clips.append({"img": img_clip})

    total_base = sum(base_durations) or MIN_PAGE_DURATION
    target_total = audio_clip.duration if audio_clip else total_base
    scale = max(1.0, target_total / total_base) if total_base else 1.0

    composed_clips = []
    for idx, clip_info in enumerate(clips):
        img_clip = clip_info["img"]
        scroll_distance = scroll_distances[idx]
        duration = base_durations[idx] * scale
        scroll_speed = scroll_distance / duration if scroll_distance else 0

        def _pos(t, sd=scroll_distance, sp=scroll_speed):
            offset = min(sd, t * sp)
            return (0, -offset)

        moving = img_clip.set_position(_pos).set_duration(duration)
        composed = CompositeVideoClip([moving], size=VIDEO_SIZE, bg_color=(10, 12, 20)).set_duration(duration)
        composed_clips.append(composed)

    video_body = concatenate_videoclips(composed_clips, method="compose")

    if audio_clip:
        video_body = video_body.set_audio(audio_clip.set_duration(video_body.duration))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    video_body.write_videofile(
        str(output_path),
        fps=24,
        codec="libx264",
        audio=bool(audio_clip),
        audio_codec="aac" if audio_clip else None,
        verbose=False,
        logger=None,
    )

class HealthView(APIView):
    def get(self, _request):
        return Response({"status": "ok"})

class DocumentToVideoView(APIView):
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request):
        upload = request.FILES.get("file")
        title = request.data.get("title") or ""
        narration_enabled = request.data.get("narration") == "true"

        if not upload:
            return Response({"detail": "Attach a document file as 'file'."}, status=status.HTTP_400_BAD_REQUEST)

        if upload.size > MAX_FILE_SIZE_MB * 1024 * 1024:
            return Response({"detail": f"File too large. Limit is {MAX_FILE_SIZE_MB} MB."}, status=status.HTTP_400_BAD_REQUEST)

        ext = Path(upload.name).suffix.lower()
        if ext not in SUPPORTED_EXTENSIONS:
            return Response(
                {"detail": f"Unsupported format '{ext}'. Use .pdf, .docx, or .txt."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        job_id = uuid.uuid4().hex
        workdir = Path(settings.MEDIA_ROOT) / "jobs" / job_id
        src_path = workdir / f"source{ext}"
        save_upload(upload, src_path)

        try:
            if ext == ".pdf":
                image_paths = render_pdf_pages(src_path, workdir)
            else:
                image_paths = render_text_doc(src_path, workdir, ext,  narration_enabled)
            video_path = workdir / "video.mp4"
            audio_clip = None

            if narration_enabled:
                try:
                    full_text = extract_text(src_path)

                    if full_text.strip():
                        audio_path = workdir / "narration.wav"
                        audio_clip = generate_audio(full_text, audio_path)

                except Exception:
                    audio_clip = None

            build_video_from_pages(image_paths, video_path, audio_clip)
        except Exception as exc:  
            return Response({"detail": f"Conversion failed: {exc}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        video_url = request.build_absolute_uri(settings.MEDIA_URL + f"jobs/{job_id}/video.mp4")
        return Response({"video_url": video_url, "job_id": job_id}, status=status.HTTP_201_CREATED)