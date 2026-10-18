"""A project's life: creating it from a GP file, swapping that file, listing and
reading projects, their metadata, and deleting a project or the version a
rebuild replaced."""

from __future__ import annotations

import json
import math
import shutil
import time
import uuid
from pathlib import Path
from typing import Any, cast

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from starlette.background import BackgroundTask

from rockforge import i18n
from rockforge.infrastructure.db.models import Job, JobStatus
from rockforge.interfaces.api import app as api
from rockforge.interfaces.api.schemas import JobOut, MetadataIn, ProjectInfoOut

router = APIRouter()


# A song has a few hundred bars at most; the ceiling only stops an absurd
# payload from being persisted into params.
_MAX_BAR_TIMES = 10_000


def _parse_bar_times(raw: str) -> list[float]:
    """``bar_times`` arrives as a JSON list inside a multipart form, so it
    bypasses the models — validate it here like the other form floats."""
    if not raw.strip():
        return []
    try:
        values = json.loads(raw)
    except ValueError as exc:
        raise HTTPException(422, "bar_times must be a JSON list of seconds") from exc
    if not isinstance(values, list) or not all(
        isinstance(v, int | float) and not isinstance(v, bool) for v in values
    ):
        raise HTTPException(422, "bar_times must be a JSON list of seconds")
    if len(values) > _MAX_BAR_TIMES:
        raise HTTPException(422, f"bar_times has more than {_MAX_BAR_TIMES} entries")
    floats = [float(v) for v in values]
    if not all(math.isfinite(v) and v >= 0 for v in floats):
        raise HTTPException(422, "bar_times must be finite, non-negative seconds")
    return floats


MAX_ESTIMATED_BARS_CHARS = 200_000


_MAX_TRACKS = 64


def _parse_estimated_bars(raw: str) -> dict[str, list[int]]:
    """``estimated_bars`` (/pdf/import's, handed back by the wizard) as a JSON object
    of track index → bar numbers; checked here like ``bar_times``. Stored with the
    track index as a string key, the way JSON keeps it in ``params``."""
    if not raw.strip():
        return {}
    message = "estimated_bars must map track indexes to lists of bar numbers"
    try:
        values = json.loads(raw)
    except ValueError as exc:
        raise HTTPException(422, message) from exc
    if not isinstance(values, dict) or len(values) > _MAX_TRACKS:
        raise HTTPException(422, message)
    out: dict[str, list[int]] = {}
    for key, bars in values.items():
        if not (isinstance(key, str) and key.isdigit() and int(key) < _MAX_TRACKS):
            raise HTTPException(422, message)
        if not isinstance(bars, list) or len(bars) > _MAX_BAR_TIMES or not all(
            isinstance(b, int) and not isinstance(b, bool) and 1 <= b <= _MAX_BAR_TIMES
            for b in bars
        ):
            raise HTTPException(422, message)
        if bars:
            out[str(int(key))] = sorted(set(bars))
    return out


@router.post("/jobs/gp", response_model=JobOut, status_code=202)
def create_gp_job(
    gp_token: str = Form(...),
    audio: UploadFile | None = File(None),
    # Use the recording the GP8 file carries instead of an upload — the audio
    # its sync points were made against (see gpif_parser.embedded_audio).
    use_embedded_audio: bool = Form(False),
    # The audio of the chosen YouTube video, already fetched by /youtube/audio.
    audio_token: str = Form(""),
    # Where each bar starts in the recording (JSON list of seconds), e.g. the
    # Songsterr timestamps /songsterr returned for the video the user picked.
    bar_times: str = Form(""),
    bar_times_source: str = Form(""),
    lead_track: str = Form(""),
    rhythm_track: str = Form(""),
    combo_track: str = Form(""),
    alt_lead_track: str = Form(""),
    alt_rhythm_track: str = Form(""),
    bass_track: str = Form(""),
    # A second GP track folded into a chart: JSON {"Lead": 2, …}.
    merge_tracks: str = Form(""),
    offset_s: float = Form(0.0),
    lead_in_s: float = Form(0.0),
    tempo_scale: float = Form(1.0),
    tone_base: str = Form(""),
    tone_names: str = Form(""),  # comma-separated, max 4
    import_mutes: bool = Form(True),
    lrc: UploadFile | None = File(None),
    # Synced lyrics the wizard found on LRCLIB (/lyrics-lookup) and the user
    # kept — the same LRC text an uploaded file carries; an upload still wins.
    lyrics_lrc: str = Form("", max_length=api.MAX_LYRICS_LRC_CHARS),
    title: str = Form(""),
    artist: str = Form(""),
    album: str = Form(""),
    year: str = Form(""),
    # A cover the user chose from /album-lookup, downloaded before the job is
    # queued so the very first build carries it.
    cover_url: str = Form(""),
    # Or an image from the user's own computer (JPEG/PNG, read by its bytes),
    # which wins over cover_url.
    cover: UploadFile | None = File(None),
    # /pdf/import's estimated_bars (JSON), kept for the viewer's review links.
    estimated_bars: str = Form("", max_length=MAX_ESTIMATED_BARS_CHARS),
) -> JobOut:
    """Create a CDLC job from a previously inspected GP file + the recording."""
    gp_path = api.settings.work_dir / "gp" / Path(gp_token).name
    if not gp_path.exists():
        raise HTTPException(404, "gp_token not found — upload the GP file via /gp/inspect first")

    from rockforge.domain.errors import IngestionError

    upload_dir = api.settings.work_dir / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    if use_embedded_audio:
        from rockforge.infrastructure.gpimport.gpif_parser import extract_embedded_audio

        try:
            audio_dest = extract_embedded_audio(gp_path, upload_dir / str(uuid.uuid4()))
        except IngestionError as exc:
            raise HTTPException(422, str(exc)) from exc
    elif audio_token.strip():
        from rockforge.infrastructure.youtube_audio import FILE_PREFIX

        # Only a bare name this server wrote (yt-…) under uploads/ — never a path.
        name = Path(audio_token.strip()).name
        audio_dest = upload_dir / name
        if not name.startswith(FILE_PREFIX) or not audio_dest.is_file():
            raise HTTPException(404, "audio_token not found — fetch the audio via /youtube/audio")
    else:
        if audio is None or not audio.filename:
            raise HTTPException(
                422, "a recording is required (or use_embedded_audio for a GP8 file that has one)"
            )
        suffix = Path(audio.filename).suffix.lower()
        from rockforge.infrastructure.ingestion.sources import ALLOWED_SUFFIXES

        if suffix not in ALLOWED_SUFFIXES:
            raise HTTPException(415, f"unsupported audio format: {suffix or '(none)'}")
        audio_dest = upload_dir / f"{uuid.uuid4()}{suffix}"
        api._copy_upload_capped(audio, audio_dest)

    from rockforge.infrastructure.gpimport.parser import inspect_gp
    from rockforge.infrastructure.ingestion.tags import read_tags

    try:
        info = inspect_gp(gp_path)
    except IngestionError as exc:
        raise HTTPException(422, str(exc)) from exc
    tags = read_tags(audio_dest)

    final_title = title.strip() or info.title or tags.title
    final_artist = artist.strip() or info.artist or tags.artist
    final_album = album.strip() or info.album or tags.album or ""
    final_year: int | None = int(year) if year.strip().isdigit() else tags.year
    missing = [n for n, v in (("title", final_title), ("artist", final_artist)) if not v]
    if missing:
        audio_dest.unlink(missing_ok=True)
        raise HTTPException(
            422,
            f"neither the GP file, the audio tags nor the form provide: {missing}",
        )
    assert final_title is not None and final_artist is not None

    tones = [t.strip() for t in tone_names.split(",") if t.strip()]
    if len(tones) > 4:
        raise HTTPException(422, "Rocksmith supports at most 4 switchable tones")

    lrc_text: str | None = None
    if lrc is not None and lrc.filename:
        lrc_text = api._read_upload_capped(lrc).decode("utf-8", errors="replace")
    elif lyrics_lrc.strip():
        from rockforge.infrastructure.rsxml.vocals import parse_lyrics

        # Refused here, not at build time: an unreadable text would only
        # surface later as a build that silently has no lyrics.
        if not parse_lyrics(lyrics_lrc):
            raise HTTPException(422, i18n.tr(
                "a letra escolhida não tem tempos que se possam ler (LRC)",
                "the chosen lyrics have no timestamps that can be read (LRC)",
            ))
        lrc_text = lyrics_lrc

    # Multipart form floats bypass the ``Finite`` models above (they arrive as
    # strings and coerce), and NaN would slip past the ``<= 0`` guard below
    # because ``NaN <= 0`` is False.
    api._reject_non_finite(offset_s=offset_s, lead_in_s=lead_in_s, tempo_scale=tempo_scale)
    if tempo_scale <= 0:
        raise HTTPException(422, "tempo_scale must be > 0")
    if lead_in_s < 0.0:
        raise HTTPException(422, "lead_in_s must be >= 0")

    parsed_bar_times = _parse_bar_times(bar_times)
    parsed_estimated_bars = _parse_estimated_bars(estimated_bars)
    try:
        merge_raw = json.loads(merge_tracks) if merge_tracks.strip() else None
    except ValueError as exc:
        raise HTTPException(422, "merge_tracks must be a JSON object") from exc
    parsed_merge = api._clean_merge_tracks(merge_raw)
    cover_url = cover_url.strip()
    if cover_url:
        from rockforge.infrastructure.album_lookup import cover_url_allowed

        if not cover_url_allowed(cover_url):
            raise HTTPException(422, "cover_url is not from a known cover service")
    cover_upload: tuple[bytes, str] | None = None
    if cover is not None and cover.filename:
        from rockforge.infrastructure.album_lookup import image_suffix

        cover_data = api._read_upload_capped(cover)
        cover_suffix = image_suffix(cover_data)
        if cover_suffix is None:
            raise HTTPException(415, i18n.tr(
                "a capa tem de ser uma imagem JPEG ou PNG",
                "the cover must be a JPEG or PNG image",
            ))
        cover_upload = (cover_data, cover_suffix)

    params: dict[str, object] = {
        "gp_path": str(gp_path),
        "bar_times": parsed_bar_times,
        "bar_times_source": bar_times_source.strip()[:200] if parsed_bar_times else "",
        "offset_s": offset_s,
        "lead_in_s": lead_in_s,
        "tempo_scale": tempo_scale,
        "tone_base": tone_base.strip() or None,
        "tone_names": tones,
        "lrc_text": lrc_text,
        "import_mute_techniques": import_mutes,
        "recording_from_gp": use_embedded_audio,
    }
    if parsed_estimated_bars:
        params["estimated_bars"] = parsed_estimated_bars
    if lead_track.strip().isdigit():
        params["lead_track"] = int(lead_track)
    if rhythm_track.strip().isdigit():
        params["rhythm_track"] = int(rhythm_track)
    if combo_track.strip().isdigit():
        params["combo_track"] = int(combo_track)
    if alt_lead_track.strip().isdigit():
        params["alt_lead_track"] = int(alt_lead_track)
    if alt_rhythm_track.strip().isdigit():
        params["alt_rhythm_track"] = int(alt_rhythm_track)
    if bass_track.strip().isdigit():
        params["bass_track"] = int(bass_track)
    if parsed_merge:
        params["merge_tracks"] = parsed_merge

    with api._session_factory() as session:
        job = Job(
            source=str(audio_dest),
            source_type="gp",
            title=final_title,
            artist=final_artist,
            album=final_album,
            year=final_year,
            params=params,
        )
        session.add(job)
        session.commit()
        if cover_upload is not None:
            dest = api._replace_cover(job, cover_upload[1])
            dest.write_bytes(cover_upload[0])
            api._record_cover(job, dest)
            session.commit()
        elif cover_url:
            # Best effort: a cover that will not download must not cost the
            # user the project. The response's empty cover_art says so, and the
            # UI tells them to pick another on the Capa page.
            from rockforge.infrastructure.album_lookup import AlbumLookupError, fetch_cover

            try:
                data, suffix = fetch_cover(cover_url)
            except AlbumLookupError:
                pass
            else:
                dest = api._replace_cover(job, suffix)
                dest.write_bytes(data)
                api._record_cover(job, dest)
                session.commit()
        api._enqueue(job)
        return api._to_out(job)


@router.post("/jobs/{job_id}/reload-gp", response_model=JobOut, status_code=202)
def reload_gp(
    job_id: str,
    gp: UploadFile = File(...),
    use_embedded_audio: bool = Form(True),
) -> JobOut:
    """Replace the Guitar Pro file of an existing GP job and rebuild, keeping
    every override the job already carries (tuning, sync anchors, tempo, tones,
    lyrics, cover). For when you tweak a note in Guitar Pro and re-export — no
    need to recreate the job and redo all the alignment work.

    Like /rebuild it forks a NEW job (fresh work dir) so the previous build is
    preserved. The recording is reused unchanged — unless the new file carries
    its own audio and ``use_embedded_audio`` (the default) says to use it, as
    the wizard does: that copy is the one the file's sync points describe. A
    file with audio also stands in for a recording that no longer exists."""
    suffix = Path(gp.filename or "").suffix.lower()
    if suffix in api.GP_REJECTED_SUFFIXES:
        raise HTTPException(
            415,
            "GP6 (.gpx) is not supported (proprietary binary container). "
            "Export as GP5 or GP7 (.gp) from Guitar Pro or TuxGuitar and upload again.",
        )
    if suffix not in api.GP_SUFFIXES:
        raise HTTPException(415, f"unsupported Guitar Pro format: {suffix or '(none)'}")

    from rockforge.domain.errors import IngestionError
    from rockforge.infrastructure.gpimport.parser import inspect_gp

    with api._session_factory() as session:
        original = api._job_or_404(session, job_id)
        if original.source_type != "gp":
            raise HTTPException(422, "reload-gp only applies to Guitar Pro jobs")
        params: dict[str, object] = dict(original.params or {})
        src_recording = original.source
        meta = (original.title, original.artist, original.album, original.year)

        gp_dir = api.settings.work_dir / "gp"
        gp_dir.mkdir(parents=True, exist_ok=True)
        gp_dest = gp_dir / f"{uuid.uuid4()}{suffix}"
        api._copy_upload_capped(gp, gp_dest)

        try:
            info = inspect_gp(gp_dest)
        except IngestionError as exc:
            gp_dest.unlink(missing_ok=True)
            raise HTTPException(422, str(exc)) from exc

        # The stored track selection must still be valid: a plain note edit keeps
        # the track layout, but a restructured file may not — fail loudly rather
        # than silently building the wrong track.
        valid = {t.index for t in info.tracks}
        merged = cast("dict[str, int]", params.get("merge_tracks") or {})
        for key, idx in [*((k, params.get(k)) for k in (
                "lead_track", "rhythm_track", "combo_track",
                "alt_lead_track", "alt_rhythm_track", "bass_track")),
                *((f"merge_tracks[{k}]", v) for k, v in merged.items())]:
            if isinstance(idx, int) and idx not in valid:
                gp_dest.unlink(missing_ok=True)
                raise HTTPException(
                    422,
                    f"the new GP file has no track at the previously selected {key} "
                    f"(index {idx}) — the track layout changed. Create a new job via "
                    "'Inspecionar pistas' instead.",
                )

        from rockforge.infrastructure.gpimport.gpif_parser import (
            embedded_audio,
            extract_embedded_audio,
            sync_start_s,
        )

        recording_gone = not Path(src_recording).exists()
        if embedded_audio(gp_dest) is not None and (use_embedded_audio or recording_gone):
            upload_dir = api.settings.work_dir / "uploads"
            try:
                src_recording = str(extract_embedded_audio(gp_dest, upload_dir / str(uuid.uuid4())))
            except IngestionError as exc:
                gp_dest.unlink(missing_ok=True)
                raise HTTPException(422, str(exc)) from exc
            if not params.get("recording_from_gp"):
                # Another recording's start does not fit this one; where bar 1
                # sits in the file's own audio is what the wizard would offer.
                start = sync_start_s(gp_dest)
                if start is not None:
                    params["offset_s"] = round(start, 3)
            params["recording_from_gp"] = True
            # What was measured on the old recording does not describe this one: its
            # separated guitar would put the attacks and the stem sources elsewhere.
            for key in ("stems", "stems_status", "stems_log", "detected_tones",
                        "tone_detection_status", "tone_detection_log"):
                params.pop(key, None)
        elif recording_gone:
            gp_dest.unlink(missing_ok=True)
            raise HTTPException(409, "original recording no longer exists on the work volume")

        params["gp_path"] = str(gp_dest)
        # The converter's estimated bars described the old file, not this one.
        params.pop("estimated_bars", None)
        params["rebuilt_from"] = original.id
        title, artist, album, year = meta
        job = Job(
            source=src_recording,
            source_type="gp",
            title=title,
            artist=artist,
            album=album,
            year=year,
            params=params,
        )
        session.add(job)
        session.commit()

        # Carry the album art across to the forked job's work dir (same as
        # /rebuild) so a reload never loses the cover.
        cover_art_name = params.get("cover_art")
        if cover_art_name:
            src = api.settings.work_dir / job_id / cast(str, cover_art_name)
            if src.exists():
                dest_dir = api.settings.work_dir / job.id
                dest_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest_dir / cast(str, cover_art_name))

        api._enqueue(job)
        return api._to_out(job)


@router.get("/jobs", response_model=list[JobOut])
def list_jobs(limit: int = 50) -> list[JobOut]:
    from sqlalchemy import select

    with api._session_factory() as session:
        jobs = session.scalars(
            select(Job).order_by(Job.created_at.desc()).limit(min(limit, 200))
        ).all()
        return [api._to_out(j) for j in jobs]


@router.delete("/jobs/{job_id}", status_code=204)
def delete_job(job_id: str, force: bool = False) -> Response:
    """Delete a job and its work artifacts. Running jobs must finish first,
    unless ``force=true`` — the escape hatch for a job stuck in RUNNING because
    its worker died or hung (otherwise it could never be deleted).

    The uploaded source file is removed only when no other job (e.g. a rebuild)
    still references it."""
    with api._session_factory() as session:
        job = api._job_or_404(session, job_id)
        if job.status is JobStatus.RUNNING and not force:
            raise HTTPException(409, "job is running — wait for it to finish before deleting")
        _delete_job_files_and_row(session, job)
        session.commit()
    return Response(status_code=204)


def _delete_job_files_and_row(session: Any, job: Job) -> None:
    """Remove a job's work dir, its recording and GP file when no other job
    uses them, and its row (the caller commits)."""
    from sqlalchemy import func, select

    shutil.rmtree(api.settings.work_dir / job.id, ignore_errors=True)

    others = session.scalar(
        select(func.count()).select_from(Job).where(Job.source == job.source, Job.id != job.id)
    )
    if not others and job.source_type in {"upload", "gp"}:
        Path(job.source).unlink(missing_ok=True)

    # The uploaded Guitar Pro file too — it lives outside the job's work dir
    # (work_dir/gp/<uuid>.gp*) and was previously left behind forever, so a
    # deleted job still cost its GP file on disk. Reference-counted like the
    # recording above, because a rebuild/reload-gp fork shares the path.
    gp_path = (job.params or {}).get("gp_path")
    if isinstance(gp_path, str) and gp_path and not api._gp_path_in_use(session, gp_path, job.id):
        Path(gp_path).unlink(missing_ok=True)

    session.delete(job)


# Work-dir subfolders a later version keeps using: params["stems"] is inherited
# by every rebuild with absolute paths into the version that ran the
# separation, and detect_tones/separate_stems reuse the guitar stem cached there.
_CARRIED_WORK_DIRS = ("demucs_stems", "stem_separation")


@router.post("/jobs/{job_id}/drop-previous", response_model=JobOut)
def drop_previous_version(job_id: str) -> JobOut:
    """Delete the version this one was rebuilt from ("Aplicar e reconstruir"
    asks whether to). Only once THIS version is built — a failed rebuild keeps
    the old one. What the new version still uses from the old one is moved
    over first (the separated stems), and any other version rebuilt from the
    old one then points at the version before it."""
    from sqlalchemy import select

    with api._session_factory() as session:
        job = api._job_or_404(session, job_id)
        if job.status is not JobStatus.COMPLETED:
            raise HTTPException(409, "the new version has to finish building first")
        params = dict(job.params or {})
        prev_id = params.get("rebuilt_from")
        prev = session.get(Job, prev_id) if isinstance(prev_id, str) and prev_id else None
        if prev is None:
            raise HTTPException(404, "this version has no previous version to delete")
        if prev.status is JobStatus.RUNNING:
            raise HTTPException(409, "the previous version is still building")

        old_dir, new_dir = api.settings.work_dir / prev.id, api.settings.work_dir / job.id
        for sub in _CARRIED_WORK_DIRS:
            if (old_dir / sub).is_dir() and not (new_dir / sub).exists():
                new_dir.mkdir(parents=True, exist_ok=True)
                shutil.move(str(old_dir / sub), str(new_dir / sub))
        stems = params.get("stems")
        if isinstance(stems, dict):
            params["stems"] = {
                name: str(new_dir / Path(path).relative_to(old_dir))
                if isinstance(path, str) and Path(path).is_relative_to(old_dir) else path
                for name, path in stems.items()
            }

        rebuilt_from = cast("dict[str, Any]", prev.params or {}).get("rebuilt_from")
        grand: str | None = None
        if isinstance(rebuilt_from, str) and session.get(Job, rebuilt_from) is not None:
            grand = rebuilt_from
        for other in session.execute(select(Job).where(Job.id != prev.id)).scalars():
            other_params = params if other.id == job.id else dict(other.params or {})
            if other_params.get("rebuilt_from") != prev.id:
                continue
            if grand:
                other_params["rebuilt_from"] = grand
            else:
                other_params.pop("rebuilt_from", None)
            if other.id != job.id:
                other.params = other_params
        job.params = {**params}
        _delete_job_files_and_row(session, prev)
        session.commit()
        return api._to_out(job)


@router.get("/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: str) -> JobOut:
    with api._session_factory() as session:
        job = api._job_or_404(session, job_id)
        return api._to_out(job)


@router.patch("/jobs/{job_id}/metadata", response_model=JobOut)
def update_metadata(job_id: str, payload: MetadataIn) -> JobOut:
    """Edit the song's identity (title/artist/album/year) after the job exists.

    Updates the job columns directly; the worker reads these when building, so the
    change lands in the bundle/PSARC on the next build/rebuild (like the cover
    art). Does not fork or re-run the job.
    """
    title = payload.title.strip()
    artist = payload.artist.strip()
    if not title or not artist:
        raise HTTPException(422, "title and artist are required")
    with api._session_factory() as session:
        job = api._job_or_404(session, job_id)
        job.title = title
        job.artist = artist
        job.album = payload.album.strip()
        job.year = payload.year
        session.commit()
        return api._to_out(job)


# ── The whole project in one file (infrastructure/project_archive.py) ──────────


def _project_files(job: Job) -> tuple[Path | None, Path | None, Path | None]:
    """The recording, the Guitar Pro file and the cover, each None when gone."""
    params = cast("dict[str, Any]", job.params or {})
    recording = Path(job.source) if job.source and Path(job.source).is_file() else None
    raw_gp = params.get("gp_path")
    score = Path(raw_gp) if isinstance(raw_gp, str) and Path(raw_gp).is_file() else None
    cover: Path | None = None
    name = params.get("cover_art")
    if isinstance(name, str) and name:
        candidate = api.settings.work_dir / job.id / Path(name).name
        cover = candidate if candidate.is_file() else None
    return recording, score, cover


@router.get("/jobs/{job_id}/project-info", response_model=ProjectInfoOut)
def project_info(job_id: str) -> ProjectInfoOut:
    """What "Exportar projeto" would carry, for the Exportar page to describe."""
    with api._session_factory() as session:
        job = api._job_or_404(session, job_id)
        recording, score, cover = _project_files(job)
        stems = api._separated_stems(job.id, dict(job.params or {}), drums=True)
    missing = [n for n, f in (("recording", recording), ("score", score)) if f is None]
    return ProjectInfoOut(
        ready=not missing,
        missing=missing,
        cover=cover is not None,
        stems=sorted(stems),
        base_bytes=sum(f.stat().st_size for f in (recording, score, cover) if f is not None),
        stems_bytes=sum(p.stat().st_size for p in stems.values()),
    )


@router.get("/jobs/{job_id}/export-project")
def export_project(job_id: str, stems: bool = False) -> FileResponse:
    """The project as one ``.rfproj`` file: the recording, the Guitar Pro file,
    the cover and every correction, and the separated instruments when
    ``stems``. What it saves is the project as last built or edited on the
    server — edits still pending in the browser are not in it."""
    from rockforge.infrastructure import project_archive

    with api._session_factory() as session:
        job = api._job_or_404(session, job_id)
        if job.source_type != "gp":
            raise HTTPException(422, "only Guitar Pro projects can be exported")
        recording, score, cover = _project_files(job)
        params = dict(job.params or {})
        separated = api._separated_stems(job.id, params, drums=True) if stems else {}
        meta = {"title": job.title, "artist": job.artist, "album": job.album,
                "year": job.year, "source_type": job.source_type}
    if recording is None or score is None:
        raise HTTPException(409, i18n.tr(
            "a gravação ou o ficheiro Guitar Pro deste projeto já não existe,"
            " por isso não se pode exportar",
            "this project's recording or Guitar Pro file no longer exists,"
            " so it cannot be exported",
        ))
    out_dir = api.settings.work_dir / "exports"
    out_dir.mkdir(parents=True, exist_ok=True)
    # A download the browser abandoned never reaches the clean-up below.
    for old in out_dir.glob(f"*{project_archive.SUFFIX}"):
        if time.time() - old.stat().st_mtime > 3600:
            old.unlink(missing_ok=True)
    dest = out_dir / f"{uuid.uuid4()}{project_archive.SUFFIX}"
    project_archive.write_project(
        dest, job=meta, params=params,
        files=project_archive.ProjectFiles(recording, score, cover, separated),
    )
    return FileResponse(
        dest,
        media_type="application/zip",
        filename=project_archive.file_name(str(meta["artist"]), str(meta["title"])),
        background=BackgroundTask(dest.unlink, missing_ok=True),
    )


def _copy_capped(src: UploadFile, dest: Path, cap: int) -> None:
    total = 0
    try:
        with dest.open("wb") as fh:
            while chunk := src.file.read(1024 * 1024):
                total += len(chunk)
                if total > cap:
                    raise HTTPException(413, f"file too large (max {cap // (1024 * 1024)} MB)")
                fh.write(chunk)
    except HTTPException:
        dest.unlink(missing_ok=True)
        raise


@router.post("/projects/import", response_model=JobOut, status_code=202)
def import_project(file: UploadFile = File(...)) -> JobOut:
    """A ``.rfproj`` file becomes a new project, built again from what it
    carries. Nothing in it is trusted as a path: the files go where this server
    puts its own, and only the portable params come along
    (``project_archive.PORTABLE_KEYS``)."""
    from rockforge.domain.errors import IngestionError
    from rockforge.infrastructure import project_archive
    from rockforge.infrastructure.album_lookup import image_suffix
    from rockforge.infrastructure.gpimport.parser import inspect_gp

    uploads = api.settings.work_dir / "uploads"
    uploads.mkdir(parents=True, exist_ok=True)
    archive = uploads / f"import-{uuid.uuid4()}{project_archive.SUFFIX}"
    _copy_capped(file, archive, project_archive.MAX_TOTAL_BYTES)
    written: list[Path] = []
    try:
        try:
            project = project_archive.read_project(archive)
        except project_archive.ProjectArchiveError as exc:
            raise HTTPException(422, str(exc)) from exc

        recording = project.extract(
            project.recording, uploads / f"{uuid.uuid4()}{Path(project.recording).suffix.lower()}"
        )
        written.append(recording)
        gp_dir = api.settings.work_dir / "gp"
        gp_dir.mkdir(parents=True, exist_ok=True)
        score = project.extract(
            project.score, gp_dir / f"{uuid.uuid4()}{Path(project.score).suffix.lower()}"
        )
        written.append(score)
        try:
            inspect_gp(score)
        except IngestionError as exc:
            raise HTTPException(422, i18n.tr(
                f"o ficheiro Guitar Pro do projeto não se consegue ler: {exc}",
                f"the project's Guitar Pro file cannot be read: {exc}",
            )) from exc

        params: dict[str, object] = {**project.params, "gp_path": str(score)}
        with api._session_factory() as session:
            job = Job(
                source=str(recording), source_type="gp",
                title=project.job["title"], artist=project.job["artist"],
                album=project.job["album"], year=project.job["year"], params=params,
            )
            session.add(job)
            session.commit()
            job_dir = api.settings.work_dir / job.id
            try:
                if project.cover is not None:
                    tmp = project.extract(project.cover, job_dir.with_name(f"{job.id}.cover"))
                    data = tmp.read_bytes()
                    tmp.unlink(missing_ok=True)
                    suffix = image_suffix(data)
                    if suffix is not None:
                        dest = api._replace_cover(job, suffix)
                        dest.write_bytes(data)
                        api._record_cover(job, dest)
                if project.stems:
                    # Where a separation of this project would have left them
                    # (the shared Demucs cache): found by every stem reader,
                    # moved along by "drop the previous version".
                    stem_dir = job_dir / "demucs_stems" / "stems" / "htdemucs_6s" / "imported"
                    stem_dir.mkdir(parents=True, exist_ok=True)
                    stored: dict[str, str] = {}
                    for name, member in project.stems.items():
                        path = project.extract(member, stem_dir / f"{name}.wav")
                        head = path.read_bytes()[:12]
                        if head[:4] != b"RIFF" or head[8:12] != b"WAVE":
                            path.unlink(missing_ok=True)
                            continue
                        if name != "drums":
                            stored[name] = str(path)
                    if stored:
                        job.params = {**dict(job.params or {}), "stems": stored,
                                      "stems_status": "ready"}
                session.commit()
            except Exception:
                session.delete(job)
                session.commit()
                shutil.rmtree(job_dir, ignore_errors=True)
                raise
            api._enqueue(job)
            return api._to_out(job)
    except BaseException:
        for path in written:
            path.unlink(missing_ok=True)
        raise
    finally:
        archive.unlink(missing_ok=True)
