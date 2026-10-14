"""What leaves RockForge: the recording, the bundle, the PSARC and its check,
installing it in the game, and the cover."""

from __future__ import annotations

import mimetypes
import shutil
from pathlib import Path
from typing import cast

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from rockforge import i18n
from rockforge.infrastructure.db.models import Job, JobStatus
from rockforge.interfaces.api import app as api
from rockforge.interfaces.api.schemas import (
    CoverFromUrlIn,
    GameDlcOut,
    InstallOut,
    JobOut,
    PsarcCheckOut,
    PsarcProblemOut,
)

router = APIRouter()


@router.get("/jobs/{job_id}/source-audio")
def get_source_audio(job_id: str) -> FileResponse:
    """The recording, served for the in-app viewer (playback + waveform).

    Prefers the original file (`job.source`, a real path); for a file that has
    moved, or an old row whose source is not a path, falls back to the
    ingested/normalized audio in the job's work dir (normalization doesn't
    change timing, so the notes still line up).
    """
    with api._session_factory() as session:
        job = api._job_or_404(session, job_id)
        workdir = api.settings.work_dir / job.id
        candidates: list[Path] = []
        src = Path(job.source)
        if src.is_file():
            candidates.append(src)
        candidates.append(workdir / "normalized.wav")
        candidates.extend(sorted(workdir.glob("input.*")))
        audio = next((c for c in candidates if c.is_file()), None)
        if audio is None:
            raise HTTPException(404, "no playable audio found for this job")
        media_type = mimetypes.guess_type(audio.name)[0] or "application/octet-stream"
        return FileResponse(audio, media_type=media_type)


@router.get("/jobs/{job_id}/bundle")
def download_bundle(job_id: str) -> FileResponse:
    with api._session_factory() as session:
        job = session.get(Job, job_id)
        if job is None or job.status is not JobStatus.COMPLETED or not job.bundle_dir:
            raise HTTPException(404, "bundle not available")
        archive = shutil.make_archive(job.bundle_dir, "zip", job.bundle_dir)
        return FileResponse(archive, filename=f"{job.title}-rockforge-bundle.zip")


@router.get("/jobs/{job_id}/psarc")
def download_psarc(job_id: str) -> FileResponse:
    with api._session_factory() as session:
        job = session.get(Job, job_id)
        if job is None or not job.psarc_path:
            raise HTTPException(
                404,
                "PSARC not available — Wwise-dependent packing is delegated to DLC Builder; "
                "download the bundle instead",
            )
        return FileResponse(job.psarc_path, filename=Path(job.psarc_path).name)


@router.get("/jobs/{job_id}/psarc-check", response_model=PsarcCheckOut)
def check_psarc(job_id: str) -> PsarcCheckOut:
    """Read the built .psarc back and check every chart in it against the rules
    whose breaking crashed the game before (``psarc/verify.py``). Run on
    request, never stored, so it always describes the file on disk."""
    from rockforge.infrastructure.packaging.psarc.verify import describe, verify_psarc

    with api._session_factory() as session:
        job = api._job_or_404(session, job_id)
        psarc = job.psarc_path
    if not psarc or not Path(psarc).is_file():
        raise HTTPException(409, i18n.tr("este projeto não tem PSARC", "this project has no PSARC"))
    report = verify_psarc(Path(psarc))
    groups: dict[tuple[str, str], PsarcProblemOut] = {}
    for p in report.problems:
        key = (p.arrangement, p.code)
        if key in groups:
            groups[key].count += 1
            continue
        groups[key] = PsarcProblemOut(
            code=p.code, text=describe(p.code), arrangement=p.arrangement, count=1,
            level=p.level, time=None if p.time is None else round(p.time, 3), detail=p.detail,
        )
    return PsarcCheckOut(ok=report.ok, charts=report.charts, problems=list(groups.values()))


@router.get("/game-dlc", response_model=GameDlcOut)
def get_game_dlc() -> GameDlcOut:
    from rockforge.infrastructure import game_install

    dlc = game_install.dlc_folder()
    return GameDlcOut(
        dlc_dir=str(dlc) if dlc else None,
        folder=game_install.SUBFOLDER,
        target=str(dlc / game_install.SUBFOLDER) if dlc else None,
    )


@router.post("/jobs/{job_id}/install", response_model=InstallOut)
def install_in_game(job_id: str) -> InstallOut:
    """Copy this version's .psarc into the game's dlc folder (``dlc/RockForge``),
    replacing the copy an earlier version of the song installed."""
    from rockforge.infrastructure import game_install

    with api._session_factory() as session:
        job = api._job_or_404(session, job_id)
        psarc = job.psarc_path
        params = dict(job.params or {})
    if not psarc or not Path(psarc).is_file():
        raise HTTPException(409, i18n.tr("este projeto não tem PSARC", "this project has no PSARC"))
    dlc = game_install.dlc_folder()
    if dlc is None:
        raise HTTPException(404, i18n.tr(
            "não encontrei a pasta dlc do Rocksmith 2014 — indica a pasta do jogo em "
            "Definições → Geral",
            "Rocksmith 2014's dlc folder was not found — set the game folder in "
            "Settings → General",
        ))
    previous = params.get("installed_psarc")
    try:
        result = game_install.install(
            Path(psarc), dlc, Path(previous) if isinstance(previous, str) else None
        )
    except OSError as exc:
        raise HTTPException(409, i18n.tr(
            "não foi possível copiar para {dir} ({error}) — se o jogo está aberto, fecha-o "
            "e tenta outra vez",
            "could not copy into {dir} ({error}) — if the game is open, close it and try "
            "again",
        ).format(dir=dlc, error=exc)) from exc
    with api._session_factory() as session:
        job = api._job_or_404(session, job_id)
        job.params = {
            **dict(job.params or {}),
            "installed_psarc": str(result.path),
            "installed_from": job_id,
        }
        session.commit()
        out = api._to_out(job)
    return InstallOut(
        path=str(result.path),
        removed=str(result.removed) if result.removed else None,
        duplicates=[str(p) for p in result.duplicates],
        job=out,
    )


@router.post("/jobs/{job_id}/cover", response_model=JobOut, status_code=202)
def upload_cover_art(job_id: str, file: UploadFile = File(...)) -> JobOut:
    """Upload/replace the album-art image used by the next rebuild (jpg/png).

    Stored as ``<work_dir>/<job_id>/cover<ext>``; referenced via
    ``params["cover_art"]`` and passed through as ``Packager.package(...,
    cover_art=...)``. Does not trigger a rebuild — call ``/rebuild`` after.
    """
    with api._session_factory() as session:
        job = api._job_or_404(session, job_id)

        suffix = Path(file.filename or "cover").suffix.lower()
        if suffix not in api._COVER_ART_SUFFIXES:
            raise HTTPException(415, f"unsupported image format: {suffix or '(none)'}")

        dest = api._replace_cover(job, suffix)
        api._copy_upload_capped(file, dest)
        api._record_cover(job, dest)
        session.commit()
        return api._to_out(job)


@router.post("/jobs/{job_id}/cover-from-url", response_model=JobOut, status_code=202)
def cover_from_url(job_id: str, payload: CoverFromUrlIn) -> JobOut:
    """Use a cover chosen from /album-lookup as the job's album art.

    Only the cover services' own image hosts are fetched from (and redirected
    to), and only a real JPEG/PNG is stored. Like an upload it does not
    rebuild — the next build picks it up.
    """
    from rockforge.infrastructure.album_lookup import (
        AlbumLookupError,
        cover_url_allowed,
        fetch_cover,
    )

    if not cover_url_allowed(payload.url):
        raise HTTPException(422, "url is not from a known cover service")
    with api._session_factory() as session:
        job = api._job_or_404(session, job_id)
        try:
            data, suffix = fetch_cover(payload.url)
        except AlbumLookupError as exc:
            raise HTTPException(502, str(exc)) from exc
        dest = api._replace_cover(job, suffix)
        dest.write_bytes(data)
        api._record_cover(job, dest)
        session.commit()
        return api._to_out(job)


@router.get("/jobs/{job_id}/cover")
def download_cover_art(job_id: str) -> FileResponse:
    with api._session_factory() as session:
        job = session.get(Job, job_id)
        cover_art = (job.params or {}).get("cover_art") if job else None
        if job is None or not cover_art:
            raise HTTPException(404, "no cover art uploaded for this job")
        cover_path = api.settings.work_dir / job.id / cast(str, cover_art)
        if not cover_path.exists():
            raise HTTPException(404, "cover art file is missing on the work volume")
        media_type = mimetypes.guess_type(cover_path.name)[0] or "application/octet-stream"
        return FileResponse(cover_path, media_type=media_type)
