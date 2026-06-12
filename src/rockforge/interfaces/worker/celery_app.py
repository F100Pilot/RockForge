"""Celery application and the long-running pipeline task."""

from __future__ import annotations

from pathlib import Path

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

    def make(source_type: str) -> GenerateCdlcUseCase:
        ingestor = (
            YouTubeIngestor(enabled=settings.enable_youtube)
            if source_type == "youtube"
            else LocalFileIngestor()
        )
        return GenerateCdlcUseCase(
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
                    conversion=settings.wwise_conversion,
                ),
            ),
        )

    return make


@celery_app.task(name="rockforge.generate_cdlc")
def generate_cdlc(job_id: str) -> None:
    session_factory = make_session_factory(settings.database_url)
    with session_factory() as session:
        job = session.get_one(Job, job_id)
        job.status = JobStatus.RUNNING
        session.commit()

        try:
            from rockforge.domain.music import Tuning

            use_case = _build_use_case()(job.source_type)
            workdir = settings.work_dir / job.id
            workdir.mkdir(parents=True, exist_ok=True)

            params = job.params or {}
            tuning_override = None
            if "tuning_midi" in params:
                tuning_override = Tuning(
                    midi=tuple(params["tuning_midi"]),
                    cent_offset=float(params.get("cent_offset", 0.0)),
                )

            def on_stage(name: str) -> None:
                job.stage = name
                session.commit()

            result = use_case.run(
                source=job.source,
                metadata=SongMetadata(
                    title=job.title, artist=job.artist, album=job.album, year=job.year
                ),
                workdir=Path(workdir),
                split_lead_rhythm=bool(params.get("split_lead_rhythm", True)),
                tuning_override=tuning_override,
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
