"""In-process task dispatch (the standalone .exe's Celery-free path) — MIN-10.

The four enqueue_* entry points hand a job id to the celery_app task functions
through a single-worker thread pool, and each _run_* wrapper must swallow (log,
not propagate) task exceptions so a failed background run never takes the pool
worker down. Both were previously untested."""

from __future__ import annotations

import pytest

from rockforge.interfaces.worker import celery_app, inprocess


class _SyncPool:
    """Runs submitted work immediately on the calling thread, so a test can
    assert the effect without racing a background worker."""

    def __init__(self) -> None:
        self.shutdown_calls: list[bool] = []

    def submit(self, fn, *args):  # noqa: ANN001, ANN202
        fn(*args)

    def shutdown(self, wait: bool = False) -> None:
        self.shutdown_calls.append(wait)


@pytest.fixture()
def sync_pool(monkeypatch) -> _SyncPool:
    pool = _SyncPool()
    monkeypatch.setattr(inprocess, "_pool", pool)
    return pool


@pytest.mark.parametrize(
    ("enqueue", "task_name"),
    [
        (inprocess.enqueue_generate, "generate_cdlc"),
        (inprocess.enqueue_detect, "detect_lyrics"),
        (inprocess.enqueue_detect_tones, "detect_tones"),
        (inprocess.enqueue_separate_stems, "separate_stems"),
    ],
)
def test_enqueue_dispatches_to_the_matching_celery_task(
    monkeypatch, sync_pool: _SyncPool, enqueue, task_name
) -> None:
    called: list[str] = []
    monkeypatch.setattr(celery_app, task_name, lambda job_id: called.append(job_id))

    enqueue("job-123")

    assert called == ["job-123"]


@pytest.mark.parametrize(
    ("enqueue", "task_name"),
    [
        (inprocess.enqueue_generate, "generate_cdlc"),
        (inprocess.enqueue_detect, "detect_lyrics"),
        (inprocess.enqueue_detect_tones, "detect_tones"),
        (inprocess.enqueue_separate_stems, "separate_stems"),
    ],
)
def test_a_failing_task_is_swallowed_not_propagated(
    monkeypatch, sync_pool: _SyncPool, enqueue, task_name
) -> None:
    def _boom(job_id: str) -> None:
        raise RuntimeError("task blew up")

    monkeypatch.setattr(celery_app, task_name, _boom)

    # Must NOT raise — the _run_* wrapper logs and returns.
    enqueue("job-123")


def test_shutdown_stops_the_pool_without_waiting(sync_pool: _SyncPool) -> None:
    inprocess.shutdown()
    assert sync_pool.shutdown_calls == [False]


def _job_db(monkeypatch, tmp_path, **fields):  # noqa: ANN001, ANN202
    from rockforge.config import settings
    from rockforge.infrastructure.db.models import Job, make_session_factory

    url = f"sqlite:///{tmp_path / 'jobs.sqlite'}"
    monkeypatch.setattr(settings, "database_url", url)
    factory = make_session_factory(url)
    with factory() as session:
        session.add(Job(id="job-1", source="song.mp3", source_type="gp", title="t", artist="a",
                        **fields))
        session.commit()
    return factory


def test_a_build_that_dies_before_it_starts_fails_the_job_visibly(
    monkeypatch, tmp_path, sync_pool: _SyncPool
) -> None:
    """The standalone build once lacked a module Celery imports by name, so the
    worker died importing celery_app — before generate_cdlc's own error handling
    existed to catch anything. The job stayed PENDING forever and the reason
    went only to a log file; the UI just sat on the first stage."""
    from rockforge.infrastructure.db.models import Job, JobStatus

    factory = _job_db(monkeypatch, tmp_path)

    def _missing(job_id: str) -> None:
        raise ModuleNotFoundError("No module named 'celery.fixups'")

    monkeypatch.setattr(celery_app, "generate_cdlc", _missing)
    inprocess.enqueue_generate("job-1")

    with factory() as session:
        job = session.get(Job, "job-1")
        assert job.status is JobStatus.FAILED
        assert job.error == "ModuleNotFoundError: No module named 'celery.fixups'"


def test_a_detection_that_dies_before_it_starts_stops_saying_detecting(
    monkeypatch, tmp_path, sync_pool: _SyncPool
) -> None:
    """A detection is polled through its own status in params, not the job's —
    a completed project must stay completed, with the detection marked
    unavailable and the reason in the log the panel shows."""
    from rockforge.infrastructure.db.models import Job, JobStatus

    factory = _job_db(monkeypatch, tmp_path, status=JobStatus.COMPLETED,
                      params={"lyrics_status": "detecting", "lyrics_log": ["[t] queued"]})

    def _boom(job_id: str) -> None:
        raise ImportError("cannot import name 'x'")

    monkeypatch.setattr(celery_app, "detect_lyrics", _boom)
    inprocess.enqueue_detect("job-1")

    with factory() as session:
        job = session.get(Job, "job-1")
        assert job.status is JobStatus.COMPLETED
        assert job.params["lyrics_status"] == "unavailable"
        assert job.params["lyrics_log"] == [
            "[t] queued", "failed before it started: ImportError: cannot import name 'x'"]


def test_a_job_that_already_failed_keeps_its_own_error(
    monkeypatch, tmp_path, sync_pool: _SyncPool
) -> None:
    """generate_cdlc records its own failures; the safety net must not
    overwrite that more precise reason with whatever escaped afterwards."""
    from rockforge.infrastructure.db.models import Job, JobStatus

    factory = _job_db(monkeypatch, tmp_path, status=JobStatus.FAILED, error="IngestionError: x")
    monkeypatch.setattr(celery_app, "generate_cdlc",
                        lambda job_id: (_ for _ in ()).throw(RuntimeError("later")))
    inprocess.enqueue_generate("job-1")

    with factory() as session:
        assert session.get(Job, "job-1").error == "IngestionError: x"
