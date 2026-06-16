"""Celery application and the long-running pipeline task."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from celery import Celery

from rockforge.config import settings
from rockforge.domain.arrangement import SongMetadata
from rockforge.infrastructure.db.models import Job, JobStatus, make_session_factory

celery_app = Celery(
    "rockforge", broker=settings.broker_url, backend=settings.result_backend
)
celery_app.conf.task_track_started = True


def _build_packager():  # noqa: ANN202 - heavy imports deferred to worker runtime
    from rockforge.infrastructure.packaging.wwise import WwiseWemConverter

    wem_converter = WwiseWemConverter(wwise_root=settings.resolved_wwise_root())

    if settings.psarc_mode == "native":
        from rockforge.infrastructure.packaging.psarc.packer import NativePsarcPacker

        return NativePsarcPacker(wem_converter=wem_converter)

    from rockforge.infrastructure.packaging.dlcbuilder import DlcBuilderPackager

    return DlcBuilderPackager(
        psarc_packer_cmd=settings.psarc_packer_cmd,
        wem_converter=wem_converter,
    )


def _resolve_device(requested: str) -> str:
    """Resolve a configured device to a concrete one for the ML adapters.

    "cpu"/"cuda" pass through unchanged; "auto" picks "cuda" when a usable
    CUDA GPU (NVIDIA) is present and "cpu" otherwise. The torch import is
    deferred (worker-only, heavy) and any failure degrades to CPU — so "auto"
    is always safe even without the ml/lyrics extras installed.
    """
    if requested != "auto":
        return requested
    try:
        import torch

        if torch.cuda.is_available():
            return "cuda"
    except Exception:
        pass
    return "cpu"


def _build_use_case():  # noqa: ANN202 - heavy imports deferred to worker runtime
    from rockforge.application.pipeline import GenerateCdlcUseCase
    from rockforge.infrastructure.ingestion.sources import LocalFileIngestor, YouTubeIngestor
    from rockforge.infrastructure.normalize.ffmpeg import FfmpegNormalizer
    from rockforge.infrastructure.rhythm.librosa_adapter import LibrosaRhythmAdapter
    from rockforge.infrastructure.rolesplit.heuristic import HeuristicRoleSplitter
    from rockforge.infrastructure.separation.demucs_adapter import DemucsSeparator
    from rockforge.infrastructure.transcription.basic_pitch_adapter import BasicPitchTranscriber

    rhythm = LibrosaRhythmAdapter()
    device = _resolve_device(settings.demucs_device)

    from rockforge.infrastructure.lyrics.whisperx_adapter import WhisperXLyricTranscriber

    lyric_transcriber = (
        WhisperXLyricTranscriber(device=device)
        if WhisperXLyricTranscriber.available()
        else None
    )

    def make(source_type: str) -> GenerateCdlcUseCase:
        ingestor = (
            YouTubeIngestor(enabled=settings.enable_youtube)
            if source_type == "youtube"
            else LocalFileIngestor()
        )
        return GenerateCdlcUseCase(
            lyric_transcriber=lyric_transcriber,
            ingestor=ingestor,
            normalizer=FfmpegNormalizer(),
            separator=DemucsSeparator(device=device),
            transcriber=BasicPitchTranscriber(),
            beat_tracker=rhythm,
            tuning_estimator=rhythm,
            role_splitter=HeuristicRoleSplitter(),
            packager=_build_packager(),
        )

    return make


def _build_detection(device: str) -> tuple[Any, Any, Any]:  # heavy imports deferred to worker
    from rockforge.infrastructure.lyrics.whisperx_adapter import WhisperXLyricTranscriber
    from rockforge.infrastructure.normalize.ffmpeg import FfmpegNormalizer
    from rockforge.infrastructure.separation.demucs_adapter import DemucsSeparator

    return (
        FfmpegNormalizer(),
        DemucsSeparator(device=device),
        WhisperXLyricTranscriber,
    )


def _build_gp_use_case():  # noqa: ANN202
    from rockforge.application.gp_pipeline import GenerateFromGpUseCase
    from rockforge.infrastructure.ingestion.sources import LocalFileIngestor
    from rockforge.infrastructure.normalize.ffmpeg import FfmpegNormalizer

    return GenerateFromGpUseCase(
        ingestor=LocalFileIngestor(),
        normalizer=FfmpegNormalizer(),
        packager=_build_packager(),
    )


@celery_app.task(name="rockforge.generate_cdlc")
def generate_cdlc(job_id: str) -> None:
    session_factory = make_session_factory(settings.database_url)
    with session_factory() as session:
        job = session.get(Job, job_id)
        if job is None:  # deleted while queued — nothing to do
            return
        job.status = JobStatus.RUNNING
        session.commit()

        try:
            from rockforge.domain.music import Tuning

            workdir = settings.work_dir / job.id
            workdir.mkdir(parents=True, exist_ok=True)
            # params is an untyped JSON boundary (values arrive as `object`);
            # cast once and coerce explicitly below.
            params = cast(dict[str, Any], job.params or {})

            def on_stage(name: str) -> None:
                job.stage = name
                session.commit()

            cover_art: Path | None = None
            if params.get("cover_art"):
                candidate = Path(workdir) / cast(str, params["cover_art"])
                if candidate.exists():
                    cover_art = candidate

            if job.source_type == "gp":
                from rockforge.application.gp_pipeline import (
                    ArrangementSync,
                    GenerateFromGpUseCase,
                    GpJobSpec,
                )
                from rockforge.domain.arrangement import SongMetadata as Meta
                from rockforge.domain.arrangement import ToneChange
                from rockforge.infrastructure.rsxml.vocals import events_from_dicts

                def _stages(raw: Any) -> list[list[tuple[float, float]]]:
                    return [
                        [(float(a[0]), float(a[1])) for a in stage] for stage in (raw or [])
                    ]

                gp_use_case: GenerateFromGpUseCase = _build_gp_use_case()
                spec = GpJobSpec(
                    gp_path=Path(params["gp_path"]),
                    audio_source=job.source,
                    lead_track=params.get("lead_track"),
                    rhythm_track=params.get("rhythm_track"),
                    offset_s=float(params.get("offset_s", 0.0)),
                    tempo_scale=float(params.get("tempo_scale", 1.0)),
                    lrc_text=params.get("lrc_text"),
                    tone_base=params.get("tone_base"),
                    tone_names=list(params.get("tone_names", [])),
                    tone_changes=[
                        ToneChange(time=float(c["time"]), name=str(c["name"]))
                        for c in params.get("tone_changes", [])
                    ],
                    sync_anchor_stages=_stages(params.get("sync_anchor_stages")),
                    arrangement_sync={
                        str(kind): ArrangementSync(
                            tempo_scale=float(ov.get("tempo_scale", 1.0)),
                            sync_anchor_stages=_stages(ov.get("sync_anchor_stages")),
                        )
                        for kind, ov in (params.get("arrangement_sync") or {}).items()
                    },
                    import_mute_techniques=bool(params.get("import_mute_techniques", True)),
                    lyrics_events=(
                        events_from_dicts(params["lyrics_events"])
                        if params.get("lyrics_events")
                        else None
                    ),
                    cover_art=cover_art,
                )
                result = gp_use_case.run(
                    spec=spec,
                    metadata=Meta(
                        title=job.title, artist=job.artist, album=job.album, year=job.year
                    ),
                    workdir=Path(workdir),
                    on_stage=on_stage,
                )
                job.status = JobStatus.COMPLETED
                job.warnings = list(result.warnings)
                job.note_counts = result.note_counts
                job.bundle_dir = str(result.packaging.bundle_dir)
                job.psarc_path = (
                    str(result.packaging.psarc_path) if result.packaging.psarc_path else None
                )
                session.commit()
                return

            from rockforge.infrastructure.rsxml.vocals import events_from_dicts

            use_case = _build_use_case()(job.source_type)
            tuning_override = None
            if "tuning_midi" in params:
                m = [int(x) for x in params["tuning_midi"]]
                if len(m) != 6:
                    raise ValueError(f"tuning_midi must have 6 values, got {len(m)}")
                tuning_override = Tuning(
                    midi=(m[0], m[1], m[2], m[3], m[4], m[5]),
                    cent_offset=float(params.get("cent_offset", 0.0)),
                )

            result = use_case.run(
                source=job.source,
                metadata=SongMetadata(
                    title=job.title, artist=job.artist, album=job.album, year=job.year
                ),
                workdir=Path(workdir),
                split_lead_rhythm=bool(params.get("split_lead_rhythm", True)),
                tuning_override=tuning_override,
                offset_s=float(params.get("offset_s", 0.0)),
                transcribe_lyrics=bool(params.get("transcribe_lyrics", False)),
                lyrics_events=(
                    events_from_dicts(params["lyrics_events"])
                    if params.get("lyrics_events")
                    else None
                ),
                cover_art=cover_art,
                on_stage=on_stage,
            )
            job.status = JobStatus.COMPLETED
            job.warnings = list(result.warnings)
            job.note_counts = result.note_counts
            job.bundle_dir = str(result.packaging.bundle_dir)
            job.psarc_path = (
                str(result.packaging.psarc_path) if result.packaging.psarc_path else None
            )
        except Exception as exc:  # report faithfully; never mask failures
            job.status = JobStatus.FAILED
            job.error = f"{type(exc).__name__}: {exc}"
        session.commit()


def _log_lyrics_stage(params: dict[str, Any], message: str) -> None:
    """Append a timestamped line to params["lyrics_log"], capped to the most
    recent 50 entries so the job row doesn't grow unbounded."""
    log = cast("list[str]", params.get("lyrics_log") or [])
    stamp = datetime.now(UTC).strftime("%H:%M:%S")
    params["lyrics_log"] = [*log, f"[{stamp}] {message}"][-50:]


@celery_app.task(name="rockforge.detect_lyrics")
def detect_lyrics(job_id: str) -> None:
    """Detect lyrics from a job's source recording (Demucs vocals + WhisperX).

    Slow (minutes); progress is reported via params["lyrics_status"] rather
    than JobStatus, so it never hides a completed build or disables /arrangements.
    Human-readable progress is appended to params["lyrics_log"].
    """
    session_factory = make_session_factory(settings.database_url)
    with session_factory() as session:
        job = session.get(Job, job_id)
        if job is None:  # deleted while queued — nothing to do
            return
        job.stage = "lyrics"
        # Copy: job.params is the same dict object SQLAlchemy holds, and
        # reassigning that same object back doesn't register as a change
        # (old == new by identity), so the JSON column never gets written.
        params = dict(job.params or {})
        warnings = list(job.warnings or [])
        params["lyrics_log"] = []
        _log_lyrics_stage(params, "lyric detection started")
        try:
            device = _resolve_device(settings.lyrics_device())
            normalizer, separator, transcriber_cls = _build_detection(device)
            if not transcriber_cls.available():
                warnings.append(
                    "lyric detection requested but whisperx is not installed "
                    "(pip install 'rockforge[lyrics]')"
                )
                params["lyrics_status"] = "unavailable"
                _log_lyrics_stage(params, "whisperx is not installed — aborting")
            else:
                workdir = settings.work_dir / job.id / "lyrics"
                workdir.mkdir(parents=True, exist_ok=True)

                _log_lyrics_stage(
                    params, f"device: {device} ({'GPU' if device == 'cuda' else 'CPU'})"
                )
                params["lyrics_status"] = "normalizing"
                _log_lyrics_stage(params, "normalizing source audio (ffmpeg)")
                job.params = params
                session.commit()
                normalized = normalizer.normalize(Path(job.source), workdir)

                params["lyrics_status"] = "separating"
                _log_lyrics_stage(params, "isolating vocals (Demucs, 2-stem) — can take a while")
                job.params = params
                session.commit()
                vocals_stem = separator.separate_vocals(normalized, workdir)

                params["lyrics_status"] = "transcribing"
                _log_lyrics_stage(params, f"transcribing (WhisperX/{settings.whisper_model})")
                job.params = params
                session.commit()
                events = transcriber_cls(
                    model_size=settings.whisper_model, device=device
                ).transcribe(vocals_stem)

                params["lyrics_events"] = [
                    {"time": e.time, "length": e.length, "lyric": e.lyric} for e in events
                ]
                params["lyrics_status"] = "ready" if events else "empty"
                _log_lyrics_stage(params, f"done — {len(events)} word(s) detected")
        except Exception as exc:  # never crash the job over lyric detection
            params["lyrics_status"] = "unavailable"
            warnings.append(f"lyric detection failed: {type(exc).__name__}: {exc}")
            _log_lyrics_stage(params, f"failed: {type(exc).__name__}: {exc}")
        job.params = params
        job.warnings = warnings
        session.commit()
