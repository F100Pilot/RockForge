"""REST API: submit Guitar Pro jobs, poll status, edit sync/tones/lyrics,
download the bundle + PSARC.

This module holds what the endpoints share — ``settings``, ``_session_factory``,
the ``_enqueue*`` dispatchers, the heartbeat/idle-shutdown state, the common
helpers and the middleware — plus the two lifecycle endpoints (/heartbeat,
/closing), whose state the tests set directly. The endpoints live in groups in
``routers/``, each reading this module's names as ``api.<name>`` when a request
runs, never binding them at import: the API tests reload this module and patch
those names (``monkeypatch.setattr(app_module, …)``), and a router holding its
own reference would silently keep the original. ``tests/test_api_routers.py``
guards that. The request/response models are in ``schemas.py``, which nothing
reloads, so a model is the same class wherever it is named.
"""

from __future__ import annotations

import asyncio
import logging
import math
import os
import secrets
import signal
import sys
import time
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast
from urllib.parse import urlparse

from fastapi import Depends, FastAPI, HTTPException, Request, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from rockforge import __version__, i18n
from rockforge.config import settings as settings  # routers read it as api.settings
from rockforge.infrastructure.db.models import Job, make_session_factory
from rockforge.interfaces.api.schemas import (
    JobOut,
)

if TYPE_CHECKING:
    import xml.etree.ElementTree as ET

    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_last_heartbeat = time.monotonic()
# When the tab fires `pagehide`, the UI beacons /closing which sets a short
# deadline here. A refresh reloads and beacons /heartbeat within the grace,
# clearing it; a real close doesn't, so the watchdog exits ~CLOSE_GRACE_S later
# instead of waiting the full idle_shutdown_s. None => no pending close.
_closing_at: float | None = None
# True while the tab is backgrounded/minimised (Page Visibility). Browsers
# throttle/freeze a hidden tab's timers, so its heartbeats stop — that silence
# must NOT be read as "closed" (a real close comes through /closing). While
# hidden the idle-kill is suspended; only HEARTBEAT_MAX_S catches a dead browser.
_tab_hidden = False
CLOSE_GRACE_S = 3.0  # short enough to feel immediate, long enough to survive a refresh
# Absolute safety net: shut down only after this long with NO signal at all,
# for a browser that died without firing /closing. Generous so a merely idle or
# backgrounded (but open) tab is never killed prematurely.
HEARTBEAT_MAX_S = 1800.0  # 30 min
# A watchdog poll gap larger than this means the process was suspended (laptop
# sleep/hibernate); the frozen interval is not real idle time, so we reset the
# heartbeat clock on wake instead of counting it as "closed".
SUSPEND_JUMP_S = 5.0


def _should_shutdown(
    now: float,
    last_heartbeat: float,
    closing_at: float | None,
    tab_hidden: bool,
    idle_shutdown_s: float,
    work_in_flight: bool = False,
) -> bool:
    """Pure shutdown decision for the idle watchdog (unit-tested).

    Triggers: (1) a /closing beacon deadline passed (fast tab-close path);
    (2) the tab is visible but silent past ``idle_shutdown_s`` (its JS stopped);
    (3) no signal at all for HEARTBEAT_MAX_S (crashed browser). A backgrounded
    (hidden) tab is never killed by (2) — only a real close or a long crash.

    **Work in flight defers all three.** In ``inprocess`` mode (the standalone
    .exe) the worker runs in this very process, so exiting mid-task aborts a
    build or a 20-minute separation and leaves its job stuck at RUNNING in the
    database with nothing left to finish it. Closing the tab should let the work
    complete — the bundle lands on disk and is there on the next launch — so the
    close reason is remembered and applied the moment the queue drains. Every
    heavy stage is bounded by its own timeout, so this cannot defer forever."""
    if work_in_flight:
        return False
    gap = now - last_heartbeat
    closing = closing_at is not None and now >= closing_at
    idle = (not tab_hidden) and gap > idle_shutdown_s
    crashed = gap > HEARTBEAT_MAX_S
    return closing or idle or crashed


def _work_in_flight() -> bool:
    """Whether killing this process right now would destroy running work.

    Only true for the in-process worker. Under Celery the worker is a SEPARATE
    process that survives the API exiting, and a job left at RUNNING there is a
    stale row from a dead worker — waiting on it would hang shutdown forever.
    """
    if settings.worker_mode != "inprocess":
        return False
    from rockforge.interfaces.worker.inprocess import work_in_flight

    return work_in_flight()


async def _idle_shutdown_watchdog() -> None:
    """Exit the process when the web UI's tab closes.

    Two triggers: (1) a /closing beacon set a deadline that has passed (fast
    path on tab close, refresh-safe); (2) no /heartbeat for the full
    idle_shutdown_s (fallback for a crashed browser / lost beacon). Exiting lets
    start.bat's cleanup stop the Celery worker and any Redis it launched.
    """
    global _last_heartbeat
    _deferred_for_work = False  # log the deferral once, not every poll
    poll_s = min(0.5, settings.idle_shutdown_s / 2)  # responsive to the ~3s close grace
    last_poll = time.monotonic()
    while True:
        await asyncio.sleep(poll_s)
        now = time.monotonic()
        # A poll gap far longer than poll_s means the process was frozen (system
        # sleep). Don't count that as idle — reset the clock and let the UI
        # re-ping on wake, so waking never finds a dead server.
        if now - last_poll > SUSPEND_JUMP_S:
            _last_heartbeat = now
            last_poll = now
            continue
        last_poll = now
        busy = _work_in_flight()
        if busy and not _deferred_for_work:
            logger.info("shutdown deferred: a task is still running in this process")
            _deferred_for_work = True
        if _should_shutdown(
            now, _last_heartbeat, _closing_at, _tab_hidden, settings.idle_shutdown_s, busy
        ):
            os.kill(os.getpid(), signal.SIGTERM)
            return


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    global _last_heartbeat
    _last_heartbeat = time.monotonic()
    # Housekeeping: GP uploads from abandoned wizard sessions have nothing else
    # to collect them (the file is stored before the job exists).
    _sweep_orphan_gp_uploads()
    _sweep_orphan_youtube_audio()
    _backfill_gp_synced()
    _backfill_preset_tones()
    task: asyncio.Task[None] | None = None
    if settings.idle_shutdown_s > 0:
        task = asyncio.create_task(_idle_shutdown_watchdog())
    yield
    if task is not None:
        task.cancel()
    if settings.worker_mode == "inprocess":
        # Close the pool explicitly instead of leaving it to interpreter
        # teardown. shutdown() was written for this and had no caller.
        from rockforge.interfaces.worker.inprocess import shutdown as _worker_shutdown

        _worker_shutdown()


_basic_auth = HTTPBasic(auto_error=False)


def _verify_api_auth(
    credentials: HTTPBasicCredentials | None = Depends(_basic_auth),
) -> None:
    """Optional shared-secret gate applied to EVERY route, off by default.

    A no-op unless the operator sets ROCKFORGE_API_TOKEN — local single-user
    setups (start.bat / the standalone .exe, both bound to 127.0.0.1) are
    unaffected. HTTP Basic (not a custom header) so a plain browser gets a
    native login prompt and then auto-attaches the credentials to every
    subsequent same-origin request (including the page's own fetch() calls) —
    no frontend code change needed. The username is not checked; the shared
    token is entered as the password. Any deployment that opens a network port
    (docker-compose) MUST set this — see docker-compose.yml.
    """
    token = settings.api_token
    if not token:
        return
    if credentials is None or not secrets.compare_digest(credentials.password, token):
        raise HTTPException(
            401, "missing or invalid credentials", headers={"WWW-Authenticate": "Basic"}
        )


def _host_name(host: str) -> str:
    """The name in a Host header, without its port: ``[::1]:8000`` -> ``::1``."""
    host = host.strip().lower()
    if host.startswith("["):
        return host[1:].split("]", 1)[0]
    if host.count(":") == 1:
        host = host.split(":", 1)[0]
    return host.rstrip(".")


def _verify_host(request: Request) -> None:
    """Answer only to the names this server is meant to be reached by.

    DNS rebinding: a page on another site points its own domain at 127.0.0.1
    and fetches from it. To the browser that is same-origin, so neither CORS nor
    ``_verify_same_origin`` (which compares Origin with that very Host) can see
    it — but the Host header still carries the attacker's domain. Without this
    such a page could read every project and save settings that name a program
    the server then runs (the ML interpreter, Banquet's ``train.py``).
    """
    allowed = settings.allowed_host_names()
    if "*" in allowed:
        return
    if _host_name(request.headers.get("host", "")) not in allowed:
        raise HTTPException(400, "invalid host header")


_MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def _verify_same_origin(request: Request) -> None:
    """Reject a cross-origin mutating request — CSRF via a plain HTML <form>.

    multipart/form-data (GP/audio/cover uploads) is a browser "simple request":
    no CORS preflight is sent, so with no CORS middleware configured (there is
    none here) a malicious webpage can blind-POST a <form> straight to this API
    while the victim's browser has network access to it — no auth needed if
    ROCKFORGE_API_TOKEN is unset, and even WITH it set the browser attaches
    cached Basic-auth credentials automatically. A real browser reliably sends
    Origin (or falls back to Referer) on a cross-site POST; a request with
    neither (curl, the desktop app's own fetches, this test suite) is not a
    browser CSRF vector and passes through unaffected.
    """
    if request.method not in _MUTATING_METHODS:
        return
    origin = request.headers.get("origin") or request.headers.get("referer")
    if not origin:
        return
    if origin.strip().lower() == "null":
        # A sandboxed iframe or a file:// page sends the literal "null", whose
        # empty netloc would otherwise slip past the comparison below.
        raise HTTPException(403, "cross-origin request rejected")
    origin_host = urlparse(origin).netloc
    if origin_host and origin_host != request.headers.get("host", ""):
        raise HTTPException(403, "cross-origin request rejected")


async def _ui_language(request: Request) -> AsyncIterator[None]:
    """The language the browser reads (``X-RockForge-Lang``, sent by
    ``web/i18n.js`` on every request), for the text the server writes back —
    see ``rockforge.i18n``. Async, so it runs in the request's own context and
    the endpoint (even a sync one, run in a copied context) sees it."""
    token = i18n.use(request.headers.get("x-rockforge-lang"))
    try:
        yield
    finally:
        i18n.reset(token)


app = FastAPI(
    title="RockForge",
    description=(
        "Audio -> Rocksmith 2014 CDLC arrangement pipeline. Honest about limits: "
        "lead/rhythm split is experimental; PSARC finalization requires DLC Builder + Wwise. "
        "See docs/RELATORIO-TECNICO.md."
    ),
    version=__version__,
    lifespan=_lifespan,
    dependencies=[
        Depends(_verify_host), Depends(_verify_api_auth), Depends(_verify_same_origin),
        Depends(_ui_language),
    ],
)


# Sent on every response. nosniff: an uploaded file served back (a cover, a
# stem) is only ever read as the type we declare. frame-ancestors / DENY: no
# other site can frame the UI and trick a click into it.
_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Content-Security-Policy": "frame-ancestors 'none'",
}


@app.middleware("http")
async def _security_headers(request: Request, call_next: Any) -> Any:
    response = await call_next(request)
    for name, value in _SECURITY_HEADERS.items():
        response.headers.setdefault(name, value)
    return response


@app.exception_handler(RequestValidationError)
async def _validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
    """FastAPI's default 422, minus the non-finite floats it echoes back.

    The default handler puts the rejected input into the error body verbatim, so
    a NaN that ``Finite`` correctly refuses would then crash the serializer and
    surface as a bare 500 (see ``_json_safe``). Same status, same shape, just a
    body that can actually be encoded.
    """
    detail = _json_safe(jsonable_encoder(exc.errors()))
    return JSONResponse(status_code=422, content={"detail": detail})


_session_factory = make_session_factory(settings.database_url)


def _job_or_404(session: Session, job_id: str) -> Job:
    """The job, or the 404 every per-job endpoint answers for an unknown id."""
    job = session.get(Job, job_id)
    if job is None:
        raise HTTPException(404, "job not found")
    return job


def _json_safe(value: object) -> object:
    """Replace non-finite floats with their name, recursively.

    Starlette serializes with ``allow_nan=False``, so a response body carrying a
    NaN raises deep inside ``json.dumps``. FastAPI echoes the offending input
    back inside a validation error, which means rejecting NaN turns a clean 422
    into a 500 with no explanation — trading a silent accept for an unexplained
    crash. Scrubbing the payload keeps the 422 and names the field.
    """
    if isinstance(value, float) and not math.isfinite(value):
        return repr(value)
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


def _ml_extra_missing(what: str, exc: ImportError) -> HTTPException:
    """503 for a stage whose ML dependency is not installed.

    These endpoints used to wrap the ADAPTER IMPORT in try/except ImportError to
    raise this — dead code every time: the adapters import librosa inside their
    function bodies (deliberately, so the API process never pays for the ML
    stack), so the module import always succeeds and the real ImportError only
    surfaces on the CALL, where the generic handler turned it into
    "422 could not analyse the recording: No module named 'librosa'". Catch it
    around the call instead, ahead of that handler.
    """
    missing = getattr(exc, "name", None) or "the ml extra"
    return HTTPException(
        503, f"{what} needs the 'ml' extra ({missing}) — install rockforge[ml]"
    )


def _reject_bad_midi(field: str, pitches: list[object]) -> None:
    """Range guard for tunings restored via /import-sync, which takes a raw JSON
    blob and so never passes through the ``MidiPitch`` models."""
    bad = [p for p in pitches if not isinstance(p, int) or isinstance(p, bool) or not 0 <= p <= 127]
    if bad:
        raise HTTPException(422, f"{field}: MIDI pitch out of range (0-127): {bad}")


def _reject_non_finite(**values: float) -> None:
    """Boundary guard for floats that do NOT pass through a ``Finite`` model —
    multipart form fields and hand-written JSON restored via /import-sync."""
    bad = sorted(k for k, v in values.items() if not math.isfinite(v))
    if bad:
        raise HTTPException(422, f"must be a finite number: {', '.join(bad)}")


def _score_shift(params: dict[str, object]) -> float:
    """Where bar 1's score time lands in the bundle: ``max(offset_s, MIN_LEAD_S)
    + lead_in_s`` — the same formula as ``gp_pipeline``'s ``score_shift`` (and
    ``scoreShift`` in web/app.js). The anchor re-expression must use the build's
    value exactly, or a tempo change shifts every note by the difference."""
    from rockforge.application.gp_pipeline import MIN_LEAD_S

    offset = float(cast(float, params.get("offset_s", 0.0) or 0.0))
    lead_in = float(cast(float, params.get("lead_in_s", 0.0) or 0.0))
    return max(offset, MIN_LEAD_S) + max(0.0, lead_in)


def _sync_edited(params: dict[str, Any]) -> bool:
    """True if any sync adjustment was made — a moved offset, a scaled tempo, or
    a drift anchor (job-level or per-arrangement), or human-marked bar times
    (Songsterr) driving the timing. Drives the soft "confirmaste a
    sincronização?" completeness reminder."""
    if params.get("bar_times") or params.get("gp_synced"):
        return True
    raw_offset = params.get("offset_s")
    offset = float(raw_offset) if isinstance(raw_offset, (int, float, str)) else 0.0
    raw_scale = params.get("tempo_scale")
    scale = float(raw_scale) if isinstance(raw_scale, (int, float, str)) else 1.0
    if abs(offset) > 0.001 or abs(scale - 1.0) > 0.001:
        return True
    if any(params.get("sync_anchor_stages") or []):
        return True
    arr_sync = params.get("arrangement_sync") or {}
    if isinstance(arr_sync, dict):
        for entry in arr_sync.values():
            if not isinstance(entry, dict):
                continue
            e_scale = entry.get("tempo_scale")
            if isinstance(e_scale, (int, float)) and abs(float(e_scale) - 1.0) > 0.001:
                return True
            if any(entry.get("sync_anchor_stages") or []):
                return True
    return False


def _sync_source(params: dict[str, Any]) -> str | None:
    """Why the chart counts as in sync (see JobOut.sync_source); the user's own
    confirmation first, then what timed it, then corrections made here."""
    if params.get("sync_confirmed"):
        return "confirmed"
    if params.get("bar_times"):
        return "songsterr"
    if params.get("gp_synced"):
        return "gp"
    return "adjusted" if _sync_edited(params) else None


def _to_out(job: Job) -> JobOut:
    params = job.params or {}
    raw_offset = params.get("offset_s")
    offset_s = float(raw_offset) if isinstance(raw_offset, (int, float, str)) else 0.0
    raw_lead = params.get("lead_in_s")
    lead_in_s = float(raw_lead) if isinstance(raw_lead, (int, float, str)) else 0.0
    raw_scale = params.get("tempo_scale")
    tempo_scale = float(raw_scale) if isinstance(raw_scale, (int, float, str)) else 1.0
    has_tones = bool(
        params.get("tones") or params.get("tone_base") or params.get("tone_names")
    )
    has_lyrics = bool(
        params.get("lyrics_events")
        or params.get("lrc_text")
        or params.get("lyrics_status") == "ready"
    )
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
        lead_in_s=lead_in_s,
        tempo_scale=tempo_scale,
        import_mutes=bool((job.params or {}).get("import_mute_techniques", True)),
        dynamic_difficulty=bool((job.params or {}).get("dynamic_difficulty", True)),
        error=job.error,
        lyrics_status=str((job.params or {}).get("lyrics_status", "none")),
        tone_detection_status=str(
            (job.params or {}).get("tone_detection_status", "none")
        ),
        cover_art=bool(params.get("cover_art")),
        has_tones=has_tones,
        sync_edited=_sync_edited(params),
        sync_confirmed=bool(params.get("sync_confirmed")),
        sync_main=cast("str | None", params.get("sync_main") or None),
        sync_source=_sync_source(params),
        synced_arrangements=_synced_arrangements(params, job.bundle_dir),
        recording_from_gp=bool(params.get("recording_from_gp")),
        has_lyrics=has_lyrics,
        rebuilt_from=cast("str | None", params.get("rebuilt_from") or None),
        in_game=_in_game(job.id, params),
        in_game_path=_in_game_path(params),
    )


def _in_game_path(params: Mapping[str, object]) -> str | None:
    raw = params.get("installed_psarc")
    return raw if isinstance(raw, str) and Path(raw).is_file() else None


def _in_game(job_id: str, params: Mapping[str, object]) -> str | None:
    if _in_game_path(params) is None:
        return None
    return "this" if params.get("installed_from") == job_id else "older"


def _enqueue(job: Job) -> None:
    if settings.worker_mode == "inprocess":
        from rockforge.interfaces.worker.inprocess import enqueue_generate

        enqueue_generate(job.id)
    else:
        from rockforge.interfaces.worker.celery_app import generate_cdlc

        generate_cdlc.delay(job.id)


def _enqueue_detect(job: Job) -> None:
    if settings.worker_mode == "inprocess":
        from rockforge.interfaces.worker.inprocess import enqueue_detect

        enqueue_detect(job.id)
    else:
        from rockforge.interfaces.worker.celery_app import detect_lyrics

        detect_lyrics.delay(job.id)


def _enqueue_detect_tones(job: Job) -> None:
    if settings.worker_mode == "inprocess":
        from rockforge.interfaces.worker.inprocess import enqueue_detect_tones

        enqueue_detect_tones(job.id)
    else:
        from rockforge.interfaces.worker.celery_app import detect_tones

        detect_tones.delay(job.id)


def _enqueue_separate_stems(job: Job) -> None:
    if settings.worker_mode == "inprocess":
        from rockforge.interfaces.worker.inprocess import enqueue_separate_stems

        enqueue_separate_stems(job.id)
    else:
        from rockforge.interfaces.worker.celery_app import separate_stems

        separate_stems.delay(job.id)


GP_SUFFIXES = {".gp3", ".gp4", ".gp5", ".gp"}  # .gp = GP7/GP8 (native GPIF parser)
GP_REJECTED_SUFFIXES = {".gpx"}  # GP6 only — proprietary binary container

# Generous ceiling for any single upload (GP file, recording, cover art, LRC) —
# high enough that no legitimate file is ever rejected, low enough that an
# upload can't fill the disk. shutil.copyfileobj has no size cap of its own, so
# without this an unauthenticated caller (or one bypassing ROCKFORGE_API_TOKEN)
# could exhaust the work volume with a single request.
_MAX_UPLOAD_BYTES = 500 * 1024 * 1024
_UPLOAD_CHUNK = 1024 * 1024


def _copy_upload_capped(src: UploadFile, dest: Path) -> None:
    """Stream ``src`` into ``dest`` in chunks, aborting (and removing the
    partial file) once ``_MAX_UPLOAD_BYTES`` is exceeded. Reads the module-level
    cap fresh on every call (not a bound default) so tests can monkeypatch it."""
    total = 0
    try:
        with dest.open("wb") as fh:
            while True:
                chunk = src.file.read(_UPLOAD_CHUNK)
                if not chunk:
                    break
                total += len(chunk)
                if total > _MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        413, f"file too large (max {_MAX_UPLOAD_BYTES // (1024 * 1024)} MB)"
                    )
                fh.write(chunk)
    except HTTPException:
        dest.unlink(missing_ok=True)
        raise


# A whole song's LRC is a few KB; this only stops a runaway form field.
MAX_LYRICS_LRC_CHARS = 200_000


def _read_upload_capped(src: UploadFile) -> bytes:
    """Read ``src`` fully into memory, capped — for small text uploads (LRC)
    that are parsed in-process rather than written to disk. Reads the
    underlying file synchronously (like ``_copy_upload_capped``) rather than
    ``await``ing ``UploadFile.read`` so callers can be plain ``def`` routes,
    which FastAPI/Starlette run in a thread pool instead of on the event loop."""
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = src.file.read(_UPLOAD_CHUNK)
        if not chunk:
            break
        total += len(chunk)
        if total > _MAX_UPLOAD_BYTES:
            raise HTTPException(
                413, f"file too large (max {_MAX_UPLOAD_BYTES // (1024 * 1024)} MB)"
            )
        chunks.append(chunk)
    return b"".join(chunks)


# A GP upload nobody has turned into a job yet is legitimate (the creation
# wizard inspects the file before the job exists), so orphans are only swept
# once they are older than this. Generous on purpose: the sweep runs at startup,
# and a wizard left open across a restart must not lose its file.
GP_ORPHAN_MAX_AGE_S = 24 * 3600


def _gp_path_in_use(session: Session, gp_path: str, exclude_job_id: str | None = None) -> bool:
    """Whether any OTHER job still points at this Guitar Pro file.

    ``gp_path`` lives inside the ``params`` JSON column, and JSON-path querying
    differs between SQLite and Postgres, so the check is done in Python over the
    id/params pair rather than in SQL — this is a single-user app with a job
    list measured in tens, and portability matters more than the scan.
    """
    from sqlalchemy import select

    rows = session.execute(select(Job.id, Job.params)).all()
    return any(
        job_id != exclude_job_id and (params or {}).get("gp_path") == gp_path
        for job_id, params in rows
    )


def _sweep_orphan_gp_uploads() -> int:
    """Delete GP uploads that no job references and that are past the age limit.

    ``/gp/inspect`` stores every uploaded file server-side before the job exists,
    so abandoning the wizard (or the batch modal, which inspects one file per
    song) left the upload behind forever with nothing to ever collect it.
    Returns how many files were removed; never raises — a failed sweep must not
    stop the API from starting.
    """
    from sqlalchemy import select

    gp_dir = settings.work_dir / "gp"
    if not gp_dir.is_dir():
        return 0
    removed = 0
    try:
        cutoff = time.time() - GP_ORPHAN_MAX_AGE_S
        with _session_factory() as session:
            in_use = {
                str((params or {}).get("gp_path"))
                for (params,) in session.execute(select(Job.params)).all()
            }
        for f in gp_dir.iterdir():
            if not f.is_file() or str(f) in in_use:
                continue
            try:
                if f.stat().st_mtime < cutoff:
                    f.unlink()
                    removed += 1
            except OSError:  # vanished under us, or not ours to delete
                continue
    except Exception:  # noqa: BLE001 — housekeeping must never block startup
        logger.warning("orphan GP sweep failed", exc_info=True)
    if removed:
        logger.info("removed %d orphaned GP upload(s) from %s", removed, gp_dir)
    return removed


def _backfill_gp_synced() -> int:
    """Mark the GP jobs built before ``gp_synced`` existed that carry their own
    Guitar Pro 8 sync points, so a project the user synced in Guitar Pro stops
    being asked "confirmaste a sincronização?" without having to be rebuilt.
    Once per job (the key, even False, stops it being read again); returns how
    many were marked; never raises — housekeeping must not block startup."""
    from sqlalchemy import select

    from rockforge.infrastructure.gpimport.gpif_parser import sync_start_s

    marked = 0
    try:
        with _session_factory() as session:
            known: dict[str, bool] = {}
            for job in session.execute(select(Job)).scalars():
                params = dict(job.params or {})
                gp_path = params.get("gp_path")
                if (job.source_type != "gp" or "gp_synced" in params
                        or not isinstance(gp_path, str) or not gp_path):
                    continue
                if gp_path not in known:
                    try:
                        known[gp_path] = sync_start_s(Path(gp_path)) is not None
                    except Exception:  # noqa: BLE001 — a missing/odd file is just "no"
                        known[gp_path] = False
                job.params = {**params, "gp_synced": known[gp_path]}
                marked += known[gp_path]
            session.commit()
    except Exception:  # noqa: BLE001 — housekeeping must never block startup
        logger.warning("gp_synced backfill failed", exc_info=True)
    return marked


def _refresh_presets(tones: object) -> list[dict[str, Any]] | None:
    """``tones`` with every curated preset brought up to date where the user
    left it as it shipped, or None when nothing needed it: a volume still at
    a value the preset shipped with before moves to the current one, a pre-pedal chain
    still the preset's own gets the noise gate the preset now opens with
    (``tone_presets.with_preset_gate``), and a whole chain — amp, cabinet,
    pedals, racks — still exactly an earlier version of its preset gets the
    current one (``upgrade_preset_chain``).
    What the user changed is theirs."""
    from rockforge.infrastructure.packaging.gear.tone_presets import (
        PRESET_VOLUMES_BEFORE,
        preset_volume,
        upgrade_preset_chain,
        with_preset_gate,
    )

    if not isinstance(tones, list):
        return None
    out: list[dict[str, Any]] = []
    changed = False
    for tone in tones:
        if isinstance(tone, dict):
            key = str(tone.get("key", ""))
            before, new = PRESET_VOLUMES_BEFORE.get(key, ()), preset_volume(key)
            vol = tone.get("volume")
            if new is not None and isinstance(vol, (int, float)) \
                    and any(abs(float(vol) - old) < 1e-9 for old in before):
                tone = {**tone, "volume": new}
                changed = True
            upgraded = upgrade_preset_chain(tone) or with_preset_gate(tone)
            if upgraded is not None:
                tone = upgraded
                changed = True
        out.append(tone)
    return out if changed else None


def _backfill_preset_tones() -> int:
    """Projects and the tone library carrying a curated preset as it first
    shipped get what the preset has learnt since (``_refresh_presets``: the
    volume, too quiet in game, and the noise gate against the hiss), so the
    next rebuild has it without re-applying the suggestion. Returns how many
    projects changed; never raises — housekeeping must not block startup."""
    from sqlalchemy import select

    from rockforge import tone_library

    changed = 0
    try:
        with _session_factory() as session:
            for job in session.execute(select(Job)).scalars():
                params = dict(job.params or {})
                tones = _refresh_presets(params.get("tones"))
                if tones is not None:
                    job.params = {**params, "tones": tones}
                    changed += 1
            session.commit()
        library = _refresh_presets(tone_library.load())
        for tone in library or []:
            tone_library.save_tone(tone)
    except Exception:  # noqa: BLE001 — housekeeping must never block startup
        logger.warning("preset tone backfill failed", exc_info=True)
    return changed


def _sweep_orphan_youtube_audio() -> int:
    """Delete fetched YouTube audio (``uploads/yt-*``) no job uses, past the age
    limit — ``/youtube/audio`` runs in the wizard, before the job exists, so an
    abandoned wizard leaves the file behind (same reasoning as the GP sweep).
    Never raises."""
    from sqlalchemy import select

    from rockforge.infrastructure.youtube_audio import FILE_PREFIX

    up_dir = settings.work_dir / "uploads"
    if not up_dir.is_dir():
        return 0
    removed = 0
    try:
        cutoff = time.time() - GP_ORPHAN_MAX_AGE_S
        with _session_factory() as session:
            in_use = {str(src) for (src,) in session.execute(select(Job.source)).all()}
        for f in up_dir.glob(f"{FILE_PREFIX}*"):
            if not f.is_file() or str(f) in in_use:
                continue
            try:
                if f.stat().st_mtime < cutoff:
                    f.unlink()
                    removed += 1
            except OSError:
                continue
    except Exception:  # noqa: BLE001 — housekeeping must never block startup
        logger.warning("orphan YouTube audio sweep failed", exc_info=True)
    return removed


# The manually-tuned "sync state": every param a user builds by hand in the tab
# viewer (drift anchors, tempo, offset, intro silence, per-arrangement overrides,
# tuning, edited lyrics, GP track assignment). Exported/imported as one JSON blob
# so those edits survive re-creating a job (a fresh upload or a re-exported GP)
# instead of being redone from scratch.
_SYNC_STATE_KEYS: tuple[str, ...] = (
    "offset_s", "lead_in_s", "tempo_scale",
    "sync_anchor_stages", "arrangement_sync",
    "cent_offset", "tuning_overrides",
    "lyrics_events",
    "lead_track", "rhythm_track", "combo_track", "alt_lead_track", "alt_rhythm_track",
    "bass_track",
)

def _extract_sync_state(params: dict[str, object]) -> dict[str, object]:
    """The whitelisted sync-relevant subset of a job's params (only keys present)."""
    return {k: params[k] for k in _SYNC_STATE_KEYS if k in params}


def _arrangement_kinds() -> list[Any]:
    from rockforge.domain.arrangement import ArrangementKind

    return list(ArrangementKind)


def _build_order(kind: str) -> int:
    """Where a chart comes in the build's slot order (Lead, Rhythm, Combined,
    alternates…) — the order the viewer lists them in; unknown kinds last."""
    order = [k.value for k in _arrangement_kinds()]
    return order.index(kind) if kind in order else len(order)


def _synced_arrangements(params: dict[str, Any], bundle_dir: str | None) -> list[str]:
    """The charts marked as in sync. A song confirmed as a whole before charts
    could be marked one by one counts every chart it built."""
    raw = params.get("synced_arrangements")
    if isinstance(raw, list):
        return [str(k) for k in raw]
    return _built_kinds(bundle_dir) if params.get("sync_confirmed") else []


def _built_kinds(bundle_dir: str | None) -> list[str]:
    """The arrangements a build produced, by their XML file names."""
    if not bundle_dir:
        return []
    names = {k.name: k.value for k in _arrangement_kinds()}
    stems = (
        p.stem.removeprefix("arrangement_").upper()
        for p in Path(bundle_dir).glob("arrangement_*.xml")
    )
    return [names[s] for s in stems if s in names]


def _built_arrangement_kind(xml_path: Path, root: ET.Element) -> str:
    """Which arrangement a built XML is, from its file name (the packager writes
    ``arrangement_<kind name>.xml``). NOT from its ``<arrangement>`` tag: an
    alternate chart writes its BASE path there ("Lead"/"Rhythm", as the game
    needs), so reading the tag gave two tabs called "Lead" that shared every
    per-arrangement edit — sync corrections, tempo, note edits."""
    from rockforge.domain.arrangement import ArrangementKind

    name = xml_path.stem.removeprefix("arrangement_").upper()
    try:
        return ArrangementKind[name].value
    except KeyError:
        return root.findtext("arrangement", "?")


_COVER_ART_SUFFIXES = {".jpg", ".jpeg", ".png"}


def _replace_cover(job: Job, suffix: str) -> Path:
    """Where the job's cover goes, with any previous cover (of any extension)
    removed so only one is ever picked up by the build."""
    job_dir: Path = settings.work_dir / str(job.id)
    job_dir.mkdir(parents=True, exist_ok=True)
    for old in _COVER_ART_SUFFIXES:
        (job_dir / f"cover{old}").unlink(missing_ok=True)
    return job_dir / f"cover{suffix}"


def _record_cover(job: Job, dest: Path) -> None:
    params = dict(job.params or {})  # a NEW dict, or the JSON column is not written
    params["cover_art"] = dest.name
    job.params = params


def _gear_image_dirs() -> list[Path]:
    """Folders searched (in order) for a gear image, first hit wins.

    ``work_dir/gear_images`` is the RUNTIME override — the user drops their own
    amp/cab/pedal pictures there (named by the gear key) without committing.
    The bundled ``web/gear_images`` (resolved the same way ``index()`` finds the
    web UI) ships RockForge's own gear art in the repo, so a fresh install has
    pictures out of the box even before the user adds any."""
    dirs = [settings.work_dir / "gear_images"]
    for base in _web_file_candidates("gear_images"):
        if base not in dirs:
            dirs.append(base)
    return dirs


@app.post("/heartbeat", include_in_schema=False)
def heartbeat(hidden: bool = False) -> dict[str, bool]:
    """Pinged periodically by the web UI; see Settings.idle_shutdown_s.

    ``hidden=1`` (sent on Page Visibility change / from a backgrounded tab)
    marks the tab as still-open-but-backgrounded, which suspends the idle-kill
    so a throttled tab isn't mistaken for a closed one. Any heartbeat also
    cancels a pending /closing — one arriving after `pagehide` means the page
    came back (a refresh), not a real close."""
    global _last_heartbeat, _closing_at, _tab_hidden
    _last_heartbeat = time.monotonic()
    _tab_hidden = hidden
    # Only a VISIBLE heartbeat cancels a pending close (the page genuinely came
    # back — a refresh). A hidden beacon ALSO fires on tab close
    # (visibilitychange→hidden precedes pagehide), and the two beacons race on
    # the server; if a hidden heartbeat cleared _closing_at it could cancel the
    # /closing the same close just armed, and the tab would never shut down.
    if not hidden:
        _closing_at = None
    return {"ok": True}


@app.post("/closing", include_in_schema=False)
def closing() -> dict[str, bool]:
    """Beaconed by the web UI on `pagehide` (tab close/navigate). Arms a short
    shutdown grace; a following /heartbeat (refresh) cancels it. No-op when
    idle-shutdown is disabled."""
    global _closing_at
    if settings.idle_shutdown_s > 0:
        _closing_at = time.monotonic() + CLOSE_GRACE_S
    return {"ok": True}


def _web_dirs() -> tuple[Path, ...]:
    """The places a bundled ``web/`` folder can live, first hit wins.

    ``sys._MEIPASS`` is the PyInstaller bundle's extraction directory and MUST
    come first: inside the standalone .exe neither of the other two resolves
    (``__file__`` points into the frozen archive and the launcher never chdirs),
    so without it every bundled web file 404s — index.html falls back to the
    "UI not bundled" stub and /app.js is simply missing, leaving a dead page.
    """
    meipass = getattr(sys, "_MEIPASS", None)
    dirs = [Path(meipass) / "web"] if meipass else []
    dirs += [
        # repo checkout: src/rockforge/interfaces/api/app.py -> repo root
        Path(__file__).resolve().parents[3].parent / "web",
        # pip-installed (e.g. Docker WORKDIR /app with COPY web ./web)
        Path.cwd() / "web",
    ]
    return tuple(dirs)


def _web_file_candidates(name: str) -> tuple[Path, ...]:
    """The places a bundled `web/` file can live, first hit wins — the same
    resolution `_gear_image_dirs()` uses for gear images."""
    return tuple(d / name for d in _web_dirs())


# ── Endpoint groups ──────────────────────────────────────────────────────────
# Imported last: each router reads this module's names as api.<name> when a
# request runs, and this is where those names exist. The order is the order
# they had in this file; no two groups answer the same URL.
from rockforge.interfaces.api.routers import (  # noqa: E402
    analysis,
    charts,
    delivery,
    gp_export,
    imports,
    jobs,
    lyrics,
    stems,
    sync,
    tones,
    web,
)

# Aliased: app.py's own `settings` is the configuration.
from rockforge.interfaces.api.routers import settings as settings_routes  # noqa: E402

for _group in (
    imports, jobs, sync, gp_export, analysis, lyrics, tones, stems,
    settings_routes, charts, delivery, web,
):
    app.include_router(_group.router)
