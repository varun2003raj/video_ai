from pydoc import text
import textwrap
import numpy as np
import re
import uuid
from pathlib import Path
import math
import pdfplumber
import pypdfium2 as pdfium
from PIL import Image, ImageDraw, ImageFont
if not hasattr(Image, "ANTIALIAS"): 
    Image.ANTIALIAS = Image.Resampling.LANCZOS  
from docx import Document
from moviepy.editor import AudioFileClip, ImageClip, CompositeVideoClip, concatenate_videoclips,VideoClip,VideoFileClip
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework.views import APIView
from django.conf import settings
from .pexels import download_video, search_image, download_image, search_video
from .topic import get_summary, get_keywords
from moviepy.editor import (
    AudioFileClip,
    ImageClip,
    VideoFileClip,
    CompositeVideoClip,
    concatenate_videoclips
)

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

def render_slide_image(
    text: str,
    highlighted_chars: int = 0,
    image_path=None,
    width=VIDEO_SIZE[0],
    margin=60,
    background=(16, 22, 37),
    font_size=32
) -> Image.Image:
    """Render text on the left and related image on the right."""

    draw_font = None
    try:
        draw_font = ImageFont.truetype("arial.ttf", font_size)
    except OSError:
        draw_font = ImageFont.load_default()

    # Reserve space for the image on the right
    image_area_width = 430
    text_area_width = width - image_area_width - (margin * 2)

    # Convert pixel width into an approximate textwrap width
    chars_per_line = max(30, int(text_area_width / (font_size * 0.55)))

    wrapper = textwrap.TextWrapper(
        width=chars_per_line,
        break_long_words=False,
        break_on_hyphens=False
    )

    lines = []

    for paragraph in text.splitlines() or [""]:
        wrapped = wrapper.wrap(paragraph) or [""]
        lines.extend(wrapped)
        lines.append("")

    if lines:
        lines.pop()

    line_height = draw_font.size + 8

    height = max(
        VIDEO_SIZE[1],
        (len(lines) + 2) * line_height + margin * 2
    )

    img = Image.new("RGB", (width, height), background)
    draw = ImageDraw.Draw(img)

    # Draw the related image on the right
    if image_path:
        visual = Image.open(image_path).convert("RGB")

        visual.thumbnail(
            (
                image_area_width - 40,
                VIDEO_SIZE[1] - (margin * 2)
            )
        )

        image_x = width - image_area_width + 20
        image_y = margin

        img.paste(visual, (image_x, image_y))

    # Draw text only inside the left area
    y = margin

    char_count = 0

    for ln in lines:
        x = margin

        for char in ln:

            if char_count < highlighted_chars:
                fill = (255, 215, 0)      # Yellow
            else:
                fill = (240, 243, 248)    # White

            draw.text(
                (x, y),
                char,
                font=draw_font,
                fill=fill
            )

            x += draw.textlength(
                char,
                font=draw_font
            )

            char_count += 1

        y += line_height

    return img



def render_highlighted_text(
    text: str,
    highlighted_chars: int,
    width=VIDEO_SIZE[0],
    margin=60,
    background=(16, 22, 37),
    font_size=32
) -> Image.Image:

    try:
        draw_font = ImageFont.truetype(
            "arial.ttf",
            font_size
        )
    except OSError:
        draw_font = ImageFont.load_default()

    image_area_width = 430
    text_area_width = width - image_area_width - (margin * 2)

    chars_per_line = max(
        30,
        int(text_area_width / (font_size * 0.55))
    )

    wrapper = textwrap.TextWrapper(
        width=chars_per_line,
        break_long_words=False,
        break_on_hyphens=False
    )

    lines = []

    for paragraph in text.splitlines() or [""]:
        wrapped = wrapper.wrap(paragraph) or [""]
        lines.extend(wrapped)
        lines.append("")

    if lines:
        lines.pop()

    line_height = draw_font.size + 8

    height = max(
        VIDEO_SIZE[1],
        (len(lines) + 2) * line_height + margin * 2
    )

    img = Image.new(
        "RGB",
        (width, height),
        background
    )

    draw = ImageDraw.Draw(img)

    # Track how many characters have been drawn
    char_count = 0

    y = margin

    for line in lines:

        for char in line:

            if char_count < highlighted_chars:
                fill = (255, 215, 0)   # Yellow
            else:
                fill = (240, 243, 248) # White

            draw.text(
                (margin, y),
                char,
                font=draw_font,
                fill=fill
            )

            char_width = draw.textlength(
                char,
                font=draw_font
            )

            margin += char_width
            char_count += 1

        margin = 60
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

def split_sentences(text: str):
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    return [s.strip() for s in sentences if s.strip()]

def get_sentence_timings(text: str, workdir: Path):
    sentences = split_sentences(text)
    timings = []
    current_time = 0.0

    for i, sentence in enumerate(sentences, start=1):
        audio_path = workdir / f"timing_{i}.wav"

        audio = generate_audio(
            sentence,
            audio_path
        )

        start = current_time
        end = current_time + audio.duration

        timings.append({
            "text": sentence,
            "start": start,
            "end": end,
        })

        current_time = end

    return timings

def render_pdf_pages(src_path: Path, workdir: Path) -> list[Path]:
    doc = pdfium.PdfDocument(str(src_path))

    from .sections import split_into_sections, get_section_media

    # Extract all PDF text
    full_text = ""

    for page in doc:
        text_page = page.get_textpage()
        page_text = text_page.get_text_range()

        if page_text.strip():
            full_text += page_text + "\n"

    # Split PDF text into sections
    sections = split_into_sections(full_text)

    image_paths = []

    # Create media for every section
    for i, section in enumerate(sections, start=1):

        media = get_section_media(
            section,
            workdir,
            i
        )

        # Create controlled text layer
        text_img = render_slide_image(section)

        text_path = workdir / f"section_{i}_text.png"
        text_img.save(text_path)

        image_paths.append(
            (text_path, section)
        )

        """if media["image_path"]:
            image_paths.append(
                media["image_path"]
            )"""

        if media["video_path"]:
            image_paths.append(
                media["video_path"]
            )

    return image_paths

def render_text_doc(src_path: Path, workdir: Path, ext: str, narration_enabled) -> list[Path]:
    if ext == ".txt":
        text = src_path.read_text(encoding="utf-8", errors="ignore")
    else:
        doc = Document(src_path)
        text = "\n".join(p.text for p in doc.paragraphs)

    from .sections import split_into_sections, get_section_media

    sections = split_into_sections(text)

    image_paths = []

    for i, section in enumerate(sections, start=1):
        media = get_section_media(section, workdir, i)

        text_img = render_slide_image(section)

        text_path = workdir / f"section_{i}_text.png"
        text_img.save(text_path)

        image_paths.append((text_path, section))

        """if media["image_path"]:
            image_paths.append(media["image_path"])"""

        if media["video_path"]:
            image_paths.append(media["video_path"])

    return image_paths
def build_video_from_pages(
    image_paths: list[Path],
    output_path: Path,
    audio_clip: AudioFileClip | None = None
):
    section_clips = []
    section_audios = []

    for i in range(0, len(image_paths), 2):

        text_path, section_text = image_paths[i]

        section_number = (i // 2) + 1

        # Generate narration for this section
        section_audio_path = (
            output_path.parent / f"section_{section_number}.wav"
        )

        section_audio = generate_audio(
            section_text,
            section_audio_path
        )

        duration = max(
            MIN_PAGE_DURATION,
            section_audio.duration
        )

        section_audios.append(section_audio)

        # Get this section's video
        related_video_path = (
            image_paths[i + 1]
            if i + 1 < len(image_paths)
            else None
        )

        print("SECTION:", section_number)
        print("TEXT:", text_path)
        print("VIDEO:", related_video_path)
        print("AUDIO DURATION:", section_audio.duration)

        # Create text clip
        text_img = render_slide_image(
        section_text,
        highlighted_chars=0
        )

        text_clip = ImageClip(
            np.array(text_img)
        )

        total_chars = len(section_text)

        scroll_distance = max(
            0,
            text_clip.h - VIDEO_SIZE[1]
        )

        scroll_speed = (
            scroll_distance / duration
            if scroll_distance
            else 0
        )

        def text_position(
            t,
            sd=scroll_distance,
            sp=scroll_speed
        ):
            offset = min(
                sd,
                t * sp
            )
            return (
                0,
                150 - offset
            )

        sentence_timings = get_sentence_timings(
            section_text,
            output_path.parent
        )

        def make_text_frame(
            t,
            current_text=section_text,
            current_duration=duration,
            current_total_chars=total_chars
        ):
            progress = min(
                1.0,
                t / current_duration
            )

            highlighted_chars = int(
                current_total_chars * progress
            )

            frame = render_slide_image(
                current_text,
                highlighted_chars=highlighted_chars
            )

            return np.array(frame)


        moving_text = VideoClip(
            make_text_frame,
            duration=duration
        ).set_position(
            text_position
        )

        layers = [moving_text]

        # Add related video
        if related_video_path:

            related_video = VideoFileClip(
                str(related_video_path)
            )

            max_width = 450
            max_height = 350

            scale = max(
                max_width / related_video.w,
                max_height / related_video.h
            )

            related_video = related_video.resize(
                scale
            )

            related_video = related_video.crop(
                x_center=related_video.w / 2,
                y_center=related_video.h / 2,
                width=max_width,
                height=max_height
            )

            # Repeat video if shorter than narration
            if related_video.duration < duration:

                loops = math.ceil(
                    duration / related_video.duration
                )

                related_video = concatenate_videoclips(
                    [related_video] * loops
                )

            related_video = related_video.subclip(
                0,
                duration
            )

            related_video = (
                related_video
                .set_position(
                    (
                        VIDEO_SIZE[0] - related_video.w - 60,
                        (VIDEO_SIZE[1] - related_video.h) // 2
                    )
                )
                .set_duration(duration)
            )

            layers.append(related_video)

        # Combine text + video
        composed = CompositeVideoClip(
            layers,
            size=VIDEO_SIZE,
            bg_color=(10, 12, 20)
        ).set_duration(duration)

        # Add this section's narration
        composed = composed.set_audio(
            section_audio.set_duration(duration)
        )

        section_clips.append(composed)

    # Combine all sections
    video_body = concatenate_videoclips(
        section_clips,
        method="compose"
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    temp_audio = output_path.parent / "temp_audio.m4a"

    video_body.write_videofile(
        str(output_path),
        fps=24,
        codec="libx264",
        audio=True,
        audio_codec="aac",
        temp_audiofile=str(temp_audio),
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
            print("NEW IMAGE PATHS:", image_paths)

            video_path = workdir / "video.mp4"
            audio_clip = None

            

            build_video_from_pages(image_paths, video_path, audio_clip)
        except Exception as exc:  
            return Response({"detail": f"Conversion failed: {exc}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        video_url = request.build_absolute_uri(settings.MEDIA_URL + f"jobs/{job_id}/video.mp4")
        return Response({"video_url": video_url, "job_id": job_id}, status=status.HTTP_201_CREATED)