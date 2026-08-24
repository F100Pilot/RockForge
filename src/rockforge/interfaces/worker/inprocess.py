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


def _run_generate(job_id: str) -> None:
    try:
        from rockforge.interfaces.worker.celery_app import generate_cdlc

        generate_cdlc(job_id)
    except Exception:
        log.exception("in-process generate_cdlc failed for job %s", job_id)


def _run_detect(job_id: str) -> None:
    try:
        from rockforge.interfaces.worker.celery_app import detect_lyrics

        detect_lyrics(job_id)
    except Exception:
        log.exception("in-process detect_lyrics failed for job %s", job_id)


def enqueue_generate(job_id: str) -> None:
    _submit(_run_generate, job_id)


def enqueue_detect(job_id: str) -> None:
    _submit(_run_detect, job_id)


def _run_detect_tones(job_id: str) -> None:
    try:
        from rockforge.interfaces.worker.celery_app import detect_tones

        detect_tones(job_id)
    except Exception:
        log.exception("in-process detect_tones failed for job %s", job_id)


def enqueue_detect_tones(job_id: str) -> None:
    _submit(_run_detect_tones, job_id)


def _run_separate_stems(job_id: str) -> None:
    try:
        from rockforge.interfaces.worker.celery_app import separate_stems

        separate_stems(job_id)
    except Exception:
        log.exception("in-process separate_stems failed for job %s", job_id)


def enqueue_separate_stems(job_id: str) -> None:
    _submit(_run_separate_stems, job_id)


def shutdown() -> None:
    """Stop accepting new tasks. Wired to the API's lifespan teardown so the
    pool is closed explicitly rather than left to interpreter teardown."""
    _pool.shutdown(wait=False)
