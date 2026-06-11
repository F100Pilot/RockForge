"""REST API: submit audio/YouTube jobs, poll status, download results."""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, HttpUrl

from rockforge.config import settings
from rockforge.infrastructure.db.models import Job, JobStatus, make_session_factory

app = FastAPI(
    title="RockForge",
    description=(
        "Audio -> Rocksmith 2014 CDLC arrangement pipeline. Honest about limits: "
        "lead/rhythm split is experimental; PSARC finalization requires DLC Builder + Wwise. "
        "See docs/RELATORIO-TECNICO.md."
    ),
    version="0.1.0",
)

_session_factory = make_session_factory(settings.database_url)


class JobOut(BaseModel):
    id: str
    status: str
    title: str
    artist: str
    warnings: list[str]
    note_counts: dict[str, int]
    psarc_available: bool
    bundle_available: bool
    error: str | None


class YouTubeJobIn(BaseModel):
    url: HttpUrl
    title: str
    artist: str
    album: str = ""


def _to_out(job: Job) -> JobOut:
    return JobOut(
        id=job.id,
        status=job.status.value,
        title=job.title,
        artist=job.artist,
        warnings=job.warnings or [],
        note_counts=job.note_counts or {},
        psarc_available=job.psarc_path is not None,
        bundle_available=job.bundle_dir is not None,
        error=job.error,
    )


def _enqueue(job: Job) -> None:
    from rockforge.interfaces.worker.celery_app import generate_cdlc

    generate_cdlc.delay(job.id)


@app.post("/jobs/upload", response_model=JobOut, status_code=202)
async def create_upload_job(
    file: UploadFile = File(...),
    title: str = Form(...),
    artist: str = Form(...),
    album: str = Form(""),
) -> JobOut:
    suffix = Path(file.filename or "upload").suffix.lower()
    if suffix not in {".mp3", ".flac", ".wav", ".ogg", ".m4a", ".aiff"}:
        raise HTTPException(415, f"unsupported audio format: {suffix or '(none)'}")
    upload_dir = settings.work_dir / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    dest = upload_dir / f"{uuid.uuid4()}{suffix}"
    with dest.open("wb") as fh:
        shutil.copyfileobj(file.file, fh)

    with _session_factory() as session:
        job = Job(source=str(dest), source_type="upload", title=title, artist=artist, album=album)
        session.add(job)
        session.commit()
        _enqueue(job)
        return _to_out(job)


@app.post("/jobs/youtube", response_model=JobOut, status_code=202)
def create_youtube_job(payload: YouTubeJobIn) -> JobOut:
    if not settings.enable_youtube:
        raise HTTPException(
            403,
            "YouTube ingestion is disabled: downloading audio violates the YouTube ToS. "
            "Operator must set ROCKFORGE_ENABLE_YOUTUBE=true to accept that responsibility.",
        )
    with _session_factory() as session:
        job = Job(
            source=str(payload.url),
            source_type="youtube",
            title=payload.title,
            artist=payload.artist,
            album=payload.album,
        )
        session.add(job)
        session.commit()
        _enqueue(job)
        return _to_out(job)


@app.get("/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: str) -> JobOut:
    with _session_factory() as session:
        job = session.get(Job, job_id)
        if job is None:
            raise HTTPException(404, "job not found")
        return _to_out(job)


@app.get("/jobs/{job_id}/bundle")
def download_bundle(job_id: str) -> FileResponse:
    with _session_factory() as session:
        job = session.get(Job, job_id)
        if job is None or job.status is not JobStatus.COMPLETED or not job.bundle_dir:
            raise HTTPException(404, "bundle not available")
        archive = shutil.make_archive(job.bundle_dir, "zip", job.bundle_dir)
        return FileResponse(archive, filename=f"{job.title}-rockforge-bundle.zip")


@app.get("/jobs/{job_id}/psarc")
def download_psarc(job_id: str) -> FileResponse:
    with _session_factory() as session:
        job = session.get(Job, job_id)
        if job is None or not job.psarc_path:
            raise HTTPException(
                404,
                "PSARC not available — Wwise-dependent packing is delegated to DLC Builder; "
                "download the bundle instead",
            )
        return FileResponse(job.psarc_path, filename=Path(job.psarc_path).name)


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def index() -> str:
    ui = Path(__file__).resolve().parents[3].parent / "web" / "index.html"
    if ui.exists():
        return ui.read_text(encoding="utf-8")
    return "<h1>RockForge</h1><p>UI not bundled; see /docs for the API.</p>"
