"""REST API: submit audio/YouTube jobs, poll status, download results."""

from __future__ import annotations

import mimetypes
import shutil
import uuid
from pathlib import Path
from typing import cast

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, Response
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
    tempo_scale: float
    import_mutes: bool
    error: str | None
    lyrics_status: str = "none"
    cover_art: bool = False


class RebuildIn(BaseModel):
    """Human-review overrides: confirmed tuning and whether to attempt the experimental split."""

    tuning_midi: list[int] | None = None  # 6 MIDI pitches, low to high
    cent_offset: float = 0.0
    offset_s: float | None = None  # GP sync: second in the recording where the song starts
    tempo_scale: float | None = None  # GP sync: stretch/compress the whole chart timeline
    split_lead_rhythm: bool = True
    # Manual drift-correction points: (chart_time_s, corrected_time_s) pairs, in the
    # chart's already-shifted timeline (as shown in the tab viewer).
    sync_anchors: list[tuple[float, float]] | None = None
    # When set (ArrangementKind value, e.g. "Lead"/"Rhythm"/"Combined"), tempo_scale
    # and sync_anchors are scoped to that arrangement alone instead of all of them.
    arrangement: str | None = None
    # GP: when False, palm mute / slap / pop / tap are stripped (plain notes).
    import_mutes: bool | None = None
    # Edited per-word lyrics from the in-app lyrics editor. When set (even to an
    # empty list), replaces params["lyrics_events"] and clears lyrics_status so
    # the next build uses the edited lyrics. None leaves existing lyrics alone.
    lyrics_events: list[LyricEventOut] | None = None


class ArrangementNoteOut(BaseModel):
    time: float
    string: int
    fret: int
    sustain: float
    chord: bool
    techniques: list[str]


class ArrangementOut(BaseModel):
    kind: str
    tuning_offsets: list[int]
    cent_offset: float
    average_bpm: float
    tempo_scale: float  # this arrangement's own tempo scale (GP sync), 1.0 if none
    note_count: int
    chord_count: int
    notes: list[ArrangementNoteOut]


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
        tempo_scale=tempo_scale,
        import_mutes=bool((job.params or {}).get("import_mute_techniques", True)),
        error=job.error,
        lyrics_status=str((job.params or {}).get("lyrics_status", "none")),
        cover_art=bool((job.params or {}).get("cover_art")),
    )


def _enqueue(job: Job) -> None:
    from rockforge.interfaces.worker.celery_app import generate_cdlc

    generate_cdlc.delay(job.id)


def _enqueue_detect(job: Job) -> None:
    from rockforge.interfaces.worker.celery_app import detect_lyrics

    detect_lyrics.delay(job.id)


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


GP_SUFFIXES = {".gp3", ".gp4", ".gp5"}
GP_REJECTED_SUFFIXES = {".gpx", ".gp"}


@app.post("/gp/inspect", response_model=GpInspectOut)
async def inspect_gp_file(file: UploadFile = File(...)) -> GpInspectOut:
    """Upload a Guitar Pro file, get its tracks for selection. The file is kept
    server-side and referenced by gp_token when creating the job."""
    suffix = Path(file.filename or "").suffix.lower()
    if suffix in GP_REJECTED_SUFFIXES:
        raise HTTPException(
            415,
            "GPX/GP7 is not supported (the parser reads GP3/GP4/GP5 only). "
            "Export as GP5 from Guitar Pro or TuxGuitar and upload again.",
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


@app.get("/jobs", response_model=list[JobOut])
def list_jobs(limit: int = 50) -> list[JobOut]:
    from sqlalchemy import select

    with _session_factory() as session:
        jobs = session.scalars(
            select(Job).order_by(Job.created_at.desc()).limit(min(limit, 200))
        ).all()
        return [_to_out(j) for j in jobs]


@app.delete("/jobs/{job_id}", status_code=204)
def delete_job(job_id: str) -> Response:
    """Delete a job and its work artifacts. Running jobs must finish first.

    The uploaded source file is removed only when no other job (e.g. a rebuild)
    still references it."""
    from sqlalchemy import func, select

    with _session_factory() as session:
        job = session.get(Job, job_id)
        if job is None:
            raise HTTPException(404, "job not found")
        if job.status is JobStatus.RUNNING:
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

        if payload.tempo_scale is not None:
            if original.source_type != "gp":
                raise HTTPException(422, "tempo_scale only applies to Guitar Pro jobs")
            if payload.tempo_scale <= 0.0:
                raise HTTPException(422, "tempo_scale must be > 0")
            if payload.arrangement is not None:
                _arr_entry(payload.arrangement)["tempo_scale"] = payload.tempo_scale
            else:
                params["tempo_scale"] = payload.tempo_scale
        if payload.sync_anchors is not None:
            if original.source_type != "gp":
                raise HTTPException(422, "sync_anchors only apply to Guitar Pro jobs")
            if payload.sync_anchors:
                # Append as a new correction round on top of any carried-over rounds, so
                # corrections made in earlier sessions (after reloading a completed job)
                # are preserved rather than overwritten. Scope to one arrangement when
                # requested, else the job-level (shared-default) list.
                target = (
                    _arr_entry(payload.arrangement)
                    if payload.arrangement is not None
                    else params
                )
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
            if el.get("bend", "0") != "0":
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
            )

        notes = [parse_note(el, False) for el in root.findall("levels/level/notes/note")]
        chord_notes = [
            parse_note(el, True)
            for el in root.findall("levels/level/chords/chord/chordNote")
        ]
        all_notes = sorted(notes + chord_notes, key=lambda n: (n.time, n.string))
        kind = root.findtext("arrangement", "?")
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
    """The original recording, served for the in-app visual sync tool.

    This is the un-padded upload (source_type upload/gp); the GP sync UI plays it
    and overlays note ticks so the user can find the second where the song starts.
    """
    with _session_factory() as session:
        job = session.get(Job, job_id)
        if job is None:
            raise HTTPException(404, "job not found")
        if job.source_type not in {"upload", "gp"}:
            raise HTTPException(404, "no local source audio for this job")
        src = Path(job.source)
        if not src.exists():
            raise HTTPException(404, "source audio no longer exists on the work volume")
        media_type = mimetypes.guess_type(src.name)[0] or "application/octet-stream"
        return FileResponse(src, media_type=media_type)


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
