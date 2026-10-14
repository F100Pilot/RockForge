"""REST API: submit Guitar Pro jobs, poll status, edit sync/tones/lyrics,
download the bundle + PSARC.

This module holds what the endpoints share — ``settings``, ``_session_factory``,
the ``_enqueue*`` dispatchers, the heartbeat/idle-shutdown state and the common
helpers — plus the endpoints not yet moved out. Groups of endpoints live in
``routers/``, each reading this module's names as ``api.<name>`` when a request
runs, never binding them at import: the API tests reload this module and patch
those names (``monkeypatch.setattr(app_module, …)``), and a router holding its
own reference would silently keep the original. ``tests/test_api_routers.py``
guards that. The request/response models are in ``schemas.py``, which nothing
reloads, so a model is the same class wherever it is named.
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import os
import re
import secrets
import shutil
import signal
import sys
import time
import uuid
from collections.abc import AsyncIterator, Iterator, Mapping
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast
from urllib.parse import urlparse

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from rockforge import __version__, i18n
from rockforge.config import settings as settings  # routers read it as api.settings
from rockforge.infrastructure.db.models import Job, JobStatus, make_session_factory
from rockforge.interfaces.api.schemas import (
    MAX_CENT_OFFSET,
    JobOut,
    MetadataIn,
    RebuildIn,
    SyncConfirmedIn,
    SyncMainIn,
    SyncStateIn,
    SyncStateOut,
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


# A song has a few hundred bars at most; the ceiling only stops an absurd
# payload from being persisted into params.
_MAX_BAR_TIMES = 10_000


def _parse_bar_times(raw: str) -> list[float]:
    """``bar_times`` arrives as a JSON list inside a multipart form, so it
    bypasses the models — validate it here like the other form floats."""
    if not raw.strip():
        return []
    try:
        values = json.loads(raw)
    except ValueError as exc:
        raise HTTPException(422, "bar_times must be a JSON list of seconds") from exc
    if not isinstance(values, list) or not all(
        isinstance(v, int | float) and not isinstance(v, bool) for v in values
    ):
        raise HTTPException(422, "bar_times must be a JSON list of seconds")
    if len(values) > _MAX_BAR_TIMES:
        raise HTTPException(422, f"bar_times has more than {_MAX_BAR_TIMES} entries")
    floats = [float(v) for v in values]
    if not all(math.isfinite(v) and v >= 0 for v in floats):
        raise HTTPException(422, "bar_times must be finite, non-negative seconds")
    return floats


MAX_ESTIMATED_BARS_CHARS = 200_000
_MAX_TRACKS = 64


def _parse_estimated_bars(raw: str) -> dict[str, list[int]]:
    """``estimated_bars`` (/pdf/import's, handed back by the wizard) as a JSON object
    of track index → bar numbers; checked here like ``bar_times``. Stored with the
    track index as a string key, the way JSON keeps it in ``params``."""
    if not raw.strip():
        return {}
    message = "estimated_bars must map track indexes to lists of bar numbers"
    try:
        values = json.loads(raw)
    except ValueError as exc:
        raise HTTPException(422, message) from exc
    if not isinstance(values, dict) or len(values) > _MAX_TRACKS:
        raise HTTPException(422, message)
    out: dict[str, list[int]] = {}
    for key, bars in values.items():
        if not (isinstance(key, str) and key.isdigit() and int(key) < _MAX_TRACKS):
            raise HTTPException(422, message)
        if not isinstance(bars, list) or len(bars) > _MAX_BAR_TIMES or not all(
            isinstance(b, int) and not isinstance(b, bool) and 1 <= b <= _MAX_BAR_TIMES
            for b in bars
        ):
            raise HTTPException(422, message)
        if bars:
            out[str(int(key))] = sorted(set(bars))
    return out


@app.post("/jobs/gp", response_model=JobOut, status_code=202)
def create_gp_job(
    gp_token: str = Form(...),
    audio: UploadFile | None = File(None),
    # Use the recording the GP8 file carries instead of an upload — the audio
    # its sync points were made against (see gpif_parser.embedded_audio).
    use_embedded_audio: bool = Form(False),
    # The audio of the chosen YouTube video, already fetched by /youtube/audio.
    audio_token: str = Form(""),
    # Where each bar starts in the recording (JSON list of seconds), e.g. the
    # Songsterr timestamps /songsterr returned for the video the user picked.
    bar_times: str = Form(""),
    bar_times_source: str = Form(""),
    lead_track: str = Form(""),
    rhythm_track: str = Form(""),
    combo_track: str = Form(""),
    alt_lead_track: str = Form(""),
    alt_rhythm_track: str = Form(""),
    offset_s: float = Form(0.0),
    lead_in_s: float = Form(0.0),
    tempo_scale: float = Form(1.0),
    tone_base: str = Form(""),
    tone_names: str = Form(""),  # comma-separated, max 4
    import_mutes: bool = Form(True),
    lrc: UploadFile | None = File(None),
    # Synced lyrics the wizard found on LRCLIB (/lyrics-lookup) and the user
    # kept — the same LRC text an uploaded file carries; an upload still wins.
    lyrics_lrc: str = Form("", max_length=MAX_LYRICS_LRC_CHARS),
    title: str = Form(""),
    artist: str = Form(""),
    album: str = Form(""),
    year: str = Form(""),
    # A cover the user chose from /album-lookup, downloaded before the job is
    # queued so the very first build carries it.
    cover_url: str = Form(""),
    # /pdf/import's estimated_bars (JSON), kept for the viewer's review links.
    estimated_bars: str = Form("", max_length=MAX_ESTIMATED_BARS_CHARS),
) -> JobOut:
    """Create a CDLC job from a previously inspected GP file + the recording."""
    gp_path = settings.work_dir / "gp" / Path(gp_token).name
    if not gp_path.exists():
        raise HTTPException(404, "gp_token not found — upload the GP file via /gp/inspect first")

    from rockforge.domain.errors import IngestionError

    upload_dir = settings.work_dir / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    if use_embedded_audio:
        from rockforge.infrastructure.gpimport.gpif_parser import extract_embedded_audio

        try:
            audio_dest = extract_embedded_audio(gp_path, upload_dir / str(uuid.uuid4()))
        except IngestionError as exc:
            raise HTTPException(422, str(exc)) from exc
    elif audio_token.strip():
        from rockforge.infrastructure.youtube_audio import FILE_PREFIX

        # Only a bare name this server wrote (yt-…) under uploads/ — never a path.
        name = Path(audio_token.strip()).name
        audio_dest = upload_dir / name
        if not name.startswith(FILE_PREFIX) or not audio_dest.is_file():
            raise HTTPException(404, "audio_token not found — fetch the audio via /youtube/audio")
    else:
        if audio is None or not audio.filename:
            raise HTTPException(
                422, "a recording is required (or use_embedded_audio for a GP8 file that has one)"
            )
        suffix = Path(audio.filename).suffix.lower()
        from rockforge.infrastructure.ingestion.sources import ALLOWED_SUFFIXES

        if suffix not in ALLOWED_SUFFIXES:
            raise HTTPException(415, f"unsupported audio format: {suffix or '(none)'}")
        audio_dest = upload_dir / f"{uuid.uuid4()}{suffix}"
        _copy_upload_capped(audio, audio_dest)

    from rockforge.infrastructure.gpimport.parser import inspect_gp
    from rockforge.infrastructure.ingestion.tags import read_tags

    try:
        info = inspect_gp(gp_path)
    except IngestionError as exc:
        raise HTTPException(422, str(exc)) from exc
    tags = read_tags(audio_dest)

    final_title = title.strip() or info.title or tags.title
    final_artist = artist.strip() or info.artist or tags.artist
    final_album = album.strip() or info.album or tags.album or ""
    final_year: int | None = int(year) if year.strip().isdigit() else tags.year
    missing = [n for n, v in (("title", final_title), ("artist", final_artist)) if not v]
    if missing:
        audio_dest.unlink(missing_ok=True)
        raise HTTPException(
            422,
            f"neither the GP file, the audio tags nor the form provide: {missing}",
        )
    assert final_title is not None and final_artist is not None

    tones = [t.strip() for t in tone_names.split(",") if t.strip()]
    if len(tones) > 4:
        raise HTTPException(422, "Rocksmith supports at most 4 switchable tones")

    lrc_text: str | None = None
    if lrc is not None and lrc.filename:
        lrc_text = _read_upload_capped(lrc).decode("utf-8", errors="replace")
    elif lyrics_lrc.strip():
        from rockforge.infrastructure.rsxml.vocals import parse_lyrics

        # Refused here, not at build time: an unreadable text would only
        # surface later as a build that silently has no lyrics.
        if not parse_lyrics(lyrics_lrc):
            raise HTTPException(422, i18n.tr(
                "a letra escolhida não tem tempos que se possam ler (LRC)",
                "the chosen lyrics have no timestamps that can be read (LRC)",
            ))
        lrc_text = lyrics_lrc

    # Multipart form floats bypass the ``Finite`` models above (they arrive as
    # strings and coerce), and NaN would slip past the ``<= 0`` guard below
    # because ``NaN <= 0`` is False.
    _reject_non_finite(offset_s=offset_s, lead_in_s=lead_in_s, tempo_scale=tempo_scale)
    if tempo_scale <= 0:
        raise HTTPException(422, "tempo_scale must be > 0")
    if lead_in_s < 0.0:
        raise HTTPException(422, "lead_in_s must be >= 0")

    parsed_bar_times = _parse_bar_times(bar_times)
    parsed_estimated_bars = _parse_estimated_bars(estimated_bars)
    cover_url = cover_url.strip()
    if cover_url:
        from rockforge.infrastructure.album_lookup import cover_url_allowed

        if not cover_url_allowed(cover_url):
            raise HTTPException(422, "cover_url is not from a known cover service")

    params: dict[str, object] = {
        "gp_path": str(gp_path),
        "bar_times": parsed_bar_times,
        "bar_times_source": bar_times_source.strip()[:200] if parsed_bar_times else "",
        "offset_s": offset_s,
        "lead_in_s": lead_in_s,
        "tempo_scale": tempo_scale,
        "tone_base": tone_base.strip() or None,
        "tone_names": tones,
        "lrc_text": lrc_text,
        "import_mute_techniques": import_mutes,
        "recording_from_gp": use_embedded_audio,
    }
    if parsed_estimated_bars:
        params["estimated_bars"] = parsed_estimated_bars
    if lead_track.strip().isdigit():
        params["lead_track"] = int(lead_track)
    if rhythm_track.strip().isdigit():
        params["rhythm_track"] = int(rhythm_track)
    if combo_track.strip().isdigit():
        params["combo_track"] = int(combo_track)
    if alt_lead_track.strip().isdigit():
        params["alt_lead_track"] = int(alt_lead_track)
    if alt_rhythm_track.strip().isdigit():
        params["alt_rhythm_track"] = int(alt_rhythm_track)

    with _session_factory() as session:
        job = Job(
            source=str(audio_dest),
            source_type="gp",
            title=final_title,
            artist=final_artist,
            album=final_album,
            year=final_year,
            params=params,
        )
        session.add(job)
        session.commit()
        if cover_url:
            # Best effort: a cover that will not download must not cost the
            # user the project. The response's empty cover_art says so, and the
            # UI tells them to pick another on the Capa page.
            from rockforge.infrastructure.album_lookup import AlbumLookupError, fetch_cover

            try:
                data, suffix = fetch_cover(cover_url)
            except AlbumLookupError:
                pass
            else:
                dest = _replace_cover(job, suffix)
                dest.write_bytes(data)
                _record_cover(job, dest)
                session.commit()
        _enqueue(job)
        return _to_out(job)


@app.post("/jobs/{job_id}/reload-gp", response_model=JobOut, status_code=202)
def reload_gp(
    job_id: str,
    gp: UploadFile = File(...),
    use_embedded_audio: bool = Form(True),
) -> JobOut:
    """Replace the Guitar Pro file of an existing GP job and rebuild, keeping
    every override the job already carries (tuning, sync anchors, tempo, tones,
    lyrics, cover). For when you tweak a note in Guitar Pro and re-export — no
    need to recreate the job and redo all the alignment work.

    Like /rebuild it forks a NEW job (fresh work dir) so the previous build is
    preserved. The recording is reused unchanged — unless the new file carries
    its own audio and ``use_embedded_audio`` (the default) says to use it, as
    the wizard does: that copy is the one the file's sync points describe. A
    file with audio also stands in for a recording that no longer exists."""
    suffix = Path(gp.filename or "").suffix.lower()
    if suffix in GP_REJECTED_SUFFIXES:
        raise HTTPException(
            415,
            "GP6 (.gpx) is not supported (proprietary binary container). "
            "Export as GP5 or GP7 (.gp) from Guitar Pro or TuxGuitar and upload again.",
        )
    if suffix not in GP_SUFFIXES:
        raise HTTPException(415, f"unsupported Guitar Pro format: {suffix or '(none)'}")

    from rockforge.domain.errors import IngestionError
    from rockforge.infrastructure.gpimport.parser import inspect_gp

    with _session_factory() as session:
        original = _job_or_404(session, job_id)
        if original.source_type != "gp":
            raise HTTPException(422, "reload-gp only applies to Guitar Pro jobs")
        params: dict[str, object] = dict(original.params or {})
        src_recording = original.source
        meta = (original.title, original.artist, original.album, original.year)

        gp_dir = settings.work_dir / "gp"
        gp_dir.mkdir(parents=True, exist_ok=True)
        gp_dest = gp_dir / f"{uuid.uuid4()}{suffix}"
        _copy_upload_capped(gp, gp_dest)

        try:
            info = inspect_gp(gp_dest)
        except IngestionError as exc:
            gp_dest.unlink(missing_ok=True)
            raise HTTPException(422, str(exc)) from exc

        # The stored track selection must still be valid: a plain note edit keeps
        # the track layout, but a restructured file may not — fail loudly rather
        # than silently building the wrong track.
        valid = {t.index for t in info.tracks}
        for key in ("lead_track", "rhythm_track", "combo_track",
                    "alt_lead_track", "alt_rhythm_track"):
            idx = params.get(key)
            if isinstance(idx, int) and idx not in valid:
                gp_dest.unlink(missing_ok=True)
                raise HTTPException(
                    422,
                    f"the new GP file has no track at the previously selected {key} "
                    f"(index {idx}) — the track layout changed. Create a new job via "
                    "'Inspecionar pistas' instead.",
                )

        from rockforge.infrastructure.gpimport.gpif_parser import (
            embedded_audio,
            extract_embedded_audio,
            sync_start_s,
        )

        recording_gone = not Path(src_recording).exists()
        if embedded_audio(gp_dest) is not None and (use_embedded_audio or recording_gone):
            upload_dir = settings.work_dir / "uploads"
            try:
                src_recording = str(extract_embedded_audio(gp_dest, upload_dir / str(uuid.uuid4())))
            except IngestionError as exc:
                gp_dest.unlink(missing_ok=True)
                raise HTTPException(422, str(exc)) from exc
            if not params.get("recording_from_gp"):
                # Another recording's start does not fit this one; where bar 1
                # sits in the file's own audio is what the wizard would offer.
                start = sync_start_s(gp_dest)
                if start is not None:
                    params["offset_s"] = round(start, 3)
            params["recording_from_gp"] = True
        elif recording_gone:
            gp_dest.unlink(missing_ok=True)
            raise HTTPException(409, "original recording no longer exists on the work volume")

        params["gp_path"] = str(gp_dest)
        # The converter's estimated bars described the old file, not this one.
        params.pop("estimated_bars", None)
        params["rebuilt_from"] = original.id
        title, artist, album, year = meta
        job = Job(
            source=src_recording,
            source_type="gp",
            title=title,
            artist=artist,
            album=album,
            year=year,
            params=params,
        )
        session.add(job)
        session.commit()

        # Carry the album art across to the forked job's work dir (same as
        # /rebuild) so a reload never loses the cover.
        cover_art_name = params.get("cover_art")
        if cover_art_name:
            src = settings.work_dir / job_id / cast(str, cover_art_name)
            if src.exists():
                dest_dir = settings.work_dir / job.id
                dest_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest_dir / cast(str, cover_art_name))

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


@app.delete("/jobs/{job_id}", status_code=204)
def delete_job(job_id: str, force: bool = False) -> Response:
    """Delete a job and its work artifacts. Running jobs must finish first,
    unless ``force=true`` — the escape hatch for a job stuck in RUNNING because
    its worker died or hung (otherwise it could never be deleted).

    The uploaded source file is removed only when no other job (e.g. a rebuild)
    still references it."""
    with _session_factory() as session:
        job = _job_or_404(session, job_id)
        if job.status is JobStatus.RUNNING and not force:
            raise HTTPException(409, "job is running — wait for it to finish before deleting")
        _delete_job_files_and_row(session, job)
        session.commit()
    return Response(status_code=204)


def _delete_job_files_and_row(session: Any, job: Job) -> None:
    """Remove a job's work dir, its recording and GP file when no other job
    uses them, and its row (the caller commits)."""
    from sqlalchemy import func, select

    shutil.rmtree(settings.work_dir / job.id, ignore_errors=True)

    others = session.scalar(
        select(func.count()).select_from(Job).where(Job.source == job.source, Job.id != job.id)
    )
    if not others and job.source_type in {"upload", "gp"}:
        Path(job.source).unlink(missing_ok=True)

    # The uploaded Guitar Pro file too — it lives outside the job's work dir
    # (work_dir/gp/<uuid>.gp*) and was previously left behind forever, so a
    # deleted job still cost its GP file on disk. Reference-counted like the
    # recording above, because a rebuild/reload-gp fork shares the path.
    gp_path = (job.params or {}).get("gp_path")
    if isinstance(gp_path, str) and gp_path and not _gp_path_in_use(session, gp_path, job.id):
        Path(gp_path).unlink(missing_ok=True)

    session.delete(job)


# Work-dir subfolders a later version keeps using: params["stems"] is inherited
# by every rebuild with absolute paths into the version that ran the
# separation, and detect_tones/separate_stems reuse the guitar stem cached there.
_CARRIED_WORK_DIRS = ("demucs_stems", "stem_separation")


@app.post("/jobs/{job_id}/drop-previous", response_model=JobOut)
def drop_previous_version(job_id: str) -> JobOut:
    """Delete the version this one was rebuilt from ("Aplicar e reconstruir"
    asks whether to). Only once THIS version is built — a failed rebuild keeps
    the old one. What the new version still uses from the old one is moved
    over first (the separated stems), and any other version rebuilt from the
    old one then points at the version before it."""
    from sqlalchemy import select

    with _session_factory() as session:
        job = _job_or_404(session, job_id)
        if job.status is not JobStatus.COMPLETED:
            raise HTTPException(409, "the new version has to finish building first")
        params = dict(job.params or {})
        prev_id = params.get("rebuilt_from")
        prev = session.get(Job, prev_id) if isinstance(prev_id, str) and prev_id else None
        if prev is None:
            raise HTTPException(404, "this version has no previous version to delete")
        if prev.status is JobStatus.RUNNING:
            raise HTTPException(409, "the previous version is still building")

        old_dir, new_dir = settings.work_dir / prev.id, settings.work_dir / job.id
        for sub in _CARRIED_WORK_DIRS:
            if (old_dir / sub).is_dir() and not (new_dir / sub).exists():
                new_dir.mkdir(parents=True, exist_ok=True)
                shutil.move(str(old_dir / sub), str(new_dir / sub))
        stems = params.get("stems")
        if isinstance(stems, dict):
            params["stems"] = {
                name: str(new_dir / Path(path).relative_to(old_dir))
                if isinstance(path, str) and Path(path).is_relative_to(old_dir) else path
                for name, path in stems.items()
            }

        rebuilt_from = cast("dict[str, Any]", prev.params or {}).get("rebuilt_from")
        grand: str | None = None
        if isinstance(rebuilt_from, str) and session.get(Job, rebuilt_from) is not None:
            grand = rebuilt_from
        for other in session.execute(select(Job).where(Job.id != prev.id)).scalars():
            other_params = params if other.id == job.id else dict(other.params or {})
            if other_params.get("rebuilt_from") != prev.id:
                continue
            if grand:
                other_params["rebuilt_from"] = grand
            else:
                other_params.pop("rebuilt_from", None)
            if other.id != job.id:
                other.params = other_params
        job.params = {**params}
        _delete_job_files_and_row(session, prev)
        session.commit()
        return _to_out(job)


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
)
# Keys that only make sense for a Guitar Pro job (dropped when importing into a
# non-GP job, mirroring rebuild's per-field 422s).
_SYNC_STATE_GP_ONLY: frozenset[str] = frozenset({
    "tuning_overrides",
    "lead_track", "rhythm_track", "combo_track", "alt_lead_track", "alt_rhythm_track",
})


def _extract_sync_state(params: dict[str, object]) -> dict[str, object]:
    """The whitelisted sync-relevant subset of a job's params (only keys present)."""
    return {k: params[k] for k in _SYNC_STATE_KEYS if k in params}


def _sanitize_sync_state(incoming: dict[str, object]) -> dict[str, object]:
    """Keep only whitelisted keys and validate the shapes that would 422 on a
    rebuild, so a hand-edited or foreign JSON can never corrupt a job."""
    out = {k: incoming[k] for k in _SYNC_STATE_KEYS if k in incoming}
    cents = out.get("cent_offset")
    if cents is not None and (
        not isinstance(cents, (int, float)) or isinstance(cents, bool)
        or not abs(cents) <= MAX_CENT_OFFSET
    ):
        bound = f"{MAX_CENT_OFFSET:g}"
        raise HTTPException(422, f"cent_offset must be a number between -{bound} and {bound}")
    to = out.get("tuning_overrides")
    if to is not None:
        if not isinstance(to, dict):
            raise HTTPException(422, "tuning_overrides must be an object keyed by arrangement")
        for kind, midi in to.items():
            if not isinstance(midi, list) or len(midi) != 6:
                raise HTTPException(422, f"tuning for {kind} must have 6 MIDI pitches")
            _reject_bad_midi(f"tuning for {kind}", midi)
    # This path takes a raw JSON blob, so none of the ``Finite`` models apply:
    # a hand-edited or foreign file could otherwise restore a NaN offset/tempo
    # or a NaN drift anchor straight into the job's params.
    _reject_non_finite(
        **{
            k: float(v)
            for k in ("offset_s", "lead_in_s", "tempo_scale", "cent_offset")
            if isinstance(v := out.get(k), (int, float))
        }
    )
    for key in ("sync_anchor_stages", "arrangement_sync"):
        for value in _iter_floats(out.get(key)):
            if not math.isfinite(value):
                raise HTTPException(422, f"{key} contains a non-finite time")
    return out


def _iter_floats(value: object) -> Iterator[float]:
    """Every number nested anywhere inside a decoded-JSON structure."""
    if isinstance(value, bool):
        return
    if isinstance(value, (int, float)):
        yield float(value)
    elif isinstance(value, dict):
        for v in value.values():
            yield from _iter_floats(v)
    elif isinstance(value, (list, tuple)):
        for v in value:
            yield from _iter_floats(v)


@app.post("/jobs/{job_id}/rebuild", response_model=JobOut, status_code=202)
def rebuild_job(job_id: str, payload: RebuildIn) -> JobOut:
    """Re-run the pipeline on the same source with human-confirmed overrides."""
    with _session_factory() as session:
        original = _job_or_404(session, job_id)
        if original.source_type in {"upload", "gp"} and not Path(original.source).exists():
            raise HTTPException(409, "original upload no longer exists on the work volume")
        from rockforge.application.gp_pipeline import MIN_OFFSET_S

        params: dict[str, object] = dict(original.params or {})
        # Snapshot the PRE-EDIT timeline parameters before anything below mutates
        # them (dict() is shallow, so nested entries are shared). They are needed
        # to conjugate already-committed anchor stages — see _remap_committed_anchors.
        _old_scale = float(cast(float, params.get("tempo_scale", 1.0) or 1.0))
        _old_shift = _score_shift(params)
        _old_arr_scales: dict[str, float] = {
            k: float(cast(float, (v or {}).get("tempo_scale", _old_scale) or _old_scale))
            for k, v in cast(
                "dict[str, dict[str, object]]", params.get("arrangement_sync", {}) or {}
            ).items()
        }
        if payload.cent_offset is not None:
            params["cent_offset"] = payload.cent_offset
        if payload.offset_s is not None:
            if payload.offset_s < MIN_OFFSET_S:
                raise HTTPException(422, f"offset_s must be >= {MIN_OFFSET_S:g}")
            params["offset_s"] = payload.offset_s
        if payload.lead_in_s is not None:
            if payload.lead_in_s < 0.0:
                raise HTTPException(422, "lead_in_s must be >= 0")
            params["lead_in_s"] = payload.lead_in_s
        if payload.arrangement is not None and original.source_type != "gp":
            raise HTTPException(422, "arrangement scoping only applies to Guitar Pro jobs")

        _TRACK_SLOTS = {
            "lead": "lead_track", "rhythm": "rhythm_track", "combo": "combo_track",
            "alt_lead": "alt_lead_track", "alt_rhythm": "alt_rhythm_track",
        }
        if payload.tracks is not None:
            if original.source_type != "gp":
                raise HTTPException(422, "track assignment only applies to Guitar Pro jobs")
            unknown = set(payload.tracks) - set(_TRACK_SLOTS)
            if unknown:
                raise HTTPException(422, f"unknown arrangement slot(s): {sorted(unknown)}")
            chosen = [v for v in payload.tracks.values() if v is not None]
            if len(chosen) != len(set(chosen)):
                raise HTTPException(422, "each arrangement must use a different GP track")
            for slot, key in _TRACK_SLOTS.items():  # replace the whole assignment
                idx = payload.tracks.get(slot)
                if idx is None:
                    params.pop(key, None)
                else:
                    params[key] = int(idx)
        if payload.tuning_overrides is not None:
            if original.source_type != "gp":
                raise HTTPException(422, "tuning overrides only apply to Guitar Pro jobs")
            for kind, midi in payload.tuning_overrides.items():
                if len(midi) != 6:
                    raise HTTPException(422, f"tuning for {kind} must have 6 MIDI pitches")
            params["tuning_overrides"] = {k: list(v) for k, v in payload.tuning_overrides.items()}

        def _arr_entry(kind: str) -> dict[str, object]:
            # Per-arrangement tempo/drift overrides live under params["arrangement_sync"].
            # Seed a new entry from the job-level defaults so corrections already
            # applied to every arrangement are inherited (not dropped) the first
            # time this arrangement is edited on its own.
            store = cast(
                "dict[str, dict[str, object]]", params.setdefault("arrangement_sync", {})
            )
            if kind not in store:
                store[kind] = {
                    "tempo_scale": params.get("tempo_scale", 1.0),
                    "sync_anchor_stages": [
                        list(s)
                        for s in cast(
                            "list[list[object]]", params.get("sync_anchor_stages", [])
                        )
                    ],
                }
            return store[kind]

        def _sync_targets() -> list[dict[str, object]]:
            """Return the target dicts that tempo_scale/sync_anchors should be
            written to.  When ``apply_to_all`` is set (with ``arrangement``),
            the change propagates to every existing per-arrangement override
            *and* the job-level defaults, so both current and future
            arrangements share the same correction."""
            if payload.apply_to_all and payload.arrangement is not None:
                targets: list[dict[str, object]] = [params]
                store = cast(
                    "dict[str, dict[str, object]]",
                    params.get("arrangement_sync", {}),
                )
                for entry in store.values():
                    targets.append(entry)
                return targets
            if payload.arrangement is not None:
                return [_arr_entry(payload.arrangement)]
            return [params]

        if payload.tempo_scale is not None:
            if original.source_type != "gp":
                raise HTTPException(422, "tempo_scale only applies to Guitar Pro jobs")
            if payload.tempo_scale <= 0.0:
                raise HTTPException(422, "tempo_scale must be > 0")
            for target in _sync_targets():
                target["tempo_scale"] = payload.tempo_scale

        other_sync = (
            {}
            if original.source_type != "gp" or payload.apply_to_all or payload.arrangement is None
            else {k: v for k, v in (payload.other_sync or {}).items() if k != payload.arrangement}
        )
        for kind, pending in other_sync.items():
            if pending.tempo_scale is not None:
                if pending.tempo_scale <= 0.0:
                    raise HTTPException(422, "tempo_scale must be > 0")
                _arr_entry(kind)["tempo_scale"] = pending.tempo_scale

        def _remap_committed_anchors() -> None:
            """Re-express already-committed anchor stages in the NEW timeline.

            The build applies ``W(x·s + S)`` — parse at tempo_scale ``s`` with
            score shift ``S``, THEN warp — while the tab viewer previews
            ``R(W(x·s_built + S_built))``: it rescales the ALREADY-WARPED times it
            read back from the built XML. Function composition does not commute
            (``R∘W ≠ W∘R``), so as soon as ONE anchor stage is committed, changing
            the tempo or the offset makes the rebuild differ from the preview by
            ``d·(r−1)`` on EVERY note (``d`` = net shift the committed anchors
            introduce, ``r`` = the tempo ratio) — a CONSTANT desync, invisible in
            the viewer (which never re-derives the raw GP times) but plainly
            audible in game. That is the "no programa está sincronizado, no
            Rocksmith não" bug.

            Mapping every stored anchor pair through the viewer's own map
            ``φ(t) = (t − S_old)·r + S_new`` makes each stage ``W' = φ∘W∘φ⁻¹``,
            hence ``W'∘φ = φ∘W`` exactly — the rebuild then reproduces the
            preview. Each arrangement is conjugated with ITS OWN tempo ratio
            (tempo_scale is per-arrangement) but the shared job-level shift.
            """
            new_scale = float(cast(float, params.get("tempo_scale", 1.0) or 1.0))
            new_shift = _score_shift(params)
            store = cast(
                "dict[str, dict[str, object]]", params.get("arrangement_sync", {}) or {}
            )
            targets: list[tuple[dict[str, object], float, float]] = [
                (params, _old_scale, new_scale)
            ]
            for kind, entry in store.items():
                targets.append((
                    entry,
                    _old_arr_scales.get(kind, _old_scale),
                    float(cast(float, entry.get("tempo_scale", new_scale) or new_scale)),
                ))
            for target, s_old, s_new in targets:
                stages = cast(
                    "list[list[list[float]]]", target.get("sync_anchor_stages") or []
                )
                if not stages or s_old <= 0.0:
                    continue
                ratio = s_new / s_old
                if abs(ratio - 1.0) < 1e-12 and abs(new_shift - _old_shift) < 1e-12:
                    continue  # timeline unchanged for this arrangement
                target["sync_anchor_stages"] = [
                    [
                        [
                            (float(a) - _old_shift) * ratio + new_shift,
                            (float(b) - _old_shift) * ratio + new_shift,
                        ]
                        for a, b in stage
                    ]
                    for stage in stages
                ]

        if original.source_type == "gp":
            _remap_committed_anchors()
        if payload.sync_anchors is not None:
            if original.source_type != "gp":
                raise HTTPException(422, "sync_anchors only apply to Guitar Pro jobs")
            if payload.sync_anchors:
                for target in _sync_targets():
                    stages = [
                        list(s)
                        for s in cast(
                            "list[list[object]]", target.get("sync_anchor_stages", [])
                        )
                    ]
                    stages.append([list(a) for a in payload.sync_anchors])
                    target["sync_anchor_stages"] = stages
        for kind, pending in other_sync.items():
            if pending.sync_anchors:
                entry = _arr_entry(kind)
                done = cast("list[list[object]]", entry.get("sync_anchor_stages", []))
                entry["sync_anchor_stages"] = [
                    *[list(s) for s in done], [list(a) for a in pending.sync_anchors],
                ]
        if payload.import_mutes is not None:
            params["import_mute_techniques"] = payload.import_mutes
        if payload.dynamic_difficulty is not None:
            params["dynamic_difficulty"] = payload.dynamic_difficulty
        if payload.lyrics_events is not None:
            params["lyrics_events"] = [e.model_dump() for e in payload.lyrics_events]
            params.pop("lyrics_status", None)
        if payload.lyrics_follow_chart is not None:
            params["lyrics_follow_chart"] = payload.lyrics_follow_chart
        touches_tones = any(
            v is not None
            for v in (
                payload.tones,
                payload.tone_changes,
                payload.tone_base,
                payload.tone_names,
                payload.arrangement_tones,
            )
        )
        if touches_tones and original.source_type != "gp":
            raise HTTPException(422, "tones only apply to Guitar Pro jobs")
        if payload.tone_base is not None:
            params["tone_base"] = payload.tone_base or None
        if payload.tone_names is not None:
            if len(payload.tone_names) > 4:
                raise HTTPException(422, "Rocksmith supports at most 4 switchable tones")
            params["tone_names"] = payload.tone_names
        if payload.tones is not None:
            params["tones"] = payload.tones
        if payload.tone_changes is not None:
            params["tone_changes"] = [c.model_dump() for c in payload.tone_changes]
        if payload.arrangement_tones is not None:
            params["arrangement_tones"] = {
                kind: t.model_dump() for kind, t in payload.arrangement_tones.items()
            }
        if payload.section_overrides is not None:
            params["section_overrides"] = [s.model_dump() for s in payload.section_overrides]
        if payload.note_overrides is not None:
            params["note_overrides"] = {
                kind: [n.model_dump() for n in notes]
                for kind, notes in payload.note_overrides.items()
            }
        params["rebuilt_from"] = original.id
        job = Job(
            source=original.source,
            source_type=original.source_type,
            title=original.title,
            artist=original.artist,
            album=original.album,
            year=original.year,
            params=params,
        )
        session.add(job)
        session.commit()

        # Rebuild creates a fresh work directory (job.id != original.id); the
        # cover image referenced by params["cover_art"] lives under the
        # original job's directory, so copy it across or the worker's
        # candidate.exists() check (celery_app.generate_cdlc) silently finds
        # nothing and the bundle ends up without album art.
        cover_art_name = params.get("cover_art")
        if cover_art_name:
            src = settings.work_dir / original.id / cast(str, cover_art_name)
            if src.exists():
                dest_dir = settings.work_dir / job.id
                dest_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest_dir / cast(str, cover_art_name))

        _enqueue(job)
        return _to_out(job)


@app.get("/jobs/{job_id}/sync-state", response_model=SyncStateOut)
def get_sync_state(job_id: str) -> SyncStateOut:
    """Export a job's hand-tuned sync (anchors/tempo/offset/tuning/lyrics/tracks)
    as a portable JSON blob, so it can be re-imported into another job for the
    same song instead of redoing every manual correction."""
    with _session_factory() as session:
        job = _job_or_404(session, job_id)
        song = " - ".join(p for p in (job.artist, job.title) if p)
        return SyncStateOut(
            version=1, song=song, sync=_extract_sync_state(dict(job.params or {}))
        )


@app.post("/jobs/{job_id}/import-sync", response_model=JobOut, status_code=202)
def import_sync_state(job_id: str, payload: SyncStateIn) -> JobOut:
    """Apply a previously-exported sync state to this job and rebuild (fork),
    so hand-tuned drift/tempo/offset/lyrics/tracks survive re-creating a job."""
    clean = _sanitize_sync_state(payload.sync)
    with _session_factory() as session:
        original = _job_or_404(session, job_id)
        if original.source_type in {"upload", "gp"} and not Path(original.source).exists():
            raise HTTPException(409, "original upload no longer exists on the work volume")
        if original.source_type != "gp":
            for k in _SYNC_STATE_GP_ONLY:  # track/tuning-override keys need a GP file
                clean.pop(k, None)
        params: dict[str, object] = dict(original.params or {})
        params.update(clean)
        if "lyrics_events" in clean:
            # Let the next build use the imported lyrics (see rebuild_job).
            params.pop("lyrics_status", None)
        params["rebuilt_from"] = original.id
        job = Job(
            source=original.source, source_type=original.source_type,
            title=original.title, artist=original.artist, album=original.album,
            year=original.year, params=params,
        )
        session.add(job)
        session.commit()

        cover_art_name = params.get("cover_art")
        if cover_art_name:
            src = settings.work_dir / original.id / cast(str, cover_art_name)
            if src.exists():
                dest_dir = settings.work_dir / job.id
                dest_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest_dir / cast(str, cover_art_name))

        _enqueue(job)
        return _to_out(job)


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


@app.get("/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: str) -> JobOut:
    with _session_factory() as session:
        job = _job_or_404(session, job_id)
        return _to_out(job)


@app.patch("/jobs/{job_id}/sync-confirmed", response_model=JobOut)
def set_sync_confirmed(job_id: str, payload: SyncConfirmedIn) -> JobOut:
    """Record that the user checked the chart against the recording.

    Only the checklist reads it — nothing in the bundle changes, so there is no
    rebuild. It lives in `params`, so a rebuild/reload fork inherits it.
    """
    with _session_factory() as session:
        job = _job_or_404(session, job_id)
        params = dict(job.params or {})
        built = _built_kinds(job.bundle_dir)
        if payload.arrangement is None:
            synced = built if payload.confirmed else []
        else:
            if built and payload.arrangement not in built:
                raise HTTPException(422, f"no built arrangement named {payload.arrangement!r}")
            synced = [
                k for k in _synced_arrangements(params, job.bundle_dir) if k != payload.arrangement
            ]
            if payload.confirmed:
                synced.append(payload.arrangement)
        params["synced_arrangements"] = synced
        # The song is confirmed once every chart is — that is what the card and
        # the checklist mean by it; marking one track does not speak for others.
        params["sync_confirmed"] = (
            payload.confirmed if payload.arrangement is None
            else bool(built) and all(k in synced for k in built)
        )
        job.params = params
        session.commit()
        return _to_out(job)


@app.patch("/jobs/{job_id}/sync-main", response_model=JobOut)
def set_sync_main(job_id: str, payload: SyncMainIn) -> JobOut:
    """Choose the chart whose sync corrections the viewer carries onto the
    others ("Pista principal"). Nothing is rebuilt; it lives in `params`, so a
    fork inherits it."""
    with _session_factory() as session:
        job = _job_or_404(session, job_id)
        built = _built_kinds(job.bundle_dir)
        if payload.arrangement is not None and built and payload.arrangement not in built:
            raise HTTPException(422, f"no built arrangement named {payload.arrangement!r}")
        params = dict(job.params or {})
        if payload.arrangement:
            params["sync_main"] = payload.arrangement
        else:
            params.pop("sync_main", None)
        job.params = params
        session.commit()
        return _to_out(job)


@app.patch("/jobs/{job_id}/metadata", response_model=JobOut)
def update_metadata(job_id: str, payload: MetadataIn) -> JobOut:
    """Edit the song's identity (title/artist/album/year) after the job exists.

    Updates the job columns directly; the worker reads these when building, so the
    change lands in the bundle/PSARC on the next build/rebuild (like the cover
    art). Does not fork or re-run the job.
    """
    title = payload.title.strip()
    artist = payload.artist.strip()
    if not title or not artist:
        raise HTTPException(422, "title and artist are required")
    with _session_factory() as session:
        job = _job_or_404(session, job_id)
        job.title = title
        job.artist = artist
        job.album = payload.album.strip()
        job.year = payload.year
        session.commit()
        return _to_out(job)


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


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def index() -> str:
    for ui in _web_file_candidates("index.html"):
        if ui.exists():
            html = ui.read_text(encoding="utf-8")
            # Cache-bust app.js by its own mtime. index.html is generated per
            # request and never cached, but the browser happily keeps a stale
            # app.js — which leaves NEW markup wired to an OLD script, so a new
            # button exists and does nothing. That failure looks exactly like a
            # broken feature and has cost real debugging time.
            for name in WEB_SCRIPTS:
                for js in _web_file_candidates(name):
                    if js.exists():
                        html = html.replace(
                            f'src="/{name}"', f'src="/{name}?v={int(js.stat().st_mtime)}"'
                        )
                        break
            dicts = _i18n_dictionaries()
            stamp = max((int(d.stat().st_mtime) for d in dicts), default=0)
            html = html.replace('src="/i18n-dicts.js"', f'src="/i18n-dicts.js?v={stamp}"')
            return html
    return "<h1>RockForge</h1><p>UI not bundled; see /docs for the API.</p>"


# The web UI's own scripts, served by name (never a client path): app.js (the UI)
# and highway3d.js (the 3D note highway, which loads three.js on first use).
WEB_SCRIPTS = ("i18n.js", "app.js", "highway3d.js")
# three.js, vendored so the app works offline: the module and the core it imports.
THREE_FILES = ("three.module.js", "three.core.js")


def _serve_web_js(relative: str) -> FileResponse:
    for js in _web_file_candidates(relative):
        if js.exists():
            # Revalidate every load: the URL is mtime-stamped by index(), so a
            # changed file always wins, and an unchanged one still 304s.
            return FileResponse(
                js,
                media_type="text/javascript",
                headers={"Cache-Control": "no-cache"},
            )
    raise HTTPException(404, f"{relative} not bundled")


@app.get("/app.js", include_in_schema=False)
def app_js() -> FileResponse:
    """The web UI's JS, extracted out of index.html's inline <script> so it can
    be linted (ESLint has no way to check an inline block on its own)."""
    return _serve_web_js("app.js")


@app.get("/i18n.js", include_in_schema=False)
def i18n_js() -> FileResponse:
    """The UI's language switch and ``t()`` (loaded before app.js)."""
    return _serve_web_js("i18n.js")


def _i18n_dictionaries() -> list[Path]:
    """Every language the UI has besides Portuguese: one ``web/i18n-<code>.js``
    each, from the first web dir that has any (the same resolution as the
    other bundled files). Adding a language is adding that file."""
    for d in _web_dirs():
        found = sorted(
            p for p in d.glob("i18n-*.js") if re.fullmatch(r"i18n-[a-z]{2,3}\.js", p.name)
        )
        if found:
            return found
    return []


@app.get("/i18n-dicts.js", include_in_schema=False)
def i18n_dicts_js() -> Response:
    """All the UI's dictionaries in one script (each registers itself in
    ``I18N_DICTS``), so a new ``web/i18n-<code>.js`` needs no markup change."""
    body = "\n".join(p.read_text(encoding="utf-8") for p in _i18n_dictionaries())
    return Response(
        body, media_type="text/javascript", headers={"Cache-Control": "no-cache"}
    )


@app.get("/highway3d.js", include_in_schema=False)
def highway3d_js() -> FileResponse:
    """The 3D note highway (Partitura → "Pista 3D")."""
    return _serve_web_js("highway3d.js")


@app.get("/vendor/three/{name}", include_in_schema=False)
def three_js(name: str) -> FileResponse:
    """three.js, only the two files it is made of — never an arbitrary path."""
    if name not in THREE_FILES:
        raise HTTPException(404, "not found")
    return _serve_web_js(f"vendor/three/{name}")


# ── Endpoint groups (each reads this module's names as api.<name>) ──
from rockforge.interfaces.api.routers import tones as _tones  # noqa: E402

app.include_router(_tones.router)


# ── Endpoint groups (each reads app.py's shared state as api.<name>) ──
from rockforge.interfaces.api.routers import lyrics as _lyrics  # noqa: E402

app.include_router(_lyrics.router)
from rockforge.interfaces.api.routers import stems as _stems  # noqa: E402

app.include_router(_stems.router)
from rockforge.interfaces.api.routers import settings as _settings  # noqa: E402

app.include_router(_settings.router)
from rockforge.interfaces.api.routers import analysis as _analysis  # noqa: E402

app.include_router(_analysis.router)
from rockforge.interfaces.api.routers import gp_export as _gp_export  # noqa: E402

app.include_router(_gp_export.router)
from rockforge.interfaces.api.routers import imports as _imports  # noqa: E402

app.include_router(_imports.router)
from rockforge.interfaces.api.routers import charts as _charts  # noqa: E402

app.include_router(_charts.router)
from rockforge.interfaces.api.routers import delivery as _delivery  # noqa: E402

app.include_router(_delivery.router)
