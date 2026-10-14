"""Exporting back to Guitar Pro: the tempo corrections written into a copy of the
user's file, the edited chart as a new GP5, and the download of either."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from rockforge.infrastructure.db.models import Job, JobStatus
from rockforge.interfaces.api import app as api
from rockforge.interfaces.api.schemas import (
    AppliedCorrectionOut,
    ExportArrangementGpOut,
    ExportGpIn,
    ExportGpOut,
)

router = APIRouter()


@router.post("/jobs/{job_id}/export-gp", response_model=ExportGpOut)
def export_gp(job_id: str, payload: ExportGpIn) -> ExportGpOut:
    """Write the accepted tempo corrections into a COPY of the job's Guitar Pro
    file, so the correction is permanent in Guitar Pro itself and not only in
    RockForge. The uploaded original is never modified.

    Returns a report of what was actually written — the binary formats store
    tempo as an integer, so a recommendation of 119.085 lands as 119, and the
    user is told rather than quietly handed a different tempo. Fetch the file
    from ``GET /jobs/{id}/corrected-gp``."""
    with api._session_factory() as session:
        job = api._job_or_404(session, job_id)
        if job.source_type != "gp":
            raise HTTPException(422, "Guitar Pro export only applies to Guitar Pro jobs")
        params = dict(job.params or {})
        gp_path = Path(str(params.get("gp_path") or ""))
    if not gp_path.exists():
        raise HTTPException(409, "the Guitar Pro file no longer exists on the work volume")
    if not payload.corrections:
        raise HTTPException(422, "no tempo corrections to write")

    from rockforge.domain.errors import IngestionError
    from rockforge.infrastructure.gpexport.tempo_writer import (
        TempoCorrection,
        write_tempo_corrections,
    )

    out_dir = api.settings.work_dir / job_id
    out_dir.mkdir(parents=True, exist_ok=True)
    dst = out_dir / f"corrected{gp_path.suffix.lower()}"
    try:
        applied = write_tempo_corrections(
            gp_path,
            dst,
            [TempoCorrection(measure=c.measure, bpm=c.bpm) for c in payload.corrections],
        )
    except IngestionError as exc:
        raise HTTPException(422, str(exc)) from exc

    warnings: list[str] = []
    if any(a.rounded for a in applied):
        warnings.append(
            "this Guitar Pro format stores tempo as a whole number, so the "
            "recommended values were rounded — export as .gp (GP7/8) to keep the decimals"
        )
    with api._session_factory() as session:
        stored = session.get(Job, job_id)
        if stored is not None:
            stored.params = {**dict(stored.params or {}), "corrected_gp": dst.name}
            session.commit()
    return ExportGpOut(
        filename=dst.name,
        format=gp_path.suffix.lower().lstrip("."),
        size_bytes=dst.stat().st_size,
        applied=[AppliedCorrectionOut(**vars(a) | {"rounded": a.rounded}) for a in applied],
        warnings=warnings,
    )


@router.post("/jobs/{job_id}/export-arrangement-gp", response_model=ExportArrangementGpOut)
def export_arrangement_gp(job_id: str, arrangement: str) -> ExportArrangementGpOut:
    """Generate a NEW Guitar Pro file from one built arrangement.

    The companion to ``/export-gp``, which patches tempo into a copy of the
    user's own file. This one writes what RockForge holds — so the in-app note
    edits and the corrected timeline come out as a real score — at the cost of
    carrying only this arrangement: the original's other tracks and formatting
    are not in it, which the report states every time. Fetch the file from
    ``GET /jobs/{id}/corrected-gp``.
    """
    with api._session_factory() as session:
        job = session.get(Job, job_id)
        if job is None or job.status is not JobStatus.COMPLETED or not job.bundle_dir:
            raise HTTPException(404, "arrangements not available")
        if job.source_type != "gp":
            raise HTTPException(422, "Guitar Pro export only applies to Guitar Pro jobs")
        bundle = Path(job.bundle_dir)

    from rockforge.domain.errors import IngestionError
    from rockforge.infrastructure.gpexport.arrangement_writer import write_arrangement_gp5
    from rockforge.infrastructure.rsxml.reader import read_arrangement_xml

    path = bundle / f"arrangement_{arrangement.lower().replace(' ', '_')}.xml"
    if not path.is_file():
        raise HTTPException(404, f"no built arrangement named {arrangement!r}")
    try:
        arr = read_arrangement_xml(path)
    except (OSError, ValueError) as exc:
        raise HTTPException(422, f"could not read the built arrangement: {exc}") from exc

    out_dir = api.settings.work_dir / job_id
    dst = out_dir / "corrected.gp5"
    try:
        report = write_arrangement_gp5(arr, dst, track_name=arrangement)
    except IngestionError as exc:
        raise HTTPException(422, str(exc)) from exc

    with api._session_factory() as session:
        job = session.get(Job, job_id)
        if job is not None:
            job.params = {**dict(job.params or {}), "corrected_gp": dst.name}
            session.commit()
    return ExportArrangementGpOut(
        filename=dst.name,
        arrangement=arrangement,
        measures=report.measures,
        notes_written=report.notes_written,
        notes_dropped=report.notes_dropped,
        quantized=report.quantized,
        max_shift_ms=round(report.max_shift_s * 1000, 1),
        warnings=report.warnings,
    )


@router.get("/jobs/{job_id}/corrected-gp")
def get_corrected_gp(job_id: str) -> FileResponse:
    """Download the last Guitar Pro file written by ``/export-gp`` (tempo
    patched into a copy of the user's own file) or by
    ``/export-arrangement-gp`` (a new file carrying one built arrangement).
    Both record their own filename, so the most recent export is served."""
    with api._session_factory() as session:
        job = api._job_or_404(session, job_id)
        name = str((job.params or {}).get("corrected_gp") or "")
        title = job.title or "song"
    if not name:
        raise HTTPException(404, "no corrected Guitar Pro file has been exported yet")
    path = api.settings.work_dir / job_id / name
    if not path.exists():
        raise HTTPException(404, "the corrected file is no longer on the work volume")
    # The title reaches a Content-Disposition header, so keep it to characters
    # that cannot break the header or escape a directory.
    safe = "".join(c for c in title if c.isalnum() or c in " -_").strip() or "song"
    return FileResponse(path, filename=f"{safe}_synced{path.suffix}")
