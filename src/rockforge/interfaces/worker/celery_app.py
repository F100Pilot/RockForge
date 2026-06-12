"""Celery application and the long-running pipeline task."""

from __future__ import annotations

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


def _build_use_case():  # noqa: ANN202 - heavy imports deferred to worker runtime
    from rockforge.application.pipeline import GenerateCdlcUseCase
    from rockforge.infrastructure.ingestion.sources import LocalFileIngestor, YouTubeIngestor
    from rockforge.infrastructure.normalize.ffmpeg import FfmpegNormalizer
    from rockforge.infrastructure.packaging.dlcbuilder import DlcBuilderPackager
    from rockforge.infrastructure.packaging.wwise import WwiseWemConverter
    from rockforge.infrastructure.rhythm.librosa_adapter import LibrosaRhythmAdapter
    from rockforge.infrastructure.rolesplit.heuristic import HeuristicRoleSplitter
    from rockforge.infrastructure.separation.demucs_adapter import DemucsSeparator
    from rockforge.infrastructure.transcription.basic_pitch_adapter import BasicPitchTranscriber

    rhythm = LibrosaRhythmAdapter()

    from rockforge.infrastructure.lyrics.whisperx_adapter import WhisperXLyricTranscriber

    lyric_transcriber = (
        WhisperXLyricTranscriber(device=settings.demucs_device)
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
            separator=DemucsSeparator(device=settings.demucs_device),
            transcriber=BasicPitchTranscriber(),
            beat_tracker=rhythm,
            tuning_estimator=rhythm,
            role_splitter=HeuristicRoleSplitter(),
            packager=DlcBuilderPackager(
                psarc_packer_cmd=settings.psarc_packer_cmd,
                wem_converter=WwiseWemConverter(
                    wwise_root=settings.resolved_wwise_root(),
                ),
            ),
        )

    return make


def _build_gp_use_case():  # noqa: ANN202
    from rockforge.application.gp_pipeline import GenerateFromGpUseCase
    from rockforge.infrastructure.ingestion.sources import LocalFileIngestor
    from rockforge.infrastructure.normalize.ffmpeg import FfmpegNormalizer
    from rockforge.infrastructure.packaging.dlcbuilder import DlcBuilderPackager
    from rockforge.infrastructure.packaging.wwise import WwiseWemConverter

    return GenerateFromGpUseCase(
        ingestor=LocalFileIngestor(),
        normalizer=FfmpegNormalizer(),
        packager=DlcBuilderPackager(
            psarc_packer_cmd=settings.psarc_packer_cmd,
            wem_converter=WwiseWemConverter(
                wwise_root=settings.resolved_wwise_root(),
            ),
        ),
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

            if job.source_type == "gp":
                from rockforge.application.gp_pipeline import GenerateFromGpUseCase, GpJobSpec
                from rockforge.domain.arrangement import SongMetadata as Meta
                from rockforge.domain.arrangement import ToneChange

                gp_use_case: GenerateFromGpUseCase = _build_gp_use_case()
                spec = GpJobSpec(
                    gp_path=Path(params["gp_path"]),
                    audio_source=job.source,
                    lead_track=params.get("lead_track"),
                    rhythm_track=params.get("rhythm_track"),
                    offset_s=float(params.get("offset_s", 0.0)),
                    lrc_text=params.get("lrc_text"),
                    tone_base=params.get("tone_base"),
                    tone_names=list(params.get("tone_names", [])),
                    tone_changes=[
                        ToneChange(time=float(c["time"]), name=str(c["name"]))
                        for c in params.get("tone_changes", [])
                    ],
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
