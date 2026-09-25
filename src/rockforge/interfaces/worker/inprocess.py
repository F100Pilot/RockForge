"""In-process task runner: executes pipeline tasks in a background thread.

Used by the standalone ``.exe`` (PyInstaller) and ``start_standalone.py`` where
no Redis / Celery infrastructure is available.  The two task functions
(``generate_cdlc``, ``detect_lyrics``) are imported from ``celery_app.py`` and
called directly — they share the same DB-backed state machine, so the API polls
work identically.

Thread pool size is 1 (``--pool=solo`` parity): ML inference is not
concurrent-safe (GPU memory), and a single-user local setup gains nothing from
parallelism.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

log = logging.getLogger(__name__)

_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="rockforge-worker")

# Tasks submitted but not yet finished — RUNNING **or** still queued, since the
# pool holds one worker and a rebuild can sit behind a 20-minute separation.
# The API's idle-shutdown watchdog reads this: in ``inprocess`` mode the worker
# lives in the API's own process, so exiting on a closed tab used to abort the
# task outright and leave its job stuck at RUNNING in the database forever.
_in_flight = 0
_in_flight_lock = threading.Lock()


def work_in_flight() -> bool:
    """Whether any task is running or waiting to run in this process."""
    with _in_flight_lock:
        return _in_flight > 0


def _submit(fn: Callable[[str], None], job_id: str) -> None:
    """Count the task before queueing it, so a task that has not started yet
    still counts as in flight."""
    global _in_flight
    with _in_flight_lock:
        _in_flight += 1

    def _run() -> None:
        global _in_flight
        try:
            fn(job_id)
        finally:
            with _in_flight_lock:
                _in_flight -= 1

    _pool.submit(_run)


# Where each detection task's progress is polled from (its own status and log
# in Job.params); a build reports through the job's own status instead.
_DETECTION_KEYS = {
    "detect_lyrics": ("lyrics_status", "lyrics_log"),
    "detect_tones": ("tone_detection_status", "tone_detection_log"),
    "separate_stems": ("stems_status", "stems_log"),
}


def _record_failure(task: str, job_id: str, exc: BaseException) -> None:
    """Every task handles its own errors — once it is running. One that dies
    before that left its job PENDING forever with the reason only in a log file
    nobody opens, so the UI just sat on the first stage: the frozen build
    missing a module Celery imports by name did exactly that. Say it where the
    UI looks."""
    reason = f"{type(exc).__name__}: {exc}"
    try:
        from rockforge.config import settings
        from rockforge.infrastructure.db.models import Job, JobStatus, make_session_factory

        with make_session_factory(settings.database_url)() as session:
            job = session.get(Job, job_id)
            if job is None:
                return
            keys = _DETECTION_KEYS.get(task)
            if keys is None:
                if job.status in (JobStatus.PENDING, JobStatus.RUNNING):
                    job.status = JobStatus.FAILED
                    job.error = reason
            else:
                status_key, log_key = keys
                params = dict(job.params or {})  # a NEW dict, or the write is lost
                params[status_key] = "unavailable"
                previous = list(params.get(log_key) or [])
                params[log_key] = [*previous, f"failed before it started: {reason}"][-50:]
                job.params = params
            session.commit()
    except Exception:
        log.exception("could not record the failure of %s for job %s", task, job_id)


def _run_task(task: str, job_id: str) -> None:
    """Run one celery_app task function here, in this thread. Never raises: a
    failed run must not take the pool's only worker down with it."""
    try:
        from rockforge.interfaces.worker import celery_app

        getattr(celery_app, task)(job_id)
    except Exception as exc:
        log.exception("in-process %s failed for job %s", task, job_id)
        _record_failure(task, job_id, exc)


def enqueue_generate(job_id: str) -> None:
    _submit(lambda job: _run_task("generate_cdlc", job), job_id)


def enqueue_detect(job_id: str) -> None:
    _submit(lambda job: _run_task("detect_lyrics", job), job_id)


def enqueue_detect_tones(job_id: str) -> None:
    _submit(lambda job: _run_task("detect_tones", job), job_id)


def enqueue_separate_stems(job_id: str) -> None:
    _submit(lambda job: _run_task("separate_stems", job), job_id)


def shutdown() -> None:
    """Stop accepting new tasks. Wired to the API's lifespan teardown so the
    pool is closed explicitly rather than left to interpreter teardown."""
    _pool.shutdown(wait=False)
