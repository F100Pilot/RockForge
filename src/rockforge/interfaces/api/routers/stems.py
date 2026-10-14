"""Stem separation: start it, its status and the separated stems' audio."""

from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Any, cast

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from rockforge.interfaces.api import app as api
from rockforge.interfaces.api.schemas import JobOut, StemsOut

router = APIRouter()


@router.post("/jobs/{job_id}/separate-stems", response_model=JobOut, status_code=202)
def separate_stems_endpoint(job_id: str) -> JobOut:
    """Kick off asynchronous per-instrument stem separation (Demucs htdemucs_6s)
    on the job's source recording. Slow — poll GET /jobs/{job_id}/stems for the
    result, then play a stem via GET /jobs/{job_id}/stem/{name}. Progress is
    tracked via params["stems_status"]; never overwrites a completed build.

    Honest limit: Demucs splits by instrument type, so the guitar stem is ALL
    guitars mixed — Lead vs Rhythm cannot be separated from the recording."""
    with api._session_factory() as session:
        job = api._job_or_404(session, job_id)
        if job.source_type not in {"gp", "upload"}:
            raise HTTPException(422, "stem separation is not supported for this job's source")
        if not Path(job.source).exists():
            raise HTTPException(409, "source recording no longer exists on the work volume")
        params = dict(job.params or {})
        params["stems_status"] = "detecting"
        job.params = params
        session.commit()
        api._enqueue_separate_stems(job)
        return api._to_out(job)


@router.get("/jobs/{job_id}/stems", response_model=StemsOut)
def get_stems(job_id: str) -> StemsOut:
    """Current stem-separation status and the names of the available stems."""
    with api._session_factory() as session:
        job = api._job_or_404(session, job_id)
        params = job.params or {}
        status = str(params.get("stems_status", "none"))
        log = cast("list[str]", params.get("stems_log") or [])
        stems = cast("dict[str, Any]", params.get("stems") or {})
        # Only advertise stems whose file still exists on the work volume.
        available = sorted(name for name, p in stems.items() if Path(str(p)).is_file())
        return StemsOut(status=status, stems=available, log=[str(line) for line in log])


@router.get("/jobs/{job_id}/stem/{name}")
def get_stem_audio(job_id: str, name: str) -> FileResponse:
    """Serve a separated instrument stem (guitar/bass/drums/vocals/other/piano)
    for the viewer's audio-source selector. The stems share the normalized
    recording's clock, so the notes still line up when a stem is soloed."""
    with api._session_factory() as session:
        job = api._job_or_404(session, job_id)
        stems = cast("dict[str, Any]", (job.params or {}).get("stems") or {})
        raw = stems.get(name)
        if raw is None:
            raise HTTPException(404, "stem not found — run POST /separate-stems first")
        audio = Path(str(raw))
        if not audio.is_file():
            raise HTTPException(404, "stem file no longer exists on the work volume")
        media_type = mimetypes.guess_type(audio.name)[0] or "application/octet-stream"
        return FileResponse(audio, media_type=media_type)
