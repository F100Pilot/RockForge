"""REST API: submit audio/YouTube jobs, poll status, download results."""

from __future__ import annotations

import asyncio
import mimetypes
import os
import shutil
import signal
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, cast

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, Response
from pydantic import BaseModel, HttpUrl

from rockforge.config import settings
from rockforge.domain.chords import name_chord
from rockforge.infrastructure.db.models import Job, JobStatus, make_session_factory

# Standard open-string MIDI pitches (low→high, E A D G B e); a chord's pitches
# are these + the arrangement's tuning offset + fret. Mirrors the viewer's
# STD_TUNING_MIDI and domain STANDARD_E_MIDI.
_STD_TUNING_MIDI = (40, 45, 50, 55, 59, 64)

_last_heartbeat = time.monotonic()
# When the tab fires `pagehide`, the UI beacons /closing which sets a short
# deadline here. A refresh reloads and beacons /heartbeat within the grace,
# clearing it; a real close doesn't, so the watchdog exits ~CLOSE_GRACE_S later
# instead of waiting the full idle_shutdown_s. None => no pending close.
_closing_at: float | None = None
# True while the tab is backgrounded/minimised (Page Visibility). Browsers
# throttle/freeze a hidden tab's timers, so its heartbeats stop — that silence
# must NOT be read as "closed" (a real close comes through /closing). While
# hidden the idle-kill is suspended; only HEARTBEAT_MAX_S catches a dead browser.
_tab_hidden = False
CLOSE_GRACE_S = 3.0  # short enough to feel immediate, long enough to survive a refresh
# Absolute safety net: shut down only after this long with NO signal at all,
# for a browser that died without firing /closing. Generous so a merely idle or
# backgrounded (but open) tab is never killed prematurely.
HEARTBEAT_MAX_S = 1800.0  # 30 min
# A watchdog poll gap larger than this means the process was suspended (laptop
# sleep/hibernate); the frozen interval is not real idle time, so we reset the
# heartbeat clock on wake instead of counting it as "closed".
SUSPEND_JUMP_S = 5.0


def _should_shutdown(
    now: float,
    last_heartbeat: float,
    closing_at: float | None,
    tab_hidden: bool,
    idle_shutdown_s: float,
) -> bool:
    """Pure shutdown decision for the idle watchdog (unit-tested).

    Triggers: (1) a /closing beacon deadline passed (fast tab-close path);
    (2) the tab is visible but silent past ``idle_shutdown_s`` (its JS stopped);
    (3) no signal at all for HEARTBEAT_MAX_S (crashed browser). A backgrounded
    (hidden) tab is never killed by (2) — only a real close or a long crash."""
    gap = now - last_heartbeat
    closing = closing_at is not None and now >= closing_at
    idle = (not tab_hidden) and gap > idle_shutdown_s
    crashed = gap > HEARTBEAT_MAX_S
    return closing or idle or crashed


async def _idle_shutdown_watchdog() -> None:
    """Exit the process when the web UI's tab closes.

    Two triggers: (1) a /closing beacon set a deadline that has passed (fast
    path on tab close, refresh-safe); (2) no /heartbeat for the full
    idle_shutdown_s (fallback for a crashed browser / lost beacon). Exiting lets
    start.bat's cleanup stop the Celery worker and any Redis it launched.
    """
    global _last_heartbeat
    poll_s = min(0.5, settings.idle_shutdown_s / 2)  # responsive to the ~3s close grace
    last_poll = time.monotonic()
    while True:
        await asyncio.sleep(poll_s)
        now = time.monotonic()
        # A poll gap far longer than poll_s means the process was frozen (system
        # sleep). Don't count that as idle — reset the clock and let the UI
        # re-ping on wake, so waking never finds a dead server.
        if now - last_poll > SUSPEND_JUMP_S:
            _last_heartbeat = now
            last_poll = now
            continue
        last_poll = now
        if _should_shutdown(
            now, _last_heartbeat, _closing_at, _tab_hidden, settings.idle_shutdown_s
        ):
            os.kill(os.getpid(), signal.SIGTERM)
            return


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    global _last_heartbeat
    _last_heartbeat = time.monotonic()
    task: asyncio.Task[None] | None = None
    if settings.idle_shutdown_s > 0:
        task = asyncio.create_task(_idle_shutdown_watchdog())
    yield
    if task is not None:
        task.cancel()


app = FastAPI(
    title="RockForge",
    description=(
        "Audio -> Rocksmith 2014 CDLC arrangement pipeline. Honest about limits: "
        "lead/rhythm split is experimental; PSARC finalization requires DLC Builder + Wwise. "
        "See docs/RELATORIO-TECNICO.md."
    ),
    version="0.1.0",
    lifespan=_lifespan,
)

_session_factory = make_session_factory(settings.database_url)


PIPELINE_STAGES = [
    "ingest", "normalize", "separate", "transcribe",
    "beat_track", "tuning", "fret_mapping", "lyrics", "package",
]


class JobOut(BaseModel):
    id: str
    status: str
    stage: str | None
    stages: list[str] = PIPELINE_STAGES
    title: str
    artist: str
    album: str
    year: int | None
    created_at: str
    warnings: list[str]
    note_counts: dict[str, int]
    psarc_available: bool
    bundle_available: bool
    source_type: str
    offset_s: float
    lead_in_s: float = 0.0
    tempo_scale: float
    import_mutes: bool
    error: str | None
    lyrics_status: str = "none"
    tone_detection_status: str = "none"
    cover_art: bool = False


class RebuildIn(BaseModel):
    """Human-review overrides: confirmed tuning and whether to attempt the experimental split."""

    tuning_midi: list[int] | None = None  # 6 MIDI pitches, low to high
    cent_offset: float = 0.0
    offset_s: float | None = None  # GP sync: second in the recording where the song starts
    lead_in_s: float | None = None  # GP: extra intro silence prepended (pushes the song later)
    tempo_scale: float | None = None  # GP sync: stretch/compress the whole chart timeline
    split_lead_rhythm: bool = True
    # Manual drift-correction points: (chart_time_s, corrected_time_s) pairs, in the
    # chart's already-shifted timeline (as shown in the tab viewer).
    sync_anchors: list[tuple[float, float]] | None = None
    # When set (ArrangementKind value, e.g. "Lead"/"Rhythm"/"Combined"), tempo_scale
    # and sync_anchors are scoped to that arrangement alone instead of all of them.
    arrangement: str | None = None
    # When True (with arrangement set), tempo_scale and sync_anchors are applied
    # to every arrangement that has notes, not just the specified one.
    apply_to_all: bool = False
    # GP: when False, palm mute / slap / pop / tap are stripped (plain notes).
    import_mutes: bool | None = None
    # Edited per-word lyrics from the in-app lyrics editor. When set (even to an
    # empty list), replaces params["lyrics_events"] and clears lyrics_status so
    # the next build uses the edited lyrics. None leaves existing lyrics alone.
    lyrics_events: list[LyricEventOut] | None = None
    # Tone editor overrides (GP jobs). When set (even to an empty list), each
    # replaces the corresponding params entry; None leaves it untouched.
    # ``tones`` are full gear definitions (see gear_catalogue.tone_from_dict);
    # ``tone_base``/``tone_names`` reference them by key; ``tone_changes`` are the
    # timed switches placed on the partitura.
    tone_base: str | None = None
    tone_names: list[str] | None = None
    tones: list[dict[str, Any]] | None = None
    tone_changes: list[dict[str, Any]] | None = None


class ArrangementNoteOut(BaseModel):
    time: float
    string: int
    fret: int
    sustain: float
    chord: bool
    techniques: list[str]
    bend_semitones: int = 0  # bend magnitude (1=half, 2=full, 3=1½…); 0 if no bend
    chord_name: str | None = None  # derived name for the chord this note belongs to


class BarOut(BaseModel):
    measure: int  # 1-based bar number
    time: float   # bundle-time position of the bar's downbeat


class ArrangementOut(BaseModel):
    kind: str
    tuning_offsets: list[int]
    cent_offset: float
    average_bpm: float
    tempo_scale: float  # this arrangement's own tempo scale (GP sync), 1.0 if none
    note_count: int
    chord_count: int
    notes: list[ArrangementNoteOut]
    bars: list[BarOut] = []  # measure downbeats for the viewer's bar numbering
    beats: list[float] = []  # ALL ebeat times (downbeats + off-beats) — the drag snap grid


class AutoSyncOut(BaseModel):
    """Proposed GP→recording alignment (not applied; the user reviews then rebuilds)."""

    gp_bpm: float
    detected_bpm: float
    suggested_tempo_scale: float
    suggested_offset_s: float


class DetectTempoIn(BaseModel):
    from_s: float = 0.0  # recording time to start measuring the local tempo from


class DetectTempoOut(BaseModel):
    """Local tempo measured from a point — for the per-point 're-tempo from here' tool."""

    gp_bpm: float
    detected_bpm: float
    suggested_factor: float  # multiply note spacing after the point by this


class DetectTuningOut(BaseModel):
    """Proposed fine-tuning correction (not applied; the user reviews then
    rebuilds). String/drop tuning is NOT detected — see librosa_adapter."""

    suggested_cent_offset: float


class LyricEventOut(BaseModel):
    time: float
    length: float
    lyric: str


class DetectTonesOut(BaseModel):
    """Proposed lead + rhythm tone presets based on spectral analysis of the
    guitar stem. Not auto-applied; the user reviews in the tone editor."""

    # "none"|"detecting"|"separating"|"analyzing"|"ready"|"unavailable"
    status: str
    category: str = ""  # "clean"|"crunch"|"high_gain"
    lead: dict[str, Any] = {}
    rhythm: dict[str, Any] = {}
    log: list[str] = []


class StemsOut(BaseModel):
    """State of per-instrument stem separation. ``stems`` lists the available
    stem names (guitar/bass/drums/vocals/other/piano); each is served via
    GET /jobs/{id}/stem/{name} so the viewer can solo one while fine-tuning sync."""

    # "none"|"detecting"|"normalizing"|"separating"|"ready"|"unavailable"
    status: str
    stems: list[str] = []
    log: list[str] = []


class SettingsOut(BaseModel):
    """App settings editable from the UI (persisted in work_dir/settings.json).
    `banquet` carries per-path readiness so the UI can show ✓/✗."""

    stem_separator: str = "demucs"  # "demucs" | "banquet"
    banquet_repo: str = ""
    banquet_ckpt: str = ""
    banquet_queries: str = ""
    banquet: dict[str, Any] = {}  # repo_ok/ckpt_ok/queries_ok/query_names/ready


class SettingsIn(BaseModel):
    stem_separator: str | None = None
    banquet_repo: str | None = None
    banquet_ckpt: str | None = None
    banquet_queries: str | None = None


class LyricsOut(BaseModel):
    # "none"|"detecting"|"normalizing"|"separating"|"transcribing"|"ready"|"empty"|"unavailable"
    status: str
    events: list[LyricEventOut]
    log: list[str] = []


class YouTubeJobIn(BaseModel):
    url: HttpUrl
    title: str
    artist: str
    album: str = ""
    year: int | None = None
    transcribe_lyrics: bool = False


def _to_out(job: Job) -> JobOut:
    raw_offset = (job.params or {}).get("offset_s")
    offset_s = float(raw_offset) if isinstance(raw_offset, (int, float, str)) else 0.0
    raw_lead = (job.params or {}).get("lead_in_s")
    lead_in_s = float(raw_lead) if isinstance(raw_lead, (int, float, str)) else 0.0
    raw_scale = (job.params or {}).get("tempo_scale")
    tempo_scale = float(raw_scale) if isinstance(raw_scale, (int, float, str)) else 1.0
    return JobOut(
        id=job.id,
        status=job.status.value,
        stage=job.stage,
        title=job.title,
        artist=job.artist,
        album=job.album or "",
        year=job.year,
        created_at=job.created_at.isoformat() if job.created_at else "",
        warnings=job.warnings or [],
        note_counts=job.note_counts or {},
        psarc_available=job.psarc_path is not None,
        bundle_available=job.bundle_dir is not None,
        source_type=job.source_type,
        offset_s=offset_s,
        lead_in_s=lead_in_s,
        tempo_scale=tempo_scale,
        import_mutes=bool((job.params or {}).get("import_mute_techniques", True)),
        error=job.error,
        lyrics_status=str((job.params or {}).get("lyrics_status", "none")),
        tone_detection_status=str(
            (job.params or {}).get("tone_detection_status", "none")
        ),
        cover_art=bool((job.params or {}).get("cover_art")),
    )


def _enqueue(job: Job) -> None:
    if settings.worker_mode == "inprocess":
        from rockforge.interfaces.worker.inprocess import enqueue_generate

        enqueue_generate(job.id)
    else:
        from rockforge.interfaces.worker.celery_app import generate_cdlc

        generate_cdlc.delay(job.id)


def _enqueue_detect(job: Job) -> None:
    if settings.worker_mode == "inprocess":
        from rockforge.interfaces.worker.inprocess import enqueue_detect

        enqueue_detect(job.id)
    else:
        from rockforge.interfaces.worker.celery_app import detect_lyrics

        detect_lyrics.delay(job.id)


def _enqueue_detect_tones(job: Job) -> None:
    if settings.worker_mode == "inprocess":
        from rockforge.interfaces.worker.inprocess import enqueue_detect_tones

        enqueue_detect_tones(job.id)
    else:
        from rockforge.interfaces.worker.celery_app import detect_tones

        detect_tones.delay(job.id)


def _enqueue_separate_stems(job: Job) -> None:
    if settings.worker_mode == "inprocess":
        from rockforge.interfaces.worker.inprocess import enqueue_separate_stems

        enqueue_separate_stems(job.id)
    else:
        from rockforge.interfaces.worker.celery_app import separate_stems

        separate_stems.delay(job.id)


@app.post("/jobs/upload", response_model=JobOut, status_code=202)
async def create_upload_job(
    file: UploadFile = File(...),
    title: str = Form(""),
    artist: str = Form(""),
    album: str = Form(""),
    year: str = Form(""),
    offset_s: float = Form(0.0),
    transcribe_lyrics: bool = Form(False),
) -> JobOut:
    """Form fields are optional: missing values are read from the file's tags
    (ID3/Vorbis/MP4). If title or artist is in neither place, returns 422 so the
    user fills the labels in — values are never invented."""
    suffix = Path(file.filename or "upload").suffix.lower()
    if suffix not in {".mp3", ".flac", ".wav", ".ogg", ".m4a", ".aiff"}:
        raise HTTPException(415, f"unsupported audio format: {suffix or '(none)'}")
    upload_dir = settings.work_dir / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    dest = upload_dir / f"{uuid.uuid4()}{suffix}"
    with dest.open("wb") as fh:
        shutil.copyfileobj(file.file, fh)

    from rockforge.infrastructure.ingestion.tags import read_tags

    tags = read_tags(dest)
    final_title = title.strip() or tags.title
    final_artist = artist.strip() or tags.artist
    final_album = album.strip() or tags.album or ""
    final_year: int | None = int(year) if year.strip().isdigit() else tags.year

    missing = [n for n, v in (("title", final_title), ("artist", final_artist)) if not v]
    if missing:
        dest.unlink(missing_ok=True)
        raise HTTPException(
            422,
            f"the file has no {'/'.join(missing)} tag — fill in the form field(s): {missing}",
        )
    assert final_title is not None and final_artist is not None

    with _session_factory() as session:
        job = Job(
            source=str(dest),
            source_type="upload",
            title=final_title,
            artist=final_artist,
            album=final_album,
            year=final_year,
            params=(
                {
                    k: v
                    for k, v in (
                        ("offset_s", offset_s if offset_s > 0 else None),
                        ("transcribe_lyrics", transcribe_lyrics or None),
                    )
                    if v is not None
                }
                or None
            ),
        )
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
            year=payload.year,
            params={"transcribe_lyrics": True} if payload.transcribe_lyrics else None,
        )
        session.add(job)
        session.commit()
        _enqueue(job)
        return _to_out(job)


class GpTrackOut(BaseModel):
    index: int
    name: str
    is_percussion: bool
    string_count: int
    tuning_midi: list[int]


class GpInspectOut(BaseModel):
    gp_token: str
    title: str
    artist: str
    album: str
    tempo: int
    has_lyrics: bool
    tracks: list[GpTrackOut]


GP_SUFFIXES = {".gp3", ".gp4", ".gp5", ".gp"}  # .gp = GP7/GP8 (native GPIF parser)
GP_REJECTED_SUFFIXES = {".gpx"}  # GP6 only — proprietary binary container


@app.post("/gp/inspect", response_model=GpInspectOut)
async def inspect_gp_file(file: UploadFile = File(...)) -> GpInspectOut:
    """Upload a Guitar Pro file, get its tracks for selection. The file is kept
    server-side and referenced by gp_token when creating the job."""
    suffix = Path(file.filename or "").suffix.lower()
    if suffix in GP_REJECTED_SUFFIXES:
        raise HTTPException(
            415,
            "GP6 (.gpx) is not supported (proprietary binary container). "
            "Export as GP5 or GP7 (.gp) from Guitar Pro or TuxGuitar and upload again.",
        )
    if suffix not in GP_SUFFIXES:
        raise HTTPException(415, f"unsupported Guitar Pro format: {suffix or '(none)'}")
    gp_dir = settings.work_dir / "gp"
    gp_dir.mkdir(parents=True, exist_ok=True)
    dest = gp_dir / f"{uuid.uuid4()}{suffix}"
    with dest.open("wb") as fh:
        shutil.copyfileobj(file.file, fh)

    from rockforge.domain.errors import IngestionError
    from rockforge.infrastructure.gpimport.parser import inspect_gp

    try:
        info = inspect_gp(dest)
    except IngestionError as exc:
        dest.unlink(missing_ok=True)
        raise HTTPException(422, str(exc)) from exc
    return GpInspectOut(
        gp_token=dest.name,
        title=info.title,
        artist=info.artist,
        album=info.album,
        tempo=info.tempo,
        has_lyrics=info.has_lyrics,
        tracks=[
            GpTrackOut(
                index=t.index,
                name=t.name,
                is_percussion=t.is_percussion,
                string_count=t.string_count,
                tuning_midi=list(t.tuning_midi),
            )
            for t in info.tracks
        ],
    )


@app.post("/jobs/gp", response_model=JobOut, status_code=202)
async def create_gp_job(
    gp_token: str = Form(...),
    audio: UploadFile = File(...),
    lead_track: str = Form(""),
    rhythm_track: str = Form(""),
    offset_s: float = Form(0.0),
    lead_in_s: float = Form(0.0),
    tempo_scale: float = Form(1.0),
    tone_base: str = Form(""),
    tone_names: str = Form(""),  # comma-separated, max 4
    import_mutes: bool = Form(True),
    lrc: UploadFile | None = File(None),
    title: str = Form(""),
    artist: str = Form(""),
    album: str = Form(""),
    year: str = Form(""),
) -> JobOut:
    """Create a CDLC job from a previously inspected GP file + the recording."""
    gp_path = settings.work_dir / "gp" / Path(gp_token).name
    if not gp_path.exists():
        raise HTTPException(404, "gp_token not found — upload the GP file via /gp/inspect first")

    suffix = Path(audio.filename or "upload").suffix.lower()
    if suffix not in {".mp3", ".flac", ".wav", ".ogg", ".m4a", ".aiff"}:
        raise HTTPException(415, f"unsupported audio format: {suffix or '(none)'}")
    upload_dir = settings.work_dir / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    audio_dest = upload_dir / f"{uuid.uuid4()}{suffix}"
    with audio_dest.open("wb") as fh:
        shutil.copyfileobj(audio.file, fh)

    from rockforge.domain.errors import IngestionError
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
        lrc_text = (await lrc.read()).decode("utf-8", errors="replace")

    if tempo_scale <= 0:
        raise HTTPException(422, "tempo_scale must be > 0")

    params: dict[str, object] = {
        "gp_path": str(gp_path),
        "offset_s": offset_s,
        "lead_in_s": lead_in_s,
        "tempo_scale": tempo_scale,
        "tone_base": tone_base.strip() or None,
        "tone_names": tones,
        "lrc_text": lrc_text,
        "import_mute_techniques": import_mutes,
    }
    if lead_track.strip().isdigit():
        params["lead_track"] = int(lead_track)
    if rhythm_track.strip().isdigit():
        params["rhythm_track"] = int(rhythm_track)

    with _session_factory() as session:
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
        _enqueue(job)
        return _to_out(job)


@app.post("/jobs/{job_id}/reload-gp", response_model=JobOut, status_code=202)
async def reload_gp(job_id: str, gp: UploadFile = File(...)) -> JobOut:
    """Replace the Guitar Pro file of an existing GP job and rebuild, keeping
    every override the job already carries (tuning, sync anchors, tempo, tones,
    lyrics, cover). For when you tweak a note in Guitar Pro and re-export — no
    need to recreate the job and redo all the alignment work.

    Like /rebuild it forks a NEW job (fresh work dir) so the previous build is
    preserved; the recording is reused unchanged."""
    suffix = Path(gp.filename or "").suffix.lower()
    if suffix in GP_REJECTED_SUFFIXES:
        raise HTTPException(
            415,
            "GP6 (.gpx) is not supported (proprietary binary container). "
            "Export as GP5 or GP7 (.gp) from Guitar Pro or TuxGuitar and upload again.",
        )
    if suffix not in GP_SUFFIXES:
        raise HTTPException(415, f"unsupported Guitar Pro format: {suffix or '(none)'}")

    from rockforge.domain.errors import IngestionError
    from rockforge.infrastructure.gpimport.parser import inspect_gp

    with _session_factory() as session:
        original = session.get(Job, job_id)
        if original is None:
            raise HTTPException(404, "job not found")
        if original.source_type != "gp":
            raise HTTPException(422, "reload-gp only applies to Guitar Pro jobs")
        if not Path(original.source).exists():
            raise HTTPException(409, "original recording no longer exists on the work volume")
        params: dict[str, object] = dict(original.params or {})
        src_recording = original.source
        meta = (original.title, original.artist, original.album, original.year)

        gp_dir = settings.work_dir / "gp"
        gp_dir.mkdir(parents=True, exist_ok=True)
        gp_dest = gp_dir / f"{uuid.uuid4()}{suffix}"
        with gp_dest.open("wb") as fh:
            shutil.copyfileobj(gp.file, fh)

        try:
            info = inspect_gp(gp_dest)
        except IngestionError as exc:
            gp_dest.unlink(missing_ok=True)
            raise HTTPException(422, str(exc)) from exc

        # The stored track selection must still be valid: a plain note edit keeps
        # the track layout, but a restructured file may not — fail loudly rather
        # than silently building the wrong track.
        valid = {t.index for t in info.tracks}
        for key in ("lead_track", "rhythm_track"):
            idx = params.get(key)
            if isinstance(idx, int) and idx not in valid:
                gp_dest.unlink(missing_ok=True)
                raise HTTPException(
                    422,
                    f"the new GP file has no track at the previously selected {key} "
                    f"(index {idx}) — the track layout changed. Create a new job via "
                    "'Inspecionar pistas' instead.",
                )

        params["gp_path"] = str(gp_dest)
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
            src = settings.work_dir / job_id / cast(str, cover_art_name)
            if src.exists():
                dest_dir = settings.work_dir / job.id
                dest_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest_dir / cast(str, cover_art_name))

        _enqueue(job)
        return _to_out(job)


@app.get("/jobs", response_model=list[JobOut])
def list_jobs(limit: int = 50) -> list[JobOut]:
    from sqlalchemy import select

    with _session_factory() as session:
        jobs = session.scalars(
            select(Job).order_by(Job.created_at.desc()).limit(min(limit, 200))
        ).all()
        return [_to_out(j) for j in jobs]


@app.delete("/jobs/{job_id}", status_code=204)
def delete_job(job_id: str, force: bool = False) -> Response:
    """Delete a job and its work artifacts. Running jobs must finish first,
    unless ``force=true`` — the escape hatch for a job stuck in RUNNING because
    its worker died or hung (otherwise it could never be deleted).

    The uploaded source file is removed only when no other job (e.g. a rebuild)
    still references it."""
    from sqlalchemy import func, select

    with _session_factory() as session:
        job = session.get(Job, job_id)
        if job is None:
            raise HTTPException(404, "job not found")
        if job.status is JobStatus.RUNNING and not force:
            raise HTTPException(409, "job is running — wait for it to finish before deleting")

        shutil.rmtree(settings.work_dir / job.id, ignore_errors=True)

        others = session.scalar(
            select(func.count()).select_from(Job).where(Job.source == job.source, Job.id != job.id)
        )
        if not others and job.source_type in {"upload", "gp"}:
            Path(job.source).unlink(missing_ok=True)

        session.delete(job)
        session.commit()
    return Response(status_code=204)


@app.post("/jobs/{job_id}/rebuild", response_model=JobOut, status_code=202)
def rebuild_job(job_id: str, payload: RebuildIn) -> JobOut:
    """Re-run the pipeline on the same source with human-confirmed overrides."""
    if payload.tuning_midi is not None and len(payload.tuning_midi) != 6:
        raise HTTPException(422, "tuning_midi must contain exactly 6 MIDI pitches (low to high)")
    with _session_factory() as session:
        original = session.get(Job, job_id)
        if original is None:
            raise HTTPException(404, "job not found")
        if original.source_type in {"upload", "gp"} and not Path(original.source).exists():
            raise HTTPException(409, "original upload no longer exists on the work volume")
        params: dict[str, object] = dict(original.params or {})
        params["split_lead_rhythm"] = payload.split_lead_rhythm
        if payload.tuning_midi is not None:
            params["tuning_midi"] = payload.tuning_midi
            params["cent_offset"] = payload.cent_offset
        if payload.offset_s is not None:
            if payload.offset_s < 0.0:
                raise HTTPException(422, "offset_s must be >= 0")
            params["offset_s"] = payload.offset_s
        if payload.lead_in_s is not None:
            if payload.lead_in_s < 0.0:
                raise HTTPException(422, "lead_in_s must be >= 0")
            params["lead_in_s"] = payload.lead_in_s
        if payload.arrangement is not None and original.source_type != "gp":
            raise HTTPException(422, "arrangement scoping only applies to Guitar Pro jobs")

        def _arr_entry(kind: str) -> dict[str, object]:
            # Per-arrangement tempo/drift overrides live under params["arrangement_sync"].
            # Seed a new entry from the job-level defaults so corrections already
            # applied to every arrangement are inherited (not dropped) the first
            # time this arrangement is edited on its own.
            store = cast(
                "dict[str, dict[str, object]]", params.setdefault("arrangement_sync", {})
            )
            if kind not in store:
                store[kind] = {
                    "tempo_scale": params.get("tempo_scale", 1.0),
                    "sync_anchor_stages": [
                        list(s)
                        for s in cast(
                            "list[list[object]]", params.get("sync_anchor_stages", [])
                        )
                    ],
                }
            return store[kind]

        def _sync_targets() -> list[dict[str, object]]:
            """Return the target dicts that tempo_scale/sync_anchors should be
            written to.  When ``apply_to_all`` is set (with ``arrangement``),
            the change propagates to every existing per-arrangement override
            *and* the job-level defaults, so both current and future
            arrangements share the same correction."""
            if payload.apply_to_all and payload.arrangement is not None:
                targets: list[dict[str, object]] = [params]
                store = cast(
                    "dict[str, dict[str, object]]",
                    params.get("arrangement_sync", {}),
                )
                for entry in store.values():
                    targets.append(entry)
                return targets
            if payload.arrangement is not None:
                return [_arr_entry(payload.arrangement)]
            return [params]

        if payload.tempo_scale is not None:
            if original.source_type != "gp":
                raise HTTPException(422, "tempo_scale only applies to Guitar Pro jobs")
            if payload.tempo_scale <= 0.0:
                raise HTTPException(422, "tempo_scale must be > 0")
            for target in _sync_targets():
                target["tempo_scale"] = payload.tempo_scale
        if payload.sync_anchors is not None:
            if original.source_type != "gp":
                raise HTTPException(422, "sync_anchors only apply to Guitar Pro jobs")
            if payload.sync_anchors:
                for target in _sync_targets():
                    stages = [
                        list(s)
                        for s in cast(
                            "list[list[object]]", target.get("sync_anchor_stages", [])
                        )
                    ]
                    stages.append([list(a) for a in payload.sync_anchors])
                    target["sync_anchor_stages"] = stages
        if payload.import_mutes is not None:
            params["import_mute_techniques"] = payload.import_mutes
        if payload.lyrics_events is not None:
            params["lyrics_events"] = [e.model_dump() for e in payload.lyrics_events]
            params.pop("lyrics_status", None)
        touches_tones = any(
            v is not None
            for v in (
                payload.tones,
                payload.tone_changes,
                payload.tone_base,
                payload.tone_names,
            )
        )
        if touches_tones and original.source_type != "gp":
            raise HTTPException(422, "tones only apply to Guitar Pro jobs")
        if payload.tone_base is not None:
            params["tone_base"] = payload.tone_base or None
        if payload.tone_names is not None:
            if len(payload.tone_names) > 4:
                raise HTTPException(422, "Rocksmith supports at most 4 switchable tones")
            params["tone_names"] = payload.tone_names
        if payload.tones is not None:
            params["tones"] = payload.tones
        if payload.tone_changes is not None:
            params["tone_changes"] = payload.tone_changes
        job = Job(
            source=original.source,
            source_type=original.source_type,
            title=original.title,
            artist=original.artist,
            album=original.album,
            year=original.year,
            params=params,
        )
        session.add(job)
        session.commit()

        # Rebuild creates a fresh work directory (job.id != original.id); the
        # cover image referenced by params["cover_art"] lives under the
        # original job's directory, so copy it across or the worker's
        # candidate.exists() check (celery_app.generate_cdlc) silently finds
        # nothing and the bundle ends up without album art.
        cover_art_name = params.get("cover_art")
        if cover_art_name:
            src = settings.work_dir / original.id / cast(str, cover_art_name)
            if src.exists():
                dest_dir = settings.work_dir / job.id
                dest_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest_dir / cast(str, cover_art_name))

        _enqueue(job)
        return _to_out(job)


@app.post("/jobs/{job_id}/auto-sync", response_model=AutoSyncOut)
def auto_sync(job_id: str) -> AutoSyncOut:
    """Detect the recording's tempo/first onset (librosa) and propose how to
    align the GP chart to it: a global tempo_scale plus an offset_s. The result
    is returned for the user to preview in the tab viewer and apply via rebuild —
    it is never silently committed (honesty principle)."""
    with _session_factory() as session:
        job = session.get(Job, job_id)
        if job is None:
            raise HTTPException(404, "job not found")
        if job.source_type != "gp":
            raise HTTPException(422, "automatic sync only applies to Guitar Pro jobs")
        gp_path = Path(str((job.params or {}).get("gp_path", "")))
        src = Path(job.source)
    if not gp_path.exists():
        raise HTTPException(409, "the Guitar Pro file no longer exists on the work volume")
    if not src.exists():
        raise HTTPException(409, "source audio no longer exists on the work volume")

    from rockforge.application.gp_pipeline import suggest_sync
    from rockforge.infrastructure.gpimport.parser import inspect_gp

    try:
        from rockforge.infrastructure.rhythm.librosa_adapter import detect_tempo_and_onset
    except ImportError as exc:  # ml extra absent
        raise HTTPException(
            503, "beat detection needs the 'ml' extra (librosa) — install rockforge[ml]"
        ) from exc

    gp_bpm = float(inspect_gp(gp_path).tempo)
    try:
        detected_bpm, first_onset = detect_tempo_and_onset(src)
    except Exception as exc:  # decode/analysis failure — surface honestly
        raise HTTPException(422, f"could not analyse the recording: {exc}") from exc
    tempo_scale, offset_s = suggest_sync(gp_bpm, detected_bpm, first_onset)
    return AutoSyncOut(
        gp_bpm=gp_bpm,
        detected_bpm=detected_bpm,
        suggested_tempo_scale=tempo_scale,
        suggested_offset_s=offset_s,
    )


@app.post("/jobs/{job_id}/detect-tempo", response_model=DetectTempoOut)
def detect_tempo(job_id: str, payload: DetectTempoIn) -> DetectTempoOut:
    """Measure the recording's tempo from ``from_s`` onward (librosa) and return a
    factor to re-tempo the chart's following notes to it. Like /auto-sync this is a
    proposal the user previews in the tab viewer before rebuilding."""
    with _session_factory() as session:
        job = session.get(Job, job_id)
        if job is None:
            raise HTTPException(404, "job not found")
        if job.source_type != "gp":
            raise HTTPException(422, "tempo detection only applies to Guitar Pro jobs")
        gp_path = Path(str((job.params or {}).get("gp_path", "")))
        src = Path(job.source)
    if not gp_path.exists():
        raise HTTPException(409, "the Guitar Pro file no longer exists on the work volume")
    if not src.exists():
        raise HTTPException(409, "source audio no longer exists on the work volume")

    from rockforge.application.gp_pipeline import suggest_tempo_scale
    from rockforge.infrastructure.gpimport.parser import inspect_gp

    try:
        from rockforge.infrastructure.rhythm.librosa_adapter import detect_tempo_from
    except ImportError as exc:  # ml extra absent
        raise HTTPException(
            503, "beat detection needs the 'ml' extra (librosa) — install rockforge[ml]"
        ) from exc

    gp_bpm = float(inspect_gp(gp_path).tempo)
    try:
        detected_bpm = detect_tempo_from(src, payload.from_s)
    except Exception as exc:
        raise HTTPException(422, f"could not analyse the recording: {exc}") from exc
    return DetectTempoOut(
        gp_bpm=gp_bpm,
        detected_bpm=detected_bpm,
        suggested_factor=suggest_tempo_scale(gp_bpm, detected_bpm),
    )


@app.post("/jobs/{job_id}/detect-tuning", response_model=DetectTuningOut)
def detect_tuning(job_id: str) -> DetectTuningOut:
    """Estimate the recording's fine-tuning deviation from A440 (librosa) for
    GP jobs. String/drop tuning is taken from the GP file and is NOT detected
    here (no production-grade solution from polyphonic audio — see
    librosa_adapter). Like /auto-sync this is a proposal: the suggested
    cent_offset is previewed and applied via the normal rebuild."""
    with _session_factory() as session:
        job = session.get(Job, job_id)
        if job is None:
            raise HTTPException(404, "job not found")
        if job.source_type != "gp":
            raise HTTPException(422, "tuning detection only applies to Guitar Pro jobs")
        src = Path(job.source)
    if not src.exists():
        raise HTTPException(409, "source audio no longer exists on the work volume")

    try:
        from rockforge.infrastructure.rhythm.librosa_adapter import estimate_tuning_cents
    except ImportError as exc:  # ml extra absent
        raise HTTPException(
            503, "tuning detection needs the 'ml' extra (librosa) — install rockforge[ml]"
        ) from exc

    try:
        cents = estimate_tuning_cents(src)
    except Exception as exc:
        raise HTTPException(422, f"could not analyse the recording: {exc}") from exc
    return DetectTuningOut(suggested_cent_offset=cents)


@app.post("/jobs/{job_id}/detect-lyrics", response_model=JobOut, status_code=202)
def detect_lyrics_endpoint(job_id: str) -> JobOut:
    """Kick off asynchronous lyric detection (Demucs vocal isolation + WhisperX
    forced alignment) on the job's source recording. Slow — poll
    GET /jobs/{job_id}/lyrics for the result. Never overwrites a completed
    build's status; progress is tracked via params["lyrics_status"]."""
    with _session_factory() as session:
        job = session.get(Job, job_id)
        if job is None:
            raise HTTPException(404, "job not found")
        if job.source_type not in {"gp", "upload", "youtube"}:
            raise HTTPException(422, "lyric detection is not supported for this job's source")
        if not Path(job.source).exists():
            raise HTTPException(409, "source recording no longer exists on the work volume")
        params = dict(job.params or {})
        params["lyrics_status"] = "detecting"
        job.params = params
        session.commit()
        _enqueue_detect(job)
        return _to_out(job)


@app.get("/jobs/{job_id}/lyrics", response_model=LyricsOut)
def get_lyrics(job_id: str) -> LyricsOut:
    """Current lyric-detection status and events (raw, before pad_start_s shift
    for GP jobs). Used by the in-app lyrics editor."""
    with _session_factory() as session:
        job = session.get(Job, job_id)
        if job is None:
            raise HTTPException(404, "job not found")
        params = job.params or {}
        status = str(params.get("lyrics_status", "none"))
        rows = cast("list[dict[str, object]]", params.get("lyrics_events") or [])

        def _num(v: object) -> float:
            return float(v) if isinstance(v, (int, float, str)) else 0.0

        events = [
            LyricEventOut(
                time=_num(r.get("time", 0.0)),
                length=_num(r.get("length", 0.0)),
                lyric=str(r.get("lyric", "")),
            )
            for r in rows
        ]
        # No edited/detected events yet: fall back to lyrics supplied with the
        # job (LRC/UltraStar TXT upload), so the editor and tab view show
        # what will actually be used at build time.
        if not events:
            lrc_text = params.get("lrc_text")
            if isinstance(lrc_text, str) and lrc_text.strip():
                from rockforge.infrastructure.rsxml.vocals import parse_lyrics

                events = [
                    LyricEventOut(time=e.time, length=e.length, lyric=e.lyric)
                    for e in parse_lyrics(lrc_text)
                ]
        log = cast("list[str]", params.get("lyrics_log") or [])
        return LyricsOut(status=status, events=events, log=[str(line) for line in log])


@app.post("/jobs/{job_id}/detect-tones", response_model=JobOut, status_code=202)
def detect_tones_endpoint(job_id: str) -> JobOut:
    """Kick off asynchronous tone detection (Demucs guitar separation + spectral
    analysis) on the job's source recording.  Slow — poll
    GET /jobs/{job_id}/detected-tones for the result.  Progress is tracked via
    params["tone_detection_status"]; never overwrites a completed build's status."""
    with _session_factory() as session:
        job = session.get(Job, job_id)
        if job is None:
            raise HTTPException(404, "job not found")
        if job.source_type not in {"gp", "upload", "youtube"}:
            raise HTTPException(422, "tone detection is not supported for this job's source")
        if not Path(job.source).exists():
            raise HTTPException(409, "source recording no longer exists on the work volume")
        params = dict(job.params or {})
        params["tone_detection_status"] = "detecting"
        job.params = params
        session.commit()
        _enqueue_detect_tones(job)
        return _to_out(job)


@app.get("/jobs/{job_id}/detected-tones", response_model=DetectTonesOut)
def get_detected_tones(job_id: str) -> DetectTonesOut:
    """Current tone-detection status and suggested presets."""
    with _session_factory() as session:
        job = session.get(Job, job_id)
        if job is None:
            raise HTTPException(404, "job not found")
        params = job.params or {}
        status = str(params.get("tone_detection_status", "none"))
        log = cast("list[str]", params.get("tone_detection_log") or [])
        detected = cast("dict[str, Any]", params.get("detected_tones") or {})
        return DetectTonesOut(
            status=status,
            category=str(detected.get("category", "")),
            lead=dict(detected.get("lead", {})),
            rhythm=dict(detected.get("rhythm", {})),
            log=[str(line) for line in log],
        )


@app.post("/jobs/{job_id}/separate-stems", response_model=JobOut, status_code=202)
def separate_stems_endpoint(job_id: str) -> JobOut:
    """Kick off asynchronous per-instrument stem separation (Demucs htdemucs_6s)
    on the job's source recording. Slow — poll GET /jobs/{job_id}/stems for the
    result, then play a stem via GET /jobs/{job_id}/stem/{name}. Progress is
    tracked via params["stems_status"]; never overwrites a completed build.

    Honest limit: Demucs splits by instrument type, so the guitar stem is ALL
    guitars mixed — Lead vs Rhythm cannot be separated from the recording."""
    with _session_factory() as session:
        job = session.get(Job, job_id)
        if job is None:
            raise HTTPException(404, "job not found")
        if job.source_type not in {"gp", "upload", "youtube"}:
            raise HTTPException(422, "stem separation is not supported for this job's source")
        if not Path(job.source).exists():
            raise HTTPException(409, "source recording no longer exists on the work volume")
        params = dict(job.params or {})
        params["stems_status"] = "detecting"
        job.params = params
        session.commit()
        _enqueue_separate_stems(job)
        return _to_out(job)


@app.get("/jobs/{job_id}/stems", response_model=StemsOut)
def get_stems(job_id: str) -> StemsOut:
    """Current stem-separation status and the names of the available stems."""
    with _session_factory() as session:
        job = session.get(Job, job_id)
        if job is None:
            raise HTTPException(404, "job not found")
        params = job.params or {}
        status = str(params.get("stems_status", "none"))
        log = cast("list[str]", params.get("stems_log") or [])
        stems = cast("dict[str, Any]", params.get("stems") or {})
        # Only advertise stems whose file still exists on the work volume.
        available = sorted(name for name, p in stems.items() if Path(str(p)).is_file())
        return StemsOut(status=status, stems=available, log=[str(line) for line in log])


@app.get("/jobs/{job_id}/stem/{name}")
def get_stem_audio(job_id: str, name: str) -> FileResponse:
    """Serve a separated instrument stem (guitar/bass/drums/vocals/other/piano)
    for the viewer's audio-source selector. The stems share the normalized
    recording's clock, so the notes still line up when a stem is soloed."""
    with _session_factory() as session:
        job = session.get(Job, job_id)
        if job is None:
            raise HTTPException(404, "job not found")
        stems = cast("dict[str, Any]", (job.params or {}).get("stems") or {})
        raw = stems.get(name)
        if raw is None:
            raise HTTPException(404, "stem not found — run POST /separate-stems first")
        audio = Path(str(raw))
        if not audio.is_file():
            raise HTTPException(404, "stem file no longer exists on the work volume")
        media_type = mimetypes.guess_type(audio.name)[0] or "application/octet-stream"
        return FileResponse(audio, media_type=media_type)


def _settings_out() -> SettingsOut:
    from rockforge import runtime_settings

    repo, ckpt, queries = runtime_settings.banquet_paths()
    return SettingsOut(
        stem_separator=runtime_settings.stem_separator(),
        banquet_repo=str(repo) if repo else "",
        banquet_ckpt=str(ckpt) if ckpt else "",
        banquet_queries=str(queries) if queries else "",
        banquet=runtime_settings.banquet_validation(),
    )


@app.get("/settings", response_model=SettingsOut)
def get_settings() -> SettingsOut:
    """App settings editable from the UI (stem-separator backend + Banquet paths).
    Includes per-path readiness so the UI can show which parts are configured."""
    return _settings_out()


@app.post("/settings", response_model=SettingsOut)
def update_settings(body: SettingsIn) -> SettingsOut:
    """Persist the settings (work_dir/settings.json), shared by the worker. An
    empty string clears an override (falls back to the env default). Enabling
    Banquet without valid paths is allowed but flagged not-ready in the response
    (the separation itself then fails gracefully with a clear message)."""
    from rockforge import runtime_settings

    if body.stem_separator not in (None, "", "demucs", "banquet"):
        raise HTTPException(422, "stem_separator must be 'demucs' or 'banquet'")
    updates = dict(runtime_settings.load())
    for key in ("stem_separator", "banquet_repo", "banquet_ckpt", "banquet_queries"):
        val = getattr(body, key)
        if val is not None:
            updates[key] = val.strip() if isinstance(val, str) else val
    runtime_settings.save(updates)
    return _settings_out()


@app.get("/jobs/{job_id}/tones")
def get_tones(job_id: str) -> dict[str, Any]:
    """The job's current tone setup (full gear definitions, the base/extra tone
    keys, and the timed changes placed on the partitura). Backs the tone editor."""
    with _session_factory() as session:
        job = session.get(Job, job_id)
        if job is None:
            raise HTTPException(404, "job not found")
        params = job.params or {}
        names = params.get("tone_names")
        tones = params.get("tones")
        changes = params.get("tone_changes")
        return {
            "tone_base": params.get("tone_base"),
            "tone_names": list(names) if isinstance(names, list) else [],
            "tones": list(tones) if isinstance(tones, list) else [],
            "tone_changes": list(changes) if isinstance(changes, list) else [],
        }


@app.get("/jobs/{job_id}/arrangements", response_model=list[ArrangementOut])
def get_arrangements(job_id: str) -> list[ArrangementOut]:
    """Parsed arrangement data for human review (tab viewer, tuning confirmation)."""
    import xml.etree.ElementTree as ET

    with _session_factory() as session:
        job = session.get(Job, job_id)
        if job is None or job.status is not JobStatus.COMPLETED or not job.bundle_dir:
            raise HTTPException(404, "arrangements not available")
        job_params = dict(job.params or {})

    # Per-arrangement tempo scale, falling back to the job-level default.
    raw_default_scale = job_params.get("tempo_scale", 1.0) or 1.0
    default_scale = (
        float(raw_default_scale) if isinstance(raw_default_scale, (int, float, str)) else 1.0
    )
    arr_sync = job_params.get("arrangement_sync") or {}

    def scale_for(kind: str) -> float:
        entry = arr_sync.get(kind) if isinstance(arr_sync, dict) else None
        if isinstance(entry, dict):
            return float(entry.get("tempo_scale", default_scale) or default_scale)
        return default_scale

    out: list[ArrangementOut] = []
    for xml_path in sorted(Path(job.bundle_dir).glob("arrangement_*.xml")):
        root = ET.parse(xml_path).getroot()
        tuning_el = root.find("tuning")
        offsets = (
            [int(tuning_el.get(f"string{i}", "0")) for i in range(6)]
            if tuning_el is not None
            else [0] * 6
        )

        def parse_note(el: ET.Element, chord: bool) -> ArrangementNoteOut:
            techs = [
                t for t in (
                    "hammerOn", "pullOff", "harmonic", "palmMute", "vibrato",
                    "tap", "slap", "pluck", "accent",
                )
                if el.get(t) == "1"
            ]
            bend = el.get("bend", "0")
            try:
                bend_semitones = int(round(float(bend)))
            except ValueError:
                bend_semitones = 0
            if bend_semitones:
                techs.append("bend")
            if el.get("slideTo", "-1") != "-1":
                techs.append("slide")
            return ArrangementNoteOut(
                time=float(el.get("time", "0")),
                string=int(el.get("string", "0")),
                fret=int(el.get("fret", "0")),
                sustain=float(el.get("sustain", "0")),
                chord=chord,
                techniques=techs,
                bend_semitones=bend_semitones,
            )

        notes = [parse_note(el, False) for el in root.findall("levels/level/notes/note")]
        # Chords: name each from the pitches its chordNotes actually sound
        # (RockForge stores no authored chord name). pitch = standard open-string
        # MIDI + this arrangement's tuning offset + fret.
        chord_notes: list[ArrangementNoteOut] = []
        for chord_el in root.findall("levels/level/chords/chord"):
            members = [parse_note(el, True) for el in chord_el.findall("chordNote")]
            pitches = [_STD_TUNING_MIDI[m.string] + offsets[m.string] + m.fret for m in members]
            cname = name_chord(pitches)
            for m in members:
                m.chord_name = cname
            chord_notes.extend(members)
        all_notes = sorted(notes + chord_notes, key=lambda n: (n.time, n.string))
        kind = root.findtext("arrangement", "?")
        # Bar downbeats for the viewer's measure numbering: ebeats with a real
        # measure number (>0); off-beats carry measure="-1".
        ebeats = root.findall("ebeats/ebeat")
        bars = [
            BarOut(measure=int(eb.get("measure", "-1")), time=float(eb.get("time", "0")))
            for eb in ebeats
            if int(eb.get("measure", "-1")) > 0
        ]
        # Every beat (downbeats + off-beats) — the snap grid the tab viewer's
        # note drag quantizes to.
        beats = [float(eb.get("time", "0")) for eb in ebeats]
        out.append(
            ArrangementOut(
                kind=kind,
                tuning_offsets=offsets,
                cent_offset=float(root.findtext("centOffset", "0")),
                average_bpm=float(root.findtext("averageTempo", "0")),
                tempo_scale=scale_for(kind),
                note_count=len(notes),
                chord_count=len(root.findall("levels/level/chords/chord")),
                notes=all_notes,
                bars=bars,
                beats=beats,
            )
        )
    return out


@app.get("/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: str) -> JobOut:
    with _session_factory() as session:
        job = session.get(Job, job_id)
        if job is None:
            raise HTTPException(404, "job not found")
        return _to_out(job)


@app.get("/jobs/{job_id}/source-audio")
def get_source_audio(job_id: str) -> FileResponse:
    """The recording, served for the in-app viewer (playback + waveform).

    Prefers the original file (upload/gp, where `job.source` is a real path);
    for YouTube (`job.source` is a URL) or a moved file, falls back to the
    ingested/normalized audio in the job's work dir so audio-ML jobs are still
    playable and reviewable against the transcribed notes (normalization doesn't
    change timing, so the notes still line up).
    """
    with _session_factory() as session:
        job = session.get(Job, job_id)
        if job is None:
            raise HTTPException(404, "job not found")
        workdir = settings.work_dir / job.id
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


_COVER_ART_SUFFIXES = {".jpg", ".jpeg", ".png"}


@app.post("/jobs/{job_id}/cover", response_model=JobOut, status_code=202)
async def upload_cover_art(job_id: str, file: UploadFile = File(...)) -> JobOut:
    """Upload/replace the album-art image used by the next rebuild (jpg/png).

    Stored as ``<work_dir>/<job_id>/cover<ext>``; referenced via
    ``params["cover_art"]`` and passed through as ``Packager.package(...,
    cover_art=...)``. Does not trigger a rebuild — call ``/rebuild`` after.
    """
    with _session_factory() as session:
        job = session.get(Job, job_id)
        if job is None:
            raise HTTPException(404, "job not found")

        suffix = Path(file.filename or "cover").suffix.lower()
        if suffix not in _COVER_ART_SUFFIXES:
            raise HTTPException(415, f"unsupported image format: {suffix or '(none)'}")

        job_dir = settings.work_dir / job.id
        job_dir.mkdir(parents=True, exist_ok=True)
        # Remove any previous cover with a different extension.
        for old in _COVER_ART_SUFFIXES:
            (job_dir / f"cover{old}").unlink(missing_ok=True)
        dest = job_dir / f"cover{suffix}"
        with dest.open("wb") as fh:
            shutil.copyfileobj(file.file, fh)

        params = dict(job.params or {})
        params["cover_art"] = dest.name
        job.params = params
        session.commit()
        return _to_out(job)


@app.get("/jobs/{job_id}/cover")
def download_cover_art(job_id: str) -> FileResponse:
    with _session_factory() as session:
        job = session.get(Job, job_id)
        cover_art = (job.params or {}).get("cover_art") if job else None
        if job is None or not cover_art:
            raise HTTPException(404, "no cover art uploaded for this job")
        cover_path = settings.work_dir / job.id / cast(str, cover_art)
        if not cover_path.exists():
            raise HTTPException(404, "cover art file is missing on the work volume")
        media_type = mimetypes.guess_type(cover_path.name)[0] or "application/octet-stream"
        return FileResponse(cover_path, media_type=media_type)


@app.get("/version", include_in_schema=False)
def version() -> dict[str, str]:
    return {"version": app.version}


@app.get("/gear-catalogue")
def gear_catalogue() -> dict[str, Any]:
    """The Rocksmith gear catalogue (amps/cabinets/pedals/racks + descriptors)
    that backs the tone-builder UI. Static data — safe to cache client-side."""
    from rockforge.infrastructure.packaging.gear.gear_catalogue import catalogue_for_ui

    return catalogue_for_ui()


@app.post("/heartbeat", include_in_schema=False)
def heartbeat(hidden: bool = False) -> dict[str, bool]:
    """Pinged periodically by the web UI; see Settings.idle_shutdown_s.

    ``hidden=1`` (sent on Page Visibility change / from a backgrounded tab)
    marks the tab as still-open-but-backgrounded, which suspends the idle-kill
    so a throttled tab isn't mistaken for a closed one. Any heartbeat also
    cancels a pending /closing — one arriving after `pagehide` means the page
    came back (a refresh), not a real close."""
    global _last_heartbeat, _closing_at, _tab_hidden
    _last_heartbeat = time.monotonic()
    _tab_hidden = hidden
    # Only a VISIBLE heartbeat cancels a pending close (the page genuinely came
    # back — a refresh). A hidden beacon ALSO fires on tab close
    # (visibilitychange→hidden precedes pagehide), and the two beacons race on
    # the server; if a hidden heartbeat cleared _closing_at it could cancel the
    # /closing the same close just armed, and the tab would never shut down.
    if not hidden:
        _closing_at = None
    return {"ok": True}


@app.post("/closing", include_in_schema=False)
def closing() -> dict[str, bool]:
    """Beaconed by the web UI on `pagehide` (tab close/navigate). Arms a short
    shutdown grace; a following /heartbeat (refresh) cancels it. No-op when
    idle-shutdown is disabled."""
    global _closing_at
    if settings.idle_shutdown_s > 0:
        _closing_at = time.monotonic() + CLOSE_GRACE_S
    return {"ok": True}


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def index() -> str:
    candidates = (
        # repo checkout: src/rockforge/interfaces/api/app.py -> repo root
        Path(__file__).resolve().parents[3].parent / "web" / "index.html",
        # pip-installed (e.g. Docker WORKDIR /app with COPY web ./web)
        Path.cwd() / "web" / "index.html",
    )
    for ui in candidates:
        if ui.exists():
            return ui.read_text(encoding="utf-8")
    return "<h1>RockForge</h1><p>UI not bundled; see /docs for the API.</p>"
