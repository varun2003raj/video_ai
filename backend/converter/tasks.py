from pathlib import Path

from django.conf import settings

from .video_processing import (
    extract_text,
    chunk_text,
    render_slide_image,
    render_text_doc,
    generate_audio_for_chunks,
    build_video_from_pages,
)

from celery import shared_task


@shared_task
def process_conversion(
    job_id,
    src_path,
    ext,
    narration_enabled,
    title="",
):
    workdir = Path(settings.MEDIA_ROOT) / "jobs" / job_id
    src_path = Path(src_path)
    video_path = workdir / "video.mp4"

    try:
        # Render document
        if ext == ".pdf":
            text = extract_text(src_path)
            chunks = chunk_text(text, max_chars=250)

            image_paths = []

            for index, chunk in enumerate(chunks):
                img = render_slide_image(chunk)

                out = workdir / f"page_{index}.png"
                img.save(out)
                img.close()

                image_paths.append(out)

        else:
            image_paths, chunks = render_text_doc(
                src_path,
                workdir,
                ext,
                narration_enabled,
            )

        # Generate narration
        audio_clips = []

        if narration_enabled and chunks:
            try:
                audio_clips = generate_audio_for_chunks(
                    chunks,
                    workdir,
                )
            except Exception as exc:
                print("TTS ERROR:", exc)
                audio_clips = []

        # Build final video
        build_video_from_pages(
            image_paths,
            video_path,
            audio_clips,
        )

        print(f"Job {job_id} completed successfully.")

        return {
            "job_id": job_id,
            "status": "completed",
            "video_path": str(video_path),
        }

    except Exception as exc:
        print(f"Job {job_id} failed: {exc}")

        return {
            "job_id": job_id,
            "status": "failed",
            "error": str(exc),
        }