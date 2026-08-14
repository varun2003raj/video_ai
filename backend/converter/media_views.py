import os
import re

from django.conf import settings
from django.http import FileResponse, Http404, HttpResponse


def serve_video(request, path):
    file_path = os.path.join(settings.MEDIA_ROOT, path)

    if not os.path.isfile(file_path):
        raise Http404("Video not found")

    file_size = os.path.getsize(file_path)
    range_header = request.headers.get("Range")

    if not range_header:
        response = FileResponse(
            open(file_path, "rb"),
            content_type="video/mp4",
        )
        response["Content-Length"] = str(file_size)
        response["Accept-Ranges"] = "bytes"
        return response

    match = re.match(r"bytes=(\d+)-(\d*)", range_header)

    if not match:
        return HttpResponse(status=416)

    start = int(match.group(1))
    end = int(match.group(2)) if match.group(2) else file_size - 1

    if start >= file_size or start > end:
        return HttpResponse(status=416)

    end = min(end, file_size - 1)
    length = end - start + 1

    file = open(file_path, "rb")
    file.seek(start)

    response = FileResponse(
        file,
        status=206,
        content_type="video/mp4",
    )

    response["Content-Length"] = str(length)
    response["Content-Range"] = f"bytes {start}-{end}/{file_size}"
    response["Accept-Ranges"] = "bytes"

    return response