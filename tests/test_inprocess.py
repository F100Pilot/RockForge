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
