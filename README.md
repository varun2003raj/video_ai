# AI Document ? Video

Full-stack prototype that turns PDF/DOCX/TXT files into narrated MP4 slides using a Django API and a Vite + React frontend.

## Prerequisites
- Python 3.14+
- Node 18+ (tested with 22.22.0)
- FFmpeg (moviepy will download `imageio-ffmpeg` if not found, but native ffmpeg is faster)

## Backend (Django)
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate  # PowerShell
pip install -r ..\requirements.txt
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
```
Endpoints:
- `GET /api/health/` sanity check
- `POST /api/convert/` (multipart) fields: `file` (pdf/docx/txt, <=20 MB), optional `title`
  - Response: `{ "video_url": ".../media/jobs/<job>/video.mp4", "job_id": "..." }`
Media saves under `backend/media/jobs/<job_id>/`.

## Frontend (Vite + React)
```bash
cd frontend
npm install
npm run dev -- --host
```
- Set `VITE_API_BASE_URL` in a `.env` file (default: `http://localhost:8000/api`).
- Upload a document, optionally add a title, generate, preview, and download the MP4.

## Notes
- Text-to-speech uses `pyttsx3` (offline via Windows SAPI); adjust voice/rate in `backend/converter/views.py`.
- Slide rendering uses Pillow + MoviePy; tune sizes/colors in `render_slide_image` and `VIDEO_SIZE`.
- For production, move media to object storage and run conversions in a background worker.
