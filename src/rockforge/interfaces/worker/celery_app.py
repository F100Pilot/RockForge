"""Celery application and the long-running pipeline task."""

from __future__ import annotations

from datetime import UTC, datetime
from functools import cache
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


@celery_app.on_after_finalize.connect
def _warm_up_device(**_kwargs: object) -> None:
    """Probe CUDA once at worker startup so the first job doesn't pay for it.

    torch.cuda.is_available() initialises the CUDA runtime on first call
    (30–60s on Windows). Running it in the background while the worker waits
    for jobs means it's already cached by the time the first task arrives.
    """
    _resolve_device(settings.demucs_device)
    _resolve_device(settings.lyrics_device())


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


@cache
def _resolve_device(requested: str) -> str:
    """Resolve a configured device to a concrete one for the ML adapters.

    "cpu"/"cuda" pass through unchanged; "auto" picks "cuda" when a usable
    CUDA GPU (NVIDIA) is present and "cpu" otherwise. The torch import is
    deferred (worker-only, heavy) and any failure degrades to CPU — so "auto"
    is always safe even without the ml/lyrics extras installed.

    Cached per-process: torch import + CUDA init happen only once, not on
    every job (CUDA init on Windows can take 30–60s the first time).
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
                from rockforge.infrastructure.packaging.gear.gear_catalogue import (
                    tones_from_dicts,
                )
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
                    tones=tones_from_dicts(list(params.get("tones") or [])),
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


@celery_app.task(name="rockforge.detect_lyrics", time_limit=3600)
def detect_lyrics(job_id: str) -> None:
    """Detect lyrics from a job's source recording (Demucs vocals + WhisperX).

    Slow (minutes); progress is reported via params["lyrics_status"] rather
    than JobStatus, so it never hides a completed build or disables /arrangements.
    Human-readable progress is appended to params["lyrics_log"].

    time_limit=3600: Hard timeout at 60 minutes. If the task runs longer,
    Celery/worker will force-kill it. In inprocess mode, this is advisory only.
    """
    session_factory = make_session_factory(settings.database_url)
    with session_factory() as session:
        job = session.get(Job, job_id)
        if job is None:  # deleted while queued — nothing to do
            return
        job.stage = "lyrics"
        params = dict(job.params or {})
        warnings = list(job.warnings or [])
        params["lyrics_log"] = []
        _log_lyrics_stage(params, "lyric detection started")
        try:
            _log_lyrics_stage(params, "loading ML models (can take 30–60s on first run)…")
            job.params = params
            session.commit()

            _log_lyrics_stage(params, "importing torch…")
            job.params = params
            session.commit()
            device = _resolve_device(settings.lyrics_device())

            _log_lyrics_stage(params, "importing demucs and whisperx…")
            job.params = params
            session.commit()
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


def _log_tone_stage(params: dict[str, Any], message: str) -> None:
    """Append a timestamped line to params["tone_detection_log"]."""
    log = cast("list[str]", params.get("tone_detection_log") or [])
    stamp = datetime.now(UTC).strftime("%H:%M:%S")
    params["tone_detection_log"] = [*log, f"[{stamp}] {message}"][-50:]


@celery_app.task(name="rockforge.detect_tones", time_limit=3600)
def detect_tones(job_id: str) -> None:
    """Detect guitar tone character from the recording (Demucs guitar separation
    + spectral analysis → preset suggestion).

    Slow (minutes for Demucs); progress tracked via
    params["tone_detection_status"]. Results land in params["detected_tones"]
    as lead + rhythm tone dicts ready for the tone editor.
    """
    session_factory = make_session_factory(settings.database_url)
    with session_factory() as session:
        job = session.get(Job, job_id)
        if job is None:
            return
        params = dict(job.params or {})
        warnings = list(job.warnings or [])
        params["tone_detection_log"] = []
        _log_tone_stage(params, "tone detection started")
        try:
            _log_tone_stage(params, "importing ML models…")
            job.params = params
            session.commit()

            device = _resolve_device(settings.demucs_device)

            from rockforge.infrastructure.normalize.ffmpeg import FfmpegNormalizer
            from rockforge.infrastructure.separation.demucs_adapter import DemucsSeparator

            normalizer = FfmpegNormalizer()
            separator = DemucsSeparator(device=device)

            workdir = settings.work_dir / job.id / "tone_detection"
            workdir.mkdir(parents=True, exist_ok=True)

            _log_tone_stage(
                params, f"device: {device} ({'GPU' if device == 'cuda' else 'CPU'})"
            )

            params["tone_detection_status"] = "normalizing"
            _log_tone_stage(params, "normalizing source audio (ffmpeg)")
            job.params = params
            session.commit()
            normalized = normalizer.normalize(Path(job.source), workdir)

            params["tone_detection_status"] = "separating"
            _log_tone_stage(params, "isolating guitar stem (Demucs, 6-stem)")
            job.params = params
            session.commit()
            guitar_stem = separator.separate_guitar(normalized, workdir)

            params["tone_detection_status"] = "analyzing"
            _log_tone_stage(params, "analyzing spectral characteristics")
            job.params = params
            session.commit()

            from rockforge.infrastructure.tone_analysis.analyzer import analyze_guitar_tone

            profile = analyze_guitar_tone(guitar_stem)

            from rockforge.infrastructure.packaging.gear.tone_presets import suggest_tones

            suggestion = suggest_tones(profile.category)

            params["detected_tones"] = {
                "category": suggestion["category"],
                "lead": suggestion["lead"],
                "rhythm": suggestion["rhythm"],
                "profile": {
                    "gain_level": profile.gain_level,
                    "brightness": profile.brightness,
                    "low_end": profile.low_end,
                    "dynamic_range": profile.dynamic_range,
                },
            }
            params["tone_detection_status"] = "ready"
            _log_tone_stage(
                params,
                f"done — category: {profile.category} "
                f"(gain={profile.gain_level:.2f}, brightness={profile.brightness:.2f})",
            )
        except Exception as exc:
            params["tone_detection_status"] = "unavailable"
            warnings.append(f"tone detection failed: {type(exc).__name__}: {exc}")
            _log_tone_stage(params, f"failed: {type(exc).__name__}: {exc}")
        job.params = params
        job.warnings = warnings
        session.commit()
