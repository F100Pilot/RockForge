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


PIPELINE_STAGES = [
    "ingest", "normalize", "separate", "transcribe",
    "beat_track", "tuning", "fret_mapping", "package",
]


class JobOut(BaseModel):
    id: str
    status: str
    stage: str | None
    stages: list[str] = PIPELINE_STAGES
    title: str
    artist: str
    created_at: str
    warnings: list[str]
    note_counts: dict[str, int]
    psarc_available: bool
    bundle_available: bool
    error: str | None


class RebuildIn(BaseModel):
    """Human-review overrides: confirmed tuning and whether to attempt the experimental split."""

    tuning_midi: list[int] | None = None  # 6 MIDI pitches, low to high
    cent_offset: float = 0.0
    split_lead_rhythm: bool = True


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
    note_count: int
    chord_count: int
    notes: list[ArrangementNoteOut]


class YouTubeJobIn(BaseModel):
    url: HttpUrl
    title: str
    artist: str
    album: str = ""


def _to_out(job: Job) -> JobOut:
    return JobOut(
        id=job.id,
        status=job.status.value,
        stage=job.stage,
        title=job.title,
        artist=job.artist,
        created_at=job.created_at.isoformat() if job.created_at else "",
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


@app.get("/jobs", response_model=list[JobOut])
def list_jobs(limit: int = 50) -> list[JobOut]:
    from sqlalchemy import select

    with _session_factory() as session:
        jobs = session.scalars(
            select(Job).order_by(Job.created_at.desc()).limit(min(limit, 200))
        ).all()
        return [_to_out(j) for j in jobs]


@app.post("/jobs/{job_id}/rebuild", response_model=JobOut, status_code=202)
def rebuild_job(job_id: str, payload: RebuildIn) -> JobOut:
    """Re-run the pipeline on the same source with human-confirmed overrides."""
    if payload.tuning_midi is not None and len(payload.tuning_midi) != 6:
        raise HTTPException(422, "tuning_midi must contain exactly 6 MIDI pitches (low to high)")
    with _session_factory() as session:
        original = session.get(Job, job_id)
        if original is None:
            raise HTTPException(404, "job not found")
        if original.source_type == "upload" and not Path(original.source).exists():
            raise HTTPException(409, "original upload no longer exists on the work volume")
        params: dict[str, object] = {"split_lead_rhythm": payload.split_lead_rhythm}
        if payload.tuning_midi is not None:
            params["tuning_midi"] = payload.tuning_midi
            params["cent_offset"] = payload.cent_offset
        job = Job(
            source=original.source,
            source_type=original.source_type,
            title=original.title,
            artist=original.artist,
            album=original.album,
            params=params,
        )
        session.add(job)
        session.commit()
        _enqueue(job)
        return _to_out(job)


@app.get("/jobs/{job_id}/arrangements", response_model=list[ArrangementOut])
def get_arrangements(job_id: str) -> list[ArrangementOut]:
    """Parsed arrangement data for human review (tab viewer, tuning confirmation)."""
    import xml.etree.ElementTree as ET

    with _session_factory() as session:
        job = session.get(Job, job_id)
        if job is None or job.status is not JobStatus.COMPLETED or not job.bundle_dir:
            raise HTTPException(404, "arrangements not available")

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
                t for t in ("hammerOn", "pullOff", "harmonic", "palmMute", "vibrato")
                if el.get(t) == "1"
            ]
            if el.get("bend", "0") != "0":
                techs.append("bend")
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
        out.append(
            ArrangementOut(
                kind=root.findtext("arrangement", "?"),
                tuning_offsets=offsets,
                cent_offset=float(root.findtext("centOffset", "0")),
                average_bpm=float(root.findtext("averageTempo", "0")),
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
