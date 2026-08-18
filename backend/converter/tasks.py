from celery import shared_task
from pathlib import Path
from django.conf import settings


@shared_task(bind=True)
def convert_document_task(self, job_id, src_path, ext):
    from .views import (
        render_pdf_pages,
        render_text_doc,
        build_video_from_pages,
    )

    workdir = Path(settings.MEDIA_ROOT) / "jobs" / job_id
    src_path = Path(src_path)

    if ext == ".pdf":
        image_paths = render_pdf_pages(src_path, workdir)
    else:
        image_paths = render_text_doc(
            src_path,
            workdir,
            ext,
            True
        )

    video_path = workdir / "video.mp4"

    build_video_from_pages(
        image_paths,
        video_path,
        None
    )

    return {
        "job_id": job_id,
        "video_path": str(video_path),
    }