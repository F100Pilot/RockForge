"""REST API: submit Guitar Pro jobs, poll status, edit sync/tones/lyrics,
download the bundle + PSARC.

Kept as a single module by deliberate choice (a splitting-into-APIRouters
refactor was considered — audit IMP-1 — and deferred): the endpoints share a
lot of module-level state (``settings``, ``_session_factory``, the four
``_enqueue*`` dispatchers, the heartbeat/idle-shutdown globals) that the API
test suite patches directly as ``app_module.<symbol>`` in ~90 tests. Moving
endpoints into separate router modules would make those endpoints resolve the
shared state from a different module, silently defeating the monkeypatches (a
patch that no longer intercepts does not error — the test just exercises real
code), for a purely organizational gain. Revisit as its own change with a
matching migration of the test patch targets; the endpoints are already
clearly delineated within this file.
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import mimetypes
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
from typing import TYPE_CHECKING, Annotated, Any, Literal, cast
from urllib.parse import urlparse

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel, Field, ValidationError

from rockforge import __version__, i18n
from rockforge.config import settings
from rockforge.domain.chords import name_chord
from rockforge.domain.music import STANDARD_E_MIDI
from rockforge.infrastructure.db.models import Job, JobStatus, make_session_factory

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


PIPELINE_STAGES = [
    "ingest", "normalize", "parse_gp", "build_arrangements", "lyrics", "package",
]


# Every float a CLIENT can send goes through this, never a bare ``float``.
# JSON carries the literals ``NaN`` and ``Infinity``, Pydantic accepts them in a
# float by default, and ``NaN <= 0`` is False — so the ``tempo_scale <= 0`` guard
# waved NaN straight through, the job forked, the value was persisted into the
# JSON params column, and the build only failed much later with an error that
# pointed nowhere. ``_build_time_warp`` propagates a NaN silently across the
# whole timeline. Rejecting it at the boundary is the project's own convention:
# surface the error where the bad value entered, never default silently.
Finite = Annotated[float, Field(allow_inf_nan=False)]
# A string's open-string pitch. The length check stays an explicit 422 (it needs
# a message naming the six strings), but the RANGE belongs here: an absurd pitch
# used to reach the SNG writer, where the semitone offset is packed as an int16
# and died as a `struct.error` pointing at nothing.
MidiPitch = Annotated[int, Field(ge=0, le=127)]
# How far the recording sits from A440, in cents. Past ±50 it is closer to the
# next semitone, which is a TUNING (Editar info), not a deviation; the detector
# itself answers inside ±50 (librosa's estimate_tuning is in ±0.5 bins).
MAX_CENT_OFFSET = 50.0
CentOffset = Annotated[
    float, Field(ge=-MAX_CENT_OFFSET, le=MAX_CENT_OFFSET, allow_inf_nan=False)
]


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


class JobOut(BaseModel):
    id: str
    status: str
    stage: str | None
    stages: list[str] = PIPELINE_STAGES
    title: str
    artist: str
    album: str
    year: int | None
    created_at: str
    warnings: list[str]
    note_counts: dict[str, int]
    psarc_available: bool
    bundle_available: bool
    source_type: str
    offset_s: float
    lead_in_s: float = 0.0
    tempo_scale: float
    import_mutes: bool
    dynamic_difficulty: bool = True
    error: str | None
    lyrics_status: str = "none"
    tone_detection_status: str = "none"
    cover_art: bool = False
    # Completeness signals for the "Estado do PSARC" checklist. has_tones: the
    # user defined at least one custom tone (else DLC Builder flags "tone
    # missing"). sync_edited: at least one sync adjustment was made (offset moved
    # off 0, tempo scaled, or a drift anchor placed) — drives the soft
    # "confirmaste a sincronização?" reminder. Both GP-only.
    has_tones: bool = False
    sync_edited: bool = False
    # The user said "it is in sync" (`PATCH /jobs/{id}/sync-confirmed`). A song
    # that needed no adjustment — synced in Guitar Pro 8, its embedded audio, or
    # simply right from the start — has nothing for `sync_edited` to see, so
    # without this the reminder could never be cleared.
    sync_confirmed: bool = False
    # The chart whose sync corrections the viewer carries onto the others
    # ("Pista principal"); None = each chart on its own.
    sync_main: str | None = None
    # Why the chart counts as in sync, for the badge on the project card and the
    # score: "confirmed" (the user said so), "gp" (synced in Guitar Pro 8 — the
    # file carries its own sync points), "songsterr" (human-marked bar times),
    # "adjusted" (corrected here, not yet confirmed) or None.
    sync_source: str | None = None
    # The charts the user marked as in sync, one by one (their tabs turn green).
    synced_arrangements: list[str] = []
    # The recording is the audio the Guitar Pro file carries (its own copy, the
    # one its sync points describe), not a separate upload.
    recording_from_gp: bool = False
    # True if the bundle carries lyrics from ANY source — edited/GP-embedded
    # events, an LRC/UltraStar file, or completed WhisperX detection — not just
    # `lyrics_status == "ready"` (which only covers detection).
    has_lyrics: bool = False
    # The job this one was forked from (rebuild / reload-gp / import-sync). Lets the
    # UI offer "previous version" so an iterative sync can be walked back — the older
    # job (and its bundle) is never deleted on a rebuild.
    rebuilt_from: str | None = None
    # Is this song in the game's dlc folder ("Instalar no jogo")? "this" = this
    # version's PSARC, "older" = a copy installed from an earlier version (a
    # rebuild inherits the record), None = not installed or since deleted.
    in_game: str | None = None
    in_game_path: str | None = None


class OtherSyncIn(BaseModel):
    tempo_scale: Finite | None = None
    sync_anchors: list[tuple[Finite, Finite]] = []


def _score_shift(params: dict[str, object]) -> float:
    """Where bar 1's score time lands in the bundle: ``max(offset_s, MIN_LEAD_S)
    + lead_in_s`` — the same formula as ``gp_pipeline``'s ``score_shift`` (and
    ``scoreShift`` in web/app.js). The anchor re-expression must use the build's
    value exactly, or a tempo change shifts every note by the difference."""
    from rockforge.application.gp_pipeline import MIN_LEAD_S

    offset = float(cast(float, params.get("offset_s", 0.0) or 0.0))
    lead_in = float(cast(float, params.get("lead_in_s", 0.0) or 0.0))
    return max(offset, MIN_LEAD_S) + max(0.0, lead_in)


class RebuildIn(BaseModel):
    """Human-review overrides for a rebuild (sync, tuning, tones, lyrics, note edits)."""

    # How far the recording is from A440, for every chart (one recording); None
    # leaves the stored value. The strings' own tuning is per chart, in
    # tuning_overrides below ("Editar info").
    cent_offset: CentOffset | None = None
    offset_s: Finite | None = None  # GP sync: second in the recording where the song starts
    lead_in_s: Finite | None = None  # GP: extra intro silence prepended (pushes the song later)
    tempo_scale: Finite | None = None  # GP sync: stretch/compress the whole chart timeline
    # Manual drift-correction points: (chart_time_s, corrected_time_s) pairs, in the
    # chart's already-shifted timeline (as shown in the tab viewer).
    sync_anchors: list[tuple[Finite, Finite]] | None = None
    # When set (ArrangementKind value, e.g. "Lead"/"Rhythm"/"Combined"), tempo_scale
    # and sync_anchors are scoped to that arrangement alone instead of all of them.
    arrangement: str | None = None
    # When True (with arrangement set), tempo_scale and sync_anchors are applied
    # to every arrangement that has notes, not just the specified one.
    apply_to_all: bool = False
    # The OTHER charts' pending sync, committed in the same rebuild (keyed like
    # arrangement). Before it only the chart on screen was sent, so another
    # tab's pending corrections — and what the "Pista principal" carries onto
    # the others — were lost. Ignored with apply_to_all.
    other_sync: dict[str, OtherSyncIn] | None = None
    # GP: when False, palm mute / slap / pop / tap are stripped (plain notes).
    import_mutes: bool | None = None
    # When False, the native PSARC's SNG is a single full-chart level (no DD).
    dynamic_difficulty: bool | None = None
    # GP: re-assign which GP track feeds which arrangement, post-creation. Keys are
    # "lead"/"rhythm"/"combo"/"alt_lead"/"alt_rhythm"; a value is the track index,
    # or null to clear that slot. When set (even to {}), it REPLACES the whole
    # track assignment. None leaves it unchanged.
    tracks: dict[str, int | None] | None = None
    # GP: per-arrangement tuning override, keyed by ArrangementKind value
    # ("Lead"/"Rhythm"/…) → the six MIDI pitches (low to high). When set (even to
    # {}), replaces params["tuning_overrides"]; None leaves it untouched.
    tuning_overrides: dict[str, list[MidiPitch]] | None = None
    # Edited per-word lyrics from the in-app lyrics editor. When set (even to an
    # empty list), replaces params["lyrics_events"] and clears lyrics_status so
    # the next build uses the edited lyrics. None leaves existing lyrics alone.
    lyrics_events: list[LyricEventOut] | None = None
    # Whether the lyric rows move with the chart's sync corrections (lyrics timed
    # on the score) or stay put (timed to the recording). None leaves it alone.
    lyrics_follow_chart: bool | None = None
    # Tone editor overrides (GP jobs). When set (even to an empty list), each
    # replaces the corresponding params entry; None leaves it untouched.
    # ``tones`` are full gear definitions (see gear_catalogue.tone_from_dict);
    # ``tone_base``/``tone_names`` reference them by key; ``tone_changes`` are the
    # timed switches placed on the partitura.
    tone_base: str | None = None
    tone_names: list[str] | None = None
    tones: list[dict[str, Any]] | None = None
    tone_changes: list[ToneChangeIn] | None = None
    # Each track's own tone setup, keyed by ArrangementKind.value (the tones
    # themselves stay song-level in ``tones``). When set, REPLACES
    # params["arrangement_tones"] — {} brings every track back to the song-level
    # tone_base/tone_names/tone_changes above; None leaves it untouched.
    arrangement_tones: dict[str, ArrangementTonesIn] | None = None
    # In-app section-editor overrides (bundle-clock times, placed on the tab
    # viewer, same convention as tone_changes). When set (even to an empty
    # list), replaces the GP-parsed sections for every arrangement; None
    # leaves each arrangement's own GP-authored sections untouched.
    section_overrides: list[SectionOverrideIn] | None = None
    # In-app note-editor edits (GP jobs), keyed by ArrangementKind.value —
    # genuinely per-arrangement, unlike tone_changes/section_overrides. Each
    # entry upserts a note at (time, string), or removes it when
    # ``deleted``. When set (even to {}), REPLACES params["note_overrides"]
    # wholesale; None leaves it untouched.
    note_overrides: dict[str, list[NoteOverrideIn]] | None = None


class ArrangementTonesIn(BaseModel):
    """One track's own tone setup (see ``gp_pipeline.ArrangementTones``)."""

    tone_base: str | None = None
    tone_names: list[str] = Field(default=[], max_length=4)
    tone_changes: list[ToneChangeIn] = []


class ToneChangeIn(BaseModel):
    """A timed tone switch placed on the score. Was a free ``dict[str, Any]``,
    so its time bypassed validation entirely — same shape as the section and
    note overrides, so it gets the same treatment."""

    time: Finite
    name: str


class SectionOverrideIn(BaseModel):
    time: Finite
    name: str


class SectionOut(BaseModel):
    time: float
    name: str
    number: int


class NoteOverrideIn(BaseModel):
    time: Finite
    string: int = Field(ge=0, le=5)
    fret: int = Field(default=0, ge=0, le=24)
    sustain: Finite = 0.0
    techniques: list[str] = []
    bend_semitones: Finite = 0.0
    slide_to_fret: int | None = Field(default=None, ge=0, le=24)
    deleted: bool = False


class ArrangementNoteOut(BaseModel):
    time: float
    string: int
    fret: int
    sustain: float
    chord: bool
    techniques: list[str]
    bend_semitones: int = 0  # bend magnitude (1=half, 2=full, 3=1½…); 0 if no bend
    chord_name: str | None = None  # derived name for the chord this note belongs to
    # The fret a slide ends on (pitched, else unpitched slide-out), -1 if none —
    # the 3D highway draws the trail running to it.
    slide_to: int = -1


class BarOut(BaseModel):
    measure: int  # 1-based bar number
    time: float   # bundle-time position of the bar's downbeat


class ArrangementOut(BaseModel):
    kind: str
    tuning_offsets: list[int]
    cent_offset: float
    average_bpm: float
    tempo_scale: float  # this arrangement's own tempo scale (GP sync), 1.0 if none
    note_count: int
    chord_count: int
    notes: list[ArrangementNoteOut]
    bars: list[BarOut] = []  # measure downbeats for the viewer's bar numbering
    beats: list[float] = []  # ALL ebeat times (downbeats + off-beats) — the drag snap grid
    # Named song-structure markers (GP-authored, or the in-app editor's
    # overrides), bundle-clock time — the writer's synthetic trailing
    # "noguitar" end sentinel is never included here.
    sections: list[SectionOut] = []
    # The note-editor edits ALREADY COMMITTED for this arrangement (from
    # params["note_overrides"]). The viewer seeds its pending list from these, so
    # the always-send round-trip is lossless: it used to reset to {} on every job
    # open and a rebuild for any unrelated reason (a tuning change, say) then
    # sent {} and silently erased every note edit the user had applied.
    note_overrides: list[NoteOverrideIn] = []
    # The user marked THIS chart as in sync with the recording (each track is
    # synchronised on its own; its tab turns green).
    sync_confirmed: bool = False
    # How Rocksmith names this chart in game ("LEAD 1", "LEAD 2", "RHYTHM",
    # "COMBO") — numbered only when the song has two on the same path.
    game_name: str = ""
    # Bars (as ``bars`` numbers them) whose rhythm PDF-to-GP5 estimated from the
    # note spacing when it converted this track: the ones to check first.
    estimated_bars: list[int] = []


class TempoCorrectionIn(BaseModel):
    measure: int = Field(ge=1)
    bpm: float = Field(gt=10.0, lt=400.0)


class ExportGpIn(BaseModel):
    corrections: list[TempoCorrectionIn]


class AppliedCorrectionOut(BaseModel):
    measure: int
    requested_bpm: float
    written_bpm: float
    rounded: bool


class ExportGpOut(BaseModel):
    """Report of a corrected Guitar Pro export — the file is fetched separately."""

    filename: str
    format: str
    size_bytes: int
    applied: list[AppliedCorrectionOut]
    warnings: list[str]


class ExportArrangementGpOut(BaseModel):
    """Report of a generated Guitar Pro file — the file is fetched separately."""

    filename: str
    arrangement: str
    measures: int
    notes_written: int
    notes_dropped: int
    quantized: int
    max_shift_ms: float
    warnings: list[str]


class DetectTempoIn(BaseModel):
    from_s: Finite = 0.0  # recording time to start measuring the local tempo from
    # The chart's tempo AS CURRENTLY DISPLAYED at that point (the viewer's live
    # BPM readout: authored spacing × tempo_scale × pending anchors). Optional —
    # falls back to the GP file's header tempo, which is only right for a song
    # with no tempo changes and no corrections applied yet.
    chart_bpm: Finite | None = None


class DetectTempoOut(BaseModel):
    """Local tempo measured from a point — for the per-point 're-tempo from here' tool."""

    gp_bpm: float  # the GP file's header tempo (informational)
    reference_bpm: float  # what the factor is measured against (chart_bpm, else gp_bpm)
    detected_bpm: float
    suggested_factor: float  # multiply note spacing after the point by this
    used_drum_stem: bool = False  # tempo measured on the isolated drum stem?


class DetectTuningOut(BaseModel):
    """Proposed fine-tuning correction (not applied; the user reviews then
    rebuilds). String/drop tuning is NOT detected — see librosa_adapter."""

    suggested_cent_offset: float


# Doubles as an INPUT model (RebuildIn.lyrics_events carries the in-app lyric
# editor's rows), hence the finite times.
class LyricEventOut(BaseModel):
    time: Finite
    length: Finite
    lyric: str


class DetectTonesOut(BaseModel):
    """Proposed lead + rhythm tone presets based on spectral analysis of the
    guitar stem. Not auto-applied; the user reviews in the tone editor."""

    # "none"|"detecting"|"separating"|"analyzing"|"ready"|"unavailable"
    status: str
    category: str = ""  # "clean"|"crunch"|"high_gain"
    lead: dict[str, Any] = {}
    rhythm: dict[str, Any] = {}
    # Full ranked libraries (closest first, each carrying a 0-100 "match") so the
    # user can browse several "similar tones" rather than only the top guess.
    lead_candidates: list[dict[str, Any]] = []
    rhythm_candidates: list[dict[str, Any]] = []
    profile: dict[str, Any] = {}  # detected spectral profile (gain/brightness/…)
    log: list[str] = []
    # The detection measured the tone over time too, so /tone-suggestions can
    # propose a tone per part of each track.
    has_timeline: bool = False


class ToneReasonOut(BaseModel):
    code: str  # chords, palm_mute, lead, high, ring, gain, no_audio
    value: float = 0.0


class ToneSegmentOut(BaseModel):
    name: str
    start: float  # bundle clock, as the score draws it
    end: float
    role: str  # clean / rhythm / lead / silent
    tone_key: str | None = None
    tone_name: str | None = None
    match: int = 0
    confidence: str = "low"  # high / medium / low
    reasons: list[ToneReasonOut] = []
    gain: float = 0.0
    brightness: float = 0.0
    low_end: float = 0.0


class TrackTonePlanOut(BaseModel):
    kind: str
    segments: list[ToneSegmentOut]
    base: str | None = None
    names: list[str] = []  # slots A-D, base first — what tone_names takes
    changes: list[ToneChangeIn] = []
    tones: list[dict[str, Any]] = []


class ToneSwapIn(BaseModel):
    """The user's stand-in for one suggested tone: the whole tone, where it came
    from ("project" / "library" / "collection") and, for a PSARC tone, the song
    it came from."""

    tone: dict[str, Any]
    source: Literal["project", "library", "collection"]
    label: str | None = Field(default=None, max_length=300)


class ToneSuggestionsOut(BaseModel):
    tracks: list[TrackTonePlanOut]
    # The stand-ins the user chose for suggested tones, by suggested key — kept
    # with the project (PATCH /jobs/{id}/tone-swaps) so they survive leaving it.
    swaps: dict[str, ToneSwapIn] = {}
    # The tone over time moved onto the bundle clock, [t, gain, active], for the
    # little gain curve drawn above the suggested parts.
    timeline: list[list[float]] = []


class StemsOut(BaseModel):
    """State of per-instrument stem separation. ``stems`` lists the available
    stem names (guitar/bass/drums/vocals/other/piano); each is served via
    GET /jobs/{id}/stem/{name} so the viewer can solo one while fine-tuning sync."""

    # "none"|"detecting"|"normalizing"|"separating"|"ready"|"unavailable"
    status: str
    stems: list[str] = []
    log: list[str] = []


class SettingsOut(BaseModel):
    """App settings editable from the UI (persisted in work_dir/settings.json).
    `banquet` carries per-path readiness so the UI can show ✓/✗."""

    stem_separator: str = "demucs"  # "demucs" | "banquet"
    banquet_repo: str = ""
    banquet_ckpt: str = ""
    banquet_queries: str = ""
    banquet: dict[str, Any] = {}  # repo_ok/ckpt_ok/queries_ok/query_names/ready
    # Loudness/volume target (LUFS): louder = higher (closer to 0). The audio is
    # normalized to this AND the Wwise bus volume is calibrated to it.
    loudness_target: float = -12.0
    # True when the GPU-broken marker is set (a CUDA crash tripped the whole-ML
    # -stack CPU fallback). The UI shows this + a "reactivate GPU" button so the
    # user doesn't have to hunt for the hidden marker file.
    gpu_broken: bool = False
    # ctranslate2 compute type for WhisperX ("" = pick by device). May be a
    # manual choice or auto-persisted by the GPU escalation ladder when a
    # non-default type is found to work — editable here so the user isn't stuck
    # setting/clearing the ROCKFORGE_WHISPERX_COMPUTE_TYPE env var by hand.
    whisperx_compute_type: str = ""
    # The Python the heavy ML stages (Demucs / WhisperX / librosa) are run
    # with. Empty = this very process, which is right for a Python install and
    # impossible for the frozen .exe, whose own interpreter IS the executable.
    # `ml_python` carries per-extra readiness, probed in a subprocess so this
    # process never imports torch.
    ml_python: str = ""
    ml_python_info: dict[str, Any] = {}
    # The Rocksmith 2014 folder the user set ("" = found by looking in the Steam
    # libraries, which is `rocksmith_dir_detected`). The CDLC patch is looked for
    # there and the tone collection suggests its dlc folder.
    rocksmith_dir: str = ""
    rocksmith_dir_detected: str = ""


class SettingsIn(BaseModel):
    stem_separator: str | None = None
    banquet_repo: str | None = None
    banquet_ckpt: str | None = None
    banquet_queries: str | None = None
    loudness_target: Finite | None = None
    # "" clears the override (falls back to ROCKFORGE_WHISPERX_COMPUTE_TYPE / by
    # device); None leaves it untouched.
    whisperx_compute_type: str | None = None
    # "" clears the override (falls back to ROCKFORGE_ML_PYTHON / this process).
    ml_python: str | None = None
    # "" clears it (back to looking in the Steam libraries).
    rocksmith_dir: str | None = None


class LyricsOut(BaseModel):
    # "none"|"detecting"|"normalizing"|"separating"|"transcribing"|"aligning"|
    # "ready"|"empty"|"unavailable"
    status: str
    events: list[LyricEventOut]
    log: list[str] = []
    # The rows move with the chart's sync corrections (timed on the score) —
    # see _lyrics_follow_chart.
    follow_chart: bool = False


class MetadataIn(BaseModel):
    """Editable song identity for an existing job (title/artist/album/year)."""

    title: str
    artist: str
    album: str = ""
    year: int | None = None


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


class GpTrackOut(BaseModel):
    index: int
    name: str
    is_percussion: bool
    string_count: int
    tuning_midi: list[int]


class GpInspectOut(BaseModel):
    gp_token: str
    title: str
    artist: str
    album: str
    tempo: int
    has_lyrics: bool
    tracks: list[GpTrackOut]
    # Where bar 1 falls in the audio Guitar Pro 8 was synced to (its audio-track
    # sync points), or None. When the recording is that same file this IS the
    # offset, so the wizard pre-fills it instead of asking for a guess.
    sync_start_s: float | None = None
    # The recording a GP8 file carries inside it (its audio track), as
    # {"name", "size_bytes"}, or None. When present it is the audio the sync
    # points describe, so the wizard offers it instead of asking for an upload.
    embedded_audio: dict[str, Any] | None = None
    # When the audio GP8 was synced to is NOT inside the file, where it is: a
    # YouTube video (the wizard fetches its audio) or a file on the user's disk.
    backing_youtube_url: str | None = None
    backing_external_path: str | None = None
    # The audio track is switched off in Guitar Pro (its audio is used anyway).
    backing_disabled: bool = False
    # Set when the file was built from a Songsterr tab (/songsterr/import): the
    # link, so the wizard can fetch that song's bar times too, and what the
    # conversion could not carry over.
    songsterr_song: str | None = None
    import_warnings: list[str] = []
    # Set when the file was converted from a PDF or a picture of the tab
    # (/pdf/import, PDF-to-GP5's converter): the names of those files.
    pdf_files: list[str] = []
    # …and, per track index, the bars whose rhythm the converter estimated from
    # the note spacing, numbered as the chart plays them. The wizard hands them
    # back to /jobs/gp so the viewer can offer them for review.
    estimated_bars: dict[int, list[int]] = {}


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


@app.post("/gp/inspect", response_model=GpInspectOut)
def inspect_gp_file(file: UploadFile = File(...)) -> GpInspectOut:
    """Upload a Guitar Pro file, get its tracks for selection. The file is kept
    server-side and referenced by gp_token when creating the job."""
    suffix = Path(file.filename or "").suffix.lower()
    if suffix in GP_REJECTED_SUFFIXES:
        raise HTTPException(
            415,
            "GP6 (.gpx) is not supported (proprietary binary container). "
            "Export as GP5 or GP7 (.gp) from Guitar Pro or TuxGuitar and upload again.",
        )
    if suffix not in GP_SUFFIXES:
        raise HTTPException(415, f"unsupported Guitar Pro format: {suffix or '(none)'}")
    gp_dir = settings.work_dir / "gp"
    gp_dir.mkdir(parents=True, exist_ok=True)
    dest = gp_dir / f"{uuid.uuid4()}{suffix}"
    _copy_upload_capped(file, dest)
    return _inspect_stored_gp(dest)


def _inspect_stored_gp(dest: Path) -> GpInspectOut:
    """The wizard's track list for a GP file already stored under work_dir/gp."""
    from rockforge.domain.errors import IngestionError
    from rockforge.infrastructure.gpimport.parser import inspect_gp

    try:
        info = inspect_gp(dest)
    except IngestionError as exc:
        dest.unlink(missing_ok=True)
        raise HTTPException(422, str(exc)) from exc
    from rockforge.infrastructure.gpimport.gpif_parser import (
        BackingTrackInfo,
        backing_track,
        sync_start_s,
    )

    # Both are hints for the wizard, never a reason to refuse a file that parsed.
    try:
        synced_start = sync_start_s(dest)
    except Exception:
        synced_start = None
    try:
        backing = backing_track(dest)
    except Exception:
        backing = BackingTrackInfo()
    embedded = backing.audio
    return GpInspectOut(
        gp_token=dest.name,
        sync_start_s=synced_start,
        backing_youtube_url=backing.youtube_url,
        backing_external_path=backing.external_path,
        backing_disabled=backing.disabled,
        embedded_audio=(
            {"name": Path(embedded.member).name, "size_bytes": embedded.size_bytes}
            if embedded is not None
            else None
        ),
        title=info.title,
        artist=info.artist,
        album=info.album,
        tempo=info.tempo,
        has_lyrics=info.has_lyrics,
        tracks=[
            GpTrackOut(
                index=t.index,
                name=t.name,
                is_percussion=t.is_percussion,
                string_count=t.string_count,
                tuning_midi=list(t.tuning_midi),
            )
            for t in info.tracks
        ],
    )


class SongsterrVideoOut(BaseModel):
    video_id: str
    url: str
    #: None = Songsterr's default video; else "alternative"/"backing"/"solo"/…
    feature: str | None
    #: Where each measure starts in THAT video, in seconds — sent back as
    #: /jobs/gp's ``bar_times`` when the user picks this video.
    points: list[float]


class SongsterrOut(BaseModel):
    song_id: int
    revision_id: int
    title: str
    artist: str
    videos: list[SongsterrVideoOut]


class YouTubeAudioIn(BaseModel):
    video_id: str = Field(max_length=20)
    #: A browser on this machine whose YouTube login yt-dlp may reuse, for when
    #: YouTube refuses an anonymous download.
    cookies_browser: str | None = Field(default=None, max_length=20)


class YouTubeAudioOut(BaseModel):
    audio_token: str
    name: str
    size_bytes: int


@app.post("/youtube/audio", response_model=YouTubeAudioOut)
def youtube_audio(payload: YouTubeAudioIn) -> YouTubeAudioOut:
    """Fetch the audio of one YouTube video (the one Songsterr's bar times were
    marked on) with yt-dlp, for ``/jobs/gp``'s ``audio_token``. 422 for a bad id
    or browser name, 503 when yt-dlp is not installed, 502 when the download
    fails — its detail says when YouTube wants a browser login. See
    ``infrastructure/youtube_audio.py``."""
    from rockforge.infrastructure.youtube_audio import (
        COOKIE_BROWSERS,
        VIDEO_ID,
        YouTubeAudioError,
        YtDlpMissingError,
        download_audio,
    )

    if not VIDEO_ID.match(payload.video_id):
        raise HTTPException(422, "invalid YouTube video id")
    if payload.cookies_browser and payload.cookies_browser not in COOKIE_BROWSERS:
        raise HTTPException(422, f"unknown browser: {payload.cookies_browser}")
    try:
        path = download_audio(
            payload.video_id, settings.work_dir / "uploads",
            cookies_browser=payload.cookies_browser or None,
        )
    except YtDlpMissingError as exc:
        raise HTTPException(503, str(exc)) from exc
    except YouTubeAudioError as exc:
        hint = i18n.tr(
            " — o YouTube pediu uma sessão iniciada: escolhe um browser onde "
            "tenhas o YouTube aberto e tenta de novo",
            " — YouTube asked for a signed-in session: choose a browser where "
            "you have YouTube open and try again",
        ) if exc.needs_cookies else ""
        raise HTTPException(502, f"{exc}{hint}") from exc
    return YouTubeAudioOut(audio_token=path.name, name=path.name, size_bytes=path.stat().st_size)


class SongsterrImportIn(BaseModel):
    song: str = Field(max_length=500)


@app.post("/songsterr/import", response_model=GpInspectOut)
def songsterr_import(payload: SongsterrImportIn) -> GpInspectOut:
    """Build a Guitar Pro file from a Songsterr tab, in place of uploading one.

    The tab's tracks are fetched (``songsterr.fetch_tab``), written as a GP5
    (``gpimport/songsterr_gp``) under ``work_dir/gp`` like an upload, and the
    answer is exactly ``/gp/inspect``'s — so the rest of the wizard, the job
    and every later tool see an ordinary GP file. No audio is fetched. 422 for
    a link we cannot read, 502 when Songsterr is unreachable or changed.
    """
    from rockforge.domain.errors import IngestionError
    from rockforge.infrastructure.gpimport.songsterr_gp import write_songsterr_gp5
    from rockforge.infrastructure.songsterr import SongsterrError, fetch_tab, parse_song_id

    try:
        parse_song_id(payload.song)
    except SongsterrError as exc:
        raise HTTPException(422, str(exc)) from exc
    try:
        tab = fetch_tab(payload.song)
    except SongsterrError as exc:
        raise HTTPException(502, str(exc)) from exc
    gp_dir = settings.work_dir / "gp"
    dest = gp_dir / f"{uuid.uuid4()}.gp5"
    try:
        report = write_songsterr_gp5(list(tab.parts), dest, title=tab.title, artist=tab.artist)
    except IngestionError as exc:
        dest.unlink(missing_ok=True)
        raise HTTPException(422, str(exc)) from exc
    out = _inspect_stored_gp(dest)
    warnings = list(report.warnings)
    if tab.missing:
        warnings.insert(
            0, i18n.tr("não consegui descarregar: ", "could not download: ")
            + ", ".join(tab.missing),
        )
    out.songsterr_song = str(tab.song_id)
    out.import_warnings = warnings
    return out


@app.post("/pdf/import", response_model=GpInspectOut)
def pdf_import(files: list[UploadFile] = File(...)) -> GpInspectOut:
    """Build a Guitar Pro file from a PDF or a picture of the tab, in place of
    uploading one — PDF-to-GP5's converter (the ``[pdf]`` extra), one file per
    track in order. The GP5 lands in ``work_dir/gp`` like an upload and the
    answer is ``/gp/inspect``'s, plus what the conversion warns about. 503
    without the extra, 413/415 for a file it would not take, 422 for one the
    converter refused (its own message, in the user's language).
    """
    from rockforge.infrastructure.gpimport import pdf_import as converter

    if not converter.available():
        raise HTTPException(503, converter.missing_message())
    if not files:
        raise HTTPException(422, i18n.tr("Nenhum ficheiro enviado.", "No file uploaded."))
    if len(files) > converter.MAX_FILES:
        raise HTTPException(
            422,
            i18n.tr(
                f"No máximo {converter.MAX_FILES} ficheiros (um por pista).",
                f"At most {converter.MAX_FILES} files (one per track).",
            ),
        )
    read: list[tuple[str, bytes]] = []
    total = 0
    for upload in files:
        name = Path(upload.filename or "").name
        data = upload.file.read(converter.MAX_FILE_BYTES + 1)
        total += len(data)
        if len(data) > converter.MAX_FILE_BYTES or total > converter.MAX_TOTAL_BYTES:
            raise HTTPException(
                413, i18n.tr(f"Ficheiro demasiado grande: {name}.", f"File too large: {name}.")
            )
        if converter.file_kind(data) is None:
            raise HTTPException(
                415,
                i18n.tr(
                    f"Não é um PDF nem uma imagem PNG, JPEG ou WebP: {name}.",
                    f"Not a PDF or a PNG, JPEG or WebP picture: {name}.",
                ),
            )
        read.append((name, data))
    try:
        result = converter.convert(read)
    except converter.PdfConverterMissingError as exc:
        raise HTTPException(503, str(exc)) from exc
    except converter.PdfImportError as exc:
        raise HTTPException(422, str(exc)) from exc
    gp_dir = settings.work_dir / "gp"
    gp_dir.mkdir(parents=True, exist_ok=True)
    dest = gp_dir / f"{uuid.uuid4()}.gp5"
    dest.write_bytes(result.gp5)
    out = _inspect_stored_gp(dest)
    out.pdf_files = [name for name, _ in read]
    out.import_warnings = result.warnings
    out.estimated_bars = result.estimated_bars
    return out


@app.get("/songsterr", response_model=SongsterrOut)
def songsterr_lookup(song: str) -> SongsterrOut:
    """Per-measure timestamps Songsterr's users marked for a song's videos.

    Only the times are fetched — the recording is the user's own, converted
    from that YouTube video (Songsterr's own audio is a different recording
    and does not match these times). The API is undocumented, so
    a changed or unreachable Songsterr is a 502 saying so, never a crash; a
    link we cannot read is a 422. See ``infrastructure/songsterr.py``.
    """
    from rockforge.infrastructure.songsterr import SongsterrError, fetch_song, parse_song_id

    try:
        parse_song_id(song)
    except SongsterrError as exc:
        raise HTTPException(422, str(exc)) from exc
    try:
        found = fetch_song(song)
    except SongsterrError as exc:
        raise HTTPException(502, str(exc)) from exc
    return SongsterrOut(
        song_id=found.song_id,
        revision_id=found.revision_id,
        title=found.title,
        artist=found.artist,
        videos=[
            SongsterrVideoOut(
                video_id=v.video_id, url=v.url, feature=v.feature, points=list(v.points)
            )
            for v in found.videos
        ],
    )


class AlbumCandidateOut(BaseModel):
    source: str
    album: str
    artist: str
    year: int | None
    cover_url: str | None
    thumb_url: str | None
    track: str
    kind: str


class AlbumLookupOut(BaseModel):
    candidates: list[AlbumCandidateOut]
    #: What was actually searched (the main artist, the title without a
    #: featuring credit), so "nothing found" can say for what.
    searched_title: str = ""
    searched_artist: str = ""
    #: A service that could not be asked — its silence is not "not there".
    failures: list[str] = []


@app.get("/album-lookup", response_model=AlbumLookupOut)
def album_lookup(title: str = "", artist: str = "") -> AlbumLookupOut:
    """Album name, year and cover candidates for a song, for the user to choose.

    Asks the iTunes Search API and MusicBrainz/Cover Art Archive (no keys);
    nothing is written anywhere until the user picks one. No results is an
    empty list; both services unreachable is a 502. See
    ``infrastructure/album_lookup.py``.
    """
    from rockforge.infrastructure.album_lookup import (
        AlbumLookupError,
        primary_artist,
        search_albums,
        search_title,
    )

    if not title.strip() or not artist.strip():
        raise HTTPException(422, "title and artist are required to look up an album")
    failures: list[str] = []
    try:
        found = search_albums(title, artist, failures=failures)
    except AlbumLookupError as exc:
        raise HTTPException(502, str(exc)) from exc
    return AlbumLookupOut(
        candidates=[AlbumCandidateOut(**vars(c)) for c in found],
        searched_title=search_title(title),
        searched_artist=primary_artist(artist),
        failures=failures,
    )


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


class SyncStateOut(BaseModel):
    version: int
    song: str
    sync: dict[str, object]


class SyncStateIn(BaseModel):
    version: int | None = None
    sync: dict[str, object]


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


# --- Isolated-drum beat detection ---------------------------------------------
# librosa's beat/tempo tracker (used by /detect-tempo below) is
# unreliable on a full mix of fast, dense music — it locks onto the wrong
# metrical level (observed: 123 BPM read on a genuine ~180 BPM metal song),
# which derails both the single-tempo and the dynamic sync. Isolated DRUMS are
# by far the cleanest beat signal, so when the user has already run "Separar
# instrumentos" (Demucs htdemucs_6s), the tempo-critical detection runs on the
# drum stem instead of the mix. The 6-stem pass already produces drums.wav (a
# sibling of the guitar stem we keep in params["stems"]); it's just omitted from
# the playback list, so we can locate and reuse it with no extra separation.


def _drum_stem(params: dict[str, Any]) -> Path | None:
    """The isolated drum stem for beat/tempo detection, if a Demucs separation
    already produced one for this job — else None (fall back to the full mix).
    Derived as the sibling drums.wav of the stored guitar stem (one htdemucs_6s
    pass writes both), so no separate bookkeeping is needed."""
    stems = params.get("stems")
    if not isinstance(stems, dict):
        return None
    guitar = stems.get("guitar")
    if not isinstance(guitar, str) or not guitar:
        return None
    drums = Path(guitar).with_name("drums.wav")
    return drums if drums.exists() else None


@app.post("/jobs/{job_id}/export-gp", response_model=ExportGpOut)
def export_gp(job_id: str, payload: ExportGpIn) -> ExportGpOut:
    """Write the accepted tempo corrections into a COPY of the job's Guitar Pro
    file, so the correction is permanent in Guitar Pro itself and not only in
    RockForge. The uploaded original is never modified.

    Returns a report of what was actually written — the binary formats store
    tempo as an integer, so a recommendation of 119.085 lands as 119, and the
    user is told rather than quietly handed a different tempo. Fetch the file
    from ``GET /jobs/{id}/corrected-gp``."""
    with _session_factory() as session:
        job = _job_or_404(session, job_id)
        if job.source_type != "gp":
            raise HTTPException(422, "Guitar Pro export only applies to Guitar Pro jobs")
        params = dict(job.params or {})
        gp_path = Path(str(params.get("gp_path") or ""))
    if not gp_path.exists():
        raise HTTPException(409, "the Guitar Pro file no longer exists on the work volume")
    if not payload.corrections:
        raise HTTPException(422, "no tempo corrections to write")

    from rockforge.domain.errors import IngestionError
    from rockforge.infrastructure.gpexport.tempo_writer import (
        TempoCorrection,
        write_tempo_corrections,
    )

    out_dir = settings.work_dir / job_id
    out_dir.mkdir(parents=True, exist_ok=True)
    dst = out_dir / f"corrected{gp_path.suffix.lower()}"
    try:
        applied = write_tempo_corrections(
            gp_path,
            dst,
            [TempoCorrection(measure=c.measure, bpm=c.bpm) for c in payload.corrections],
        )
    except IngestionError as exc:
        raise HTTPException(422, str(exc)) from exc

    warnings: list[str] = []
    if any(a.rounded for a in applied):
        warnings.append(
            "this Guitar Pro format stores tempo as a whole number, so the "
            "recommended values were rounded — export as .gp (GP7/8) to keep the decimals"
        )
    with _session_factory() as session:
        stored = session.get(Job, job_id)
        if stored is not None:
            stored.params = {**dict(stored.params or {}), "corrected_gp": dst.name}
            session.commit()
    return ExportGpOut(
        filename=dst.name,
        format=gp_path.suffix.lower().lstrip("."),
        size_bytes=dst.stat().st_size,
        applied=[AppliedCorrectionOut(**vars(a) | {"rounded": a.rounded}) for a in applied],
        warnings=warnings,
    )


@app.post("/jobs/{job_id}/export-arrangement-gp", response_model=ExportArrangementGpOut)
def export_arrangement_gp(job_id: str, arrangement: str) -> ExportArrangementGpOut:
    """Generate a NEW Guitar Pro file from one built arrangement.

    The companion to ``/export-gp``, which patches tempo into a copy of the
    user's own file. This one writes what RockForge holds — so the in-app note
    edits and the corrected timeline come out as a real score — at the cost of
    carrying only this arrangement: the original's other tracks and formatting
    are not in it, which the report states every time. Fetch the file from
    ``GET /jobs/{id}/corrected-gp``.
    """
    with _session_factory() as session:
        job = session.get(Job, job_id)
        if job is None or job.status is not JobStatus.COMPLETED or not job.bundle_dir:
            raise HTTPException(404, "arrangements not available")
        if job.source_type != "gp":
            raise HTTPException(422, "Guitar Pro export only applies to Guitar Pro jobs")
        bundle = Path(job.bundle_dir)

    from rockforge.domain.errors import IngestionError
    from rockforge.infrastructure.gpexport.arrangement_writer import write_arrangement_gp5
    from rockforge.infrastructure.rsxml.reader import read_arrangement_xml

    path = bundle / f"arrangement_{arrangement.lower().replace(' ', '_')}.xml"
    if not path.is_file():
        raise HTTPException(404, f"no built arrangement named {arrangement!r}")
    try:
        arr = read_arrangement_xml(path)
    except (OSError, ValueError) as exc:
        raise HTTPException(422, f"could not read the built arrangement: {exc}") from exc

    out_dir = settings.work_dir / job_id
    dst = out_dir / "corrected.gp5"
    try:
        report = write_arrangement_gp5(arr, dst, track_name=arrangement)
    except IngestionError as exc:
        raise HTTPException(422, str(exc)) from exc

    with _session_factory() as session:
        job = session.get(Job, job_id)
        if job is not None:
            job.params = {**dict(job.params or {}), "corrected_gp": dst.name}
            session.commit()
    return ExportArrangementGpOut(
        filename=dst.name,
        arrangement=arrangement,
        measures=report.measures,
        notes_written=report.notes_written,
        notes_dropped=report.notes_dropped,
        quantized=report.quantized,
        max_shift_ms=round(report.max_shift_s * 1000, 1),
        warnings=report.warnings,
    )


@app.get("/jobs/{job_id}/corrected-gp")
def get_corrected_gp(job_id: str) -> FileResponse:
    """Download the last Guitar Pro file written by ``/export-gp`` (tempo
    patched into a copy of the user's own file) or by
    ``/export-arrangement-gp`` (a new file carrying one built arrangement).
    Both record their own filename, so the most recent export is served."""
    with _session_factory() as session:
        job = _job_or_404(session, job_id)
        name = str((job.params or {}).get("corrected_gp") or "")
        title = job.title or "song"
    if not name:
        raise HTTPException(404, "no corrected Guitar Pro file has been exported yet")
    path = settings.work_dir / job_id / name
    if not path.exists():
        raise HTTPException(404, "the corrected file is no longer on the work volume")
    # The title reaches a Content-Disposition header, so keep it to characters
    # that cannot break the header or escape a directory.
    safe = "".join(c for c in title if c.isalnum() or c in " -_").strip() or "song"
    return FileResponse(path, filename=f"{safe}_synced{path.suffix}")


@app.post("/jobs/{job_id}/detect-tempo", response_model=DetectTempoOut)
def detect_tempo(job_id: str, payload: DetectTempoIn) -> DetectTempoOut:
    """Measure the recording's tempo from ``from_s`` onward (librosa) and return a
    factor to re-tempo the chart's following notes to it. This is a
    proposal the user previews in the tab viewer before rebuilding."""
    with _session_factory() as session:
        job = _job_or_404(session, job_id)
        if job.source_type != "gp":
            raise HTTPException(422, "tempo detection only applies to Guitar Pro jobs")
        gp_path = Path(str((job.params or {}).get("gp_path", "")))
        src = Path(job.source)
        params = dict(job.params or {})
    if not gp_path.exists():
        raise HTTPException(409, "the Guitar Pro file no longer exists on the work volume")
    if not src.exists():
        raise HTTPException(409, "source audio no longer exists on the work volume")

    from rockforge.application.gp_pipeline import suggest_tempo_scale
    from rockforge.infrastructure.gpimport.parser import inspect_gp
    from rockforge.infrastructure.rhythm.librosa_adapter import detect_tempo_from

    gp_bpm = float(inspect_gp(gp_path).tempo)
    # The factor is applied by the viewer as a RELATIVE stretch of the tail of the
    # already-displayed timeline, so it must be measured against the tempo that
    # timeline currently plays at — not against the GP header tempo. Using the
    # header was wrong twice over: it ignores the song's own tempo changes (a
    # section authored slower than bar 1 got "corrected" by that whole
    # difference), and it ignores the tempo_scale/anchors already applied, so
    # correcting the same passage twice applied the same absolute factor again
    # and compounded into a chart running far too fast.
    reference_bpm = (
        float(payload.chart_bpm) if payload.chart_bpm and payload.chart_bpm > 0 else gp_bpm
    )
    drums = _drum_stem(params)
    try:
        detected_bpm = detect_tempo_from(drums or src, payload.from_s, reference_bpm)
    except ImportError as exc:
        raise _ml_extra_missing("beat detection", exc) from exc
    except Exception as exc:
        raise HTTPException(422, f"could not analyse the recording: {exc}") from exc
    return DetectTempoOut(
        gp_bpm=gp_bpm,
        reference_bpm=reference_bpm,
        detected_bpm=detected_bpm,
        suggested_factor=suggest_tempo_scale(reference_bpm, detected_bpm),
        used_drum_stem=drums is not None,
    )


@app.post("/jobs/{job_id}/detect-tuning", response_model=DetectTuningOut)
def detect_tuning(job_id: str) -> DetectTuningOut:
    """Estimate the recording's fine-tuning deviation from A440 (librosa) for
    GP jobs. String/drop tuning is taken from the GP file and is NOT detected
    here (no production-grade solution from polyphonic audio — see
    librosa_adapter). This is a proposal: the suggested cent_offset fills the
    "Desvio da afinação" field and is applied by the normal rebuild."""
    with _session_factory() as session:
        job = _job_or_404(session, job_id)
        if job.source_type != "gp":
            raise HTTPException(422, "tuning detection only applies to Guitar Pro jobs")
        src = Path(job.source)
    if not src.exists():
        raise HTTPException(409, "source audio no longer exists on the work volume")

    from rockforge.infrastructure.rhythm.librosa_adapter import estimate_tuning_cents

    try:
        cents = estimate_tuning_cents(src)
    except ImportError as exc:
        raise _ml_extra_missing("tuning detection", exc) from exc
    except Exception as exc:
        raise HTTPException(422, f"could not analyse the recording: {exc}") from exc
    return DetectTuningOut(suggested_cent_offset=cents)


class AlignLineIn(BaseModel):
    #: Where the line is believed to start (un-padded recording clock); None
    #: for plain lyrics with no timing at all.
    time: Finite | None = Field(default=None, ge=0)
    text: str = Field(max_length=500)


class DetectLyricsIn(BaseModel):
    """Optional: KNOWN lyrics to place on the recording instead of transcribing."""

    align_lines: list[AlignLineIn] = Field(default_factory=list, max_length=2000)
    #: WhisperX alignment-model language; guessed from the words when omitted.
    language: str | None = Field(default=None, pattern=r"^[a-z]{2,3}$")


@app.post("/jobs/{job_id}/detect-lyrics", response_model=JobOut, status_code=202)
def detect_lyrics_endpoint(job_id: str, payload: DetectLyricsIn | None = None) -> JobOut:
    """Kick off asynchronous lyric detection (Demucs vocal isolation + WhisperX
    forced alignment) on the job's source recording. Slow — poll
    GET /jobs/{job_id}/lyrics for the result. Never overwrites a completed
    build's status; progress is tracked via params["lyrics_status"].

    With ``align_lines`` (lyrics found on LRCLIB, or already in the editor) the
    same task ALIGNS those words to the vocals instead of transcribing — the
    text is right by construction, only the timing is measured."""
    with _session_factory() as session:
        job = _job_or_404(session, job_id)
        # Detection is source-type-agnostic (operates on job.source, the
        # recording). "gp" is the only type the app creates today; the
        # long-removed "youtube" URL-ingestion type is gone from the set.
        if job.source_type not in {"gp", "upload"}:
            raise HTTPException(422, "lyric detection is not supported for this job's source")
        if not Path(job.source).exists():
            raise HTTPException(409, "source recording no longer exists on the work volume")
        params = dict(job.params or {})
        params["lyrics_status"] = "detecting"
        params.pop("lyrics_align", None)
        lines = [ln for ln in (payload.align_lines if payload else []) if ln.text.strip()]
        if lines:
            from rockforge.infrastructure.lyrics_lookup import guess_language

            assert payload is not None
            params["lyrics_align"] = {
                "lines": [{"time": ln.time, "text": ln.text.strip()} for ln in lines],
                "language": payload.language
                or guess_language(" ".join(ln.text for ln in lines)),
            }
        job.params = params
        session.commit()
        _enqueue_detect(job)
        return _to_out(job)


class LyricsCandidateOut(BaseModel):
    id: int
    track: str
    artist: str
    album: str
    duration: float | None
    synced: str | None
    plain: str | None
    instrumental: bool


class LyricsLookupOut(BaseModel):
    candidates: list[LyricsCandidateOut]
    searched_title: str = ""
    searched_artist: str = ""


@app.get("/lyrics-lookup", response_model=LyricsLookupOut)
def lyrics_lookup(title: str = "", artist: str = "", duration: float = 0.0) -> LyricsLookupOut:
    """Lyrics candidates from LRCLIB for the user to choose — nothing is written
    until they pick one. ``duration`` (the recording's length) ranks the entry
    of the same edit first. LRCLIB unreachable is a 502. See
    ``infrastructure/lyrics_lookup.py``."""
    from rockforge.infrastructure.album_lookup import primary_artist, search_title
    from rockforge.infrastructure.lyrics_lookup import LyricsLookupError, search_lyrics

    if not title.strip() or not artist.strip():
        raise HTTPException(422, "title and artist are required to look up lyrics")
    try:
        found = search_lyrics(
            title, artist, duration if math.isfinite(duration) and duration > 0 else None
        )
    except LyricsLookupError as exc:
        raise HTTPException(502, str(exc)) from exc
    return LyricsLookupOut(
        candidates=[LyricsCandidateOut(**vars(c)) for c in found],
        searched_title=search_title(title),
        searched_artist=primary_artist(artist),
    )


class LyricsParseIn(BaseModel):
    text: str = Field(max_length=200_000)
    offset_s: Finite = 0.0


class LyricsParseOut(BaseModel):
    events: list[LyricEventOut]


@app.post("/lyrics/parse", response_model=LyricsParseOut)
def parse_lyrics_text(payload: LyricsParseIn) -> LyricsParseOut:
    """LRC/UltraStar text → the editor's per-word events (with ``offset_s``
    added). The same parser the build uses for an uploaded LRC, so what the
    editor shows is what the build would have made of the file."""
    from rockforge.infrastructure.rsxml.vocals import parse_lyrics

    events = [e for e in parse_lyrics(payload.text, payload.offset_s) if e.time >= 0]
    if not events:
        raise HTTPException(422, "no timed lines in that text (it has no LRC timestamps)")
    return LyricsParseOut(
        events=[LyricEventOut(time=e.time, length=e.length, lyric=e.lyric) for e in events]
    )


# NOTE: these three detection-status polls (/lyrics, /detected-tones, /stems)
# read job.params, which deserializes the whole JSON column. A dedicated
# *_status column was considered (to avoid that on each ~few-second poll) and
# deliberately NOT added: each endpoint also RETURNS payload that lives in
# params (the events + log, the detected-tones blob, the stem names + log), so
# params is loaded regardless — a status column would save nothing here while
# duplicating the status into a second source of truth to keep in sync (exactly
# the params-copy trap documented in CLAUDE.md). Revisit only if a status-ONLY
# poll path is ever added under real Postgres concurrency.
@app.get("/jobs/{job_id}/lyrics", response_model=LyricsOut)
def get_lyrics(job_id: str) -> LyricsOut:
    """Current lyric-detection status and events (raw, before pad_start_s shift
    for GP jobs). Used by the in-app lyrics editor."""
    with _session_factory() as session:
        job = _job_or_404(session, job_id)
        params = job.params or {}
        status = str(params.get("lyrics_status", "none"))
        rows = cast("list[dict[str, object]]", params.get("lyrics_events") or [])

        def _num(v: object) -> float:
            return float(v) if isinstance(v, (int, float, str)) else 0.0

        events = [
            LyricEventOut(
                time=_num(r.get("time", 0.0)),
                length=_num(r.get("length", 0.0)),
                lyric=str(r.get("lyric", "")),
            )
            for r in rows
        ]
        # No edited/detected events yet: fall back to lyrics supplied with the
        # job (LRC/UltraStar TXT upload), so the editor and tab view show
        # what will actually be used at build time.
        if not events:
            lrc_text = params.get("lrc_text")
            if isinstance(lrc_text, str) and lrc_text.strip():
                from rockforge.infrastructure.rsxml.vocals import parse_lyrics

                events = [
                    LyricEventOut(time=e.time, length=e.length, lyric=e.lyric)
                    for e in parse_lyrics(lrc_text)
                ]
        log = cast("list[str]", params.get("lyrics_log") or [])
        return LyricsOut(
            status=status, events=events, log=[str(line) for line in log],
            follow_chart=_lyrics_follow_chart(params),
        )


def _lyrics_follow_chart(params: dict[str, Any]) -> bool:
    """Whether the lyric rows are timed on the score (and so must move with its
    sync corrections) rather than to the recording. Set by whoever filled the
    rows; a job from before the flag existed follows the chart when its lyrics
    came from the GP file and not from an LRC or a detection."""
    if "lyrics_follow_chart" in params:
        return bool(params["lyrics_follow_chart"])
    return (
        bool(params.get("gp_has_lyrics"))
        and not params.get("lrc_text")
        and params.get("lyrics_status") != "ready"
    )


class VocalNoteOut(BaseModel):
    time: float
    length: float
    midi: int | None = None


class VocalLineOut(BaseModel):
    notes: list[VocalNoteOut]
    gp_has_lyrics: bool = False


@app.get("/jobs/{job_id}/vocal-line", response_model=VocalLineOut)
def get_vocal_line(job_id: str) -> VocalLineOut:
    """The notes of the track the GP lyrics are sung on, in the lyrics' own
    recording clock, as of the last build — played by the viewer as "Voz
    (sintetizada)" to hear where the words should fall. Empty when the file
    names no such track (or the job was never built)."""
    with _session_factory() as session:
        job = _job_or_404(session, job_id)
        params = job.params or {}
        rows = cast("list[dict[str, Any]]", params.get("vocal_melody") or [])
        notes = []
        for r in rows:
            try:
                midi = r.get("midi")
                notes.append(VocalNoteOut(
                    time=float(r["time"]), length=float(r["length"]),
                    midi=int(midi) if midi is not None else None,
                ))
            except (KeyError, TypeError, ValueError):
                continue  # a malformed row is skipped, never a 500
        return VocalLineOut(notes=notes, gp_has_lyrics=bool(params.get("gp_has_lyrics")))


@app.post("/jobs/{job_id}/detect-tones", response_model=JobOut, status_code=202)
def detect_tones_endpoint(job_id: str) -> JobOut:
    """Kick off asynchronous tone detection (Demucs guitar separation + spectral
    analysis) on the job's source recording.  Slow — poll
    GET /jobs/{job_id}/detected-tones for the result.  Progress is tracked via
    params["tone_detection_status"]; never overwrites a completed build's status."""
    with _session_factory() as session:
        job = _job_or_404(session, job_id)
        if job.source_type not in {"gp", "upload"}:
            raise HTTPException(422, "tone detection is not supported for this job's source")
        if not Path(job.source).exists():
            raise HTTPException(409, "source recording no longer exists on the work volume")
        params = dict(job.params or {})
        params["tone_detection_status"] = "detecting"
        job.params = params
        session.commit()
        _enqueue_detect_tones(job)
        return _to_out(job)


@app.get("/jobs/{job_id}/detected-tones", response_model=DetectTonesOut)
def get_detected_tones(job_id: str) -> DetectTonesOut:
    """Current tone-detection status and suggested presets."""
    with _session_factory() as session:
        job = _job_or_404(session, job_id)
        params = job.params or {}
        status = str(params.get("tone_detection_status", "none"))
        log = cast("list[str]", params.get("tone_detection_log") or [])
        detected = cast("dict[str, Any]", params.get("detected_tones") or {})
        return DetectTonesOut(
            status=status,
            category=str(detected.get("category", "")),
            lead=dict(detected.get("lead", {})),
            rhythm=dict(detected.get("rhythm", {})),
            lead_candidates=list(detected.get("lead_candidates", [])),
            rhythm_candidates=list(detected.get("rhythm_candidates", [])),
            profile=dict(detected.get("profile", {})),
            log=[str(line) for line in log],
            has_timeline=bool(detected.get("timeline")),
        )


@app.get("/jobs/{job_id}/tone-suggestions", response_model=ToneSuggestionsOut)
def get_tone_suggestions(job_id: str) -> ToneSuggestionsOut:
    """A tone for each part of each track: the recording's tone over time (from
    "Detetar tom") read against what each track plays there. Computed from the
    CURRENT build, so its parts and times follow every applied correction. 409
    until the project is built and the detection has measured the tone over
    time. See ``tone_analysis/sections.py``."""
    import xml.etree.ElementTree as ET

    from rockforge.application.gp_pipeline import MIN_LEAD_S
    from rockforge.infrastructure.rsxml.reader import read_arrangement_xml
    from rockforge.infrastructure.tone_analysis.analyzer import WindowProfile
    from rockforge.infrastructure.tone_analysis.sections import TrackChart, plan_tones, segments_for

    with _session_factory() as session:
        job = _job_or_404(session, job_id)
        if job.status is not JobStatus.COMPLETED or not job.bundle_dir:
            raise HTTPException(409, "the project has to be built first")
        params = dict(job.params or {})
        bundle = Path(job.bundle_dir)
    detected = params.get("detected_tones") or {}
    raw = detected.get("timeline") if isinstance(detected, dict) else None
    if not raw:
        raise HTTPException(409, i18n.tr(
            "ainda não há análise do tom ao longo da música — corre «Detetar tom» "
            "(de novo, se correu antes desta versão)",
            "no tone-over-time analysis yet — run «Detect tone» (again, if it ran "
            "before this version)",
        ))
    windows = [
        WindowProfile(t=float(r[0]), gain_level=float(r[1]), brightness=float(r[2]),
                      low_end=float(r[3]), active=bool(r[4]))
        for r in raw if isinstance(r, list) and len(r) >= 5
    ]
    profile_raw = detected.get("profile") if isinstance(detected, dict) else None
    profile = profile_raw if isinstance(profile_raw, dict) else {}
    song = (
        float(profile.get("gain_level", 0.4)),
        float(profile.get("brightness", 0.5)),
        float(profile.get("low_end", 0.5)),
    )

    def _num(key: str) -> float:
        v = params.get(key, 0.0)
        return float(v) if isinstance(v, (int, float, str)) else 0.0

    # The recording sits this much later in the bundle (the build's own pad).
    pad_s = max(0.0, MIN_LEAD_S - _num("offset_s")) + max(0.0, _num("lead_in_s"))
    charts: list[TrackChart] = []
    for xml_path in sorted(bundle.glob("arrangement_*.xml")):
        try:
            root = ET.parse(xml_path).getroot()
            arr = read_arrangement_xml(xml_path)
        except (ET.ParseError, ValueError, OSError):
            continue
        end = max(
            [n.time + n.sustain for n in arr.notes] + [b.time for b in arr.tempo_map.beats] + [0.0]
        )
        charts.append(TrackChart(
            kind=_built_arrangement_kind(xml_path, root),
            notes=arr.notes,
            segments=segments_for(
                [(sec.name, sec.start_time) for sec in arr.sections],
                [b.time for b in arr.tempo_map.beats if b.measure > 0],
                end,
            ),
        ))
    order = [k.value for k in _arrangement_kinds()]
    charts.sort(key=lambda c: order.index(c.kind) if c.kind in order else len(order))
    plans = plan_tones(windows, pad_s, song, charts)
    return ToneSuggestionsOut(
        tracks=[
            TrackTonePlanOut(
                kind=p.kind,
                segments=[
                    ToneSegmentOut(
                        name=g.name, start=g.start, end=g.end, role=g.role,
                        tone_key=g.tone_key, tone_name=g.tone_name, match=g.match,
                        confidence=g.confidence,
                        reasons=[ToneReasonOut(code=r.code, value=r.value) for r in g.reasons],
                        gain=g.gain, brightness=g.brightness, low_end=g.low_end,
                    )
                    for g in p.segments
                ],
                base=p.base, names=p.names,
                changes=[ToneChangeIn(time=t, name=k) for t, k in p.changes],
                tones=p.tones,
            )
            for p in plans
        ],
        timeline=[[round(w.t + pad_s, 3), w.gain_level, 1.0 if w.active else 0.0] for w in windows],
        swaps=_stored_tone_swaps(params),
    )


_MAX_TONE_SWAPS = 32


def _stored_tone_swaps(params: dict[str, Any]) -> dict[str, ToneSwapIn]:
    """The project's stored stand-ins, skipping any entry that no longer reads."""
    out: dict[str, ToneSwapIn] = {}
    raw = params.get("tone_swaps")
    for key, value in (raw.items() if isinstance(raw, dict) else []):
        try:
            out[str(key)] = ToneSwapIn.model_validate(value)
        except ValidationError:
            continue
    return out


class ToneSwapsIn(BaseModel):
    swaps: dict[str, ToneSwapIn] = {}


@app.patch("/jobs/{job_id}/tone-swaps")
def set_tone_swaps(job_id: str, payload: ToneSwapsIn) -> dict[str, Any]:
    """Keep the tones the user picked to stand in for the suggested ones (the
    whole map, replaced), so leaving the project does not lose them. Nothing is
    rebuilt; it lives in `params`, so a fork inherits it. Each stand-in must be
    a real tone (an amp and cabinet the catalogue knows)."""
    from rockforge.infrastructure.packaging.gear.gear_catalogue import tone_from_dict

    if len(payload.swaps) > _MAX_TONE_SWAPS:
        raise HTTPException(422, f"at most {_MAX_TONE_SWAPS} tone swaps")
    for key, swap in payload.swaps.items():
        if not key or len(key) > 200:
            raise HTTPException(422, "a suggested tone key must be 1-200 characters")
        try:
            valid = tone_from_dict(swap.tone) is not None
        except (KeyError, TypeError, ValueError):
            valid = False
        if not valid:
            raise HTTPException(422, i18n.tr(
                f"o tom escolhido para «{key}» não tem amplificador e coluna válidos",
                f"the tone chosen for “{key}” has no valid amp and cabinet",
            ))
    with _session_factory() as session:
        job = _job_or_404(session, job_id)
        params = dict(job.params or {})
        if payload.swaps:
            params["tone_swaps"] = {k: v.model_dump() for k, v in payload.swaps.items()}
        else:
            params.pop("tone_swaps", None)
        job.params = params
        session.commit()
    return {"swaps": {k: v.model_dump() for k, v in payload.swaps.items()}}


@app.post("/jobs/{job_id}/separate-stems", response_model=JobOut, status_code=202)
def separate_stems_endpoint(job_id: str) -> JobOut:
    """Kick off asynchronous per-instrument stem separation (Demucs htdemucs_6s)
    on the job's source recording. Slow — poll GET /jobs/{job_id}/stems for the
    result, then play a stem via GET /jobs/{job_id}/stem/{name}. Progress is
    tracked via params["stems_status"]; never overwrites a completed build.

    Honest limit: Demucs splits by instrument type, so the guitar stem is ALL
    guitars mixed — Lead vs Rhythm cannot be separated from the recording."""
    with _session_factory() as session:
        job = _job_or_404(session, job_id)
        if job.source_type not in {"gp", "upload"}:
            raise HTTPException(422, "stem separation is not supported for this job's source")
        if not Path(job.source).exists():
            raise HTTPException(409, "source recording no longer exists on the work volume")
        params = dict(job.params or {})
        params["stems_status"] = "detecting"
        job.params = params
        session.commit()
        _enqueue_separate_stems(job)
        return _to_out(job)


@app.get("/jobs/{job_id}/stems", response_model=StemsOut)
def get_stems(job_id: str) -> StemsOut:
    """Current stem-separation status and the names of the available stems."""
    with _session_factory() as session:
        job = _job_or_404(session, job_id)
        params = job.params or {}
        status = str(params.get("stems_status", "none"))
        log = cast("list[str]", params.get("stems_log") or [])
        stems = cast("dict[str, Any]", params.get("stems") or {})
        # Only advertise stems whose file still exists on the work volume.
        available = sorted(name for name, p in stems.items() if Path(str(p)).is_file())
        return StemsOut(status=status, stems=available, log=[str(line) for line in log])


@app.get("/jobs/{job_id}/stem/{name}")
def get_stem_audio(job_id: str, name: str) -> FileResponse:
    """Serve a separated instrument stem (guitar/bass/drums/vocals/other/piano)
    for the viewer's audio-source selector. The stems share the normalized
    recording's clock, so the notes still line up when a stem is soloed."""
    with _session_factory() as session:
        job = _job_or_404(session, job_id)
        stems = cast("dict[str, Any]", (job.params or {}).get("stems") or {})
        raw = stems.get(name)
        if raw is None:
            raise HTTPException(404, "stem not found — run POST /separate-stems first")
        audio = Path(str(raw))
        if not audio.is_file():
            raise HTTPException(404, "stem file no longer exists on the work volume")
        media_type = mimetypes.guess_type(audio.name)[0] or "application/octet-stream"
        return FileResponse(audio, media_type=media_type)


def _settings_out() -> SettingsOut:
    from rockforge import runtime_settings
    from rockforge.infrastructure.diagnostics import detected_rocksmith_folder
    from rockforge.interfaces.worker.celery_app import _cuda_known_broken

    repo, ckpt, queries = runtime_settings.banquet_paths()
    return SettingsOut(
        stem_separator=runtime_settings.stem_separator(),
        banquet_repo=str(repo) if repo else "",
        banquet_ckpt=str(ckpt) if ckpt else "",
        banquet_queries=str(queries) if queries else "",
        banquet=runtime_settings.banquet_validation(),
        loudness_target=runtime_settings.loudness_target(),
        gpu_broken=_cuda_known_broken(),
        whisperx_compute_type=runtime_settings.whisperx_compute_type(),
        ml_python=str(runtime_settings.ml_python() or ""),
        ml_python_info=runtime_settings.ml_python_validation(),
        rocksmith_dir=str(runtime_settings.load().get("rocksmith_dir") or ""),
        rocksmith_dir_detected=str(detected_rocksmith_folder() or ""),
    )


class UiLanguageIn(BaseModel):
    lang: str


@app.put("/ui-language")
def set_ui_language(body: UiLanguageIn) -> dict[str, str]:
    """Remember the app's language (Português / English) for what runs outside a
    request — the worker's logs, the desktop window's close dialog. The browser
    keeps its own copy and sends it with every request."""
    from rockforge import runtime_settings

    if not i18n.valid(body.lang):
        raise HTTPException(422, "lang must be a language code such as 'pt' or 'en'")
    runtime_settings.save({**runtime_settings.load(), "ui_language": body.lang})
    return {"lang": body.lang}


@app.get("/settings", response_model=SettingsOut)
def get_settings() -> SettingsOut:
    """App settings editable from the UI (stem-separator backend + Banquet paths).
    Includes per-path readiness so the UI can show which parts are configured."""
    return _settings_out()


@app.post("/settings", response_model=SettingsOut)
def update_settings(body: SettingsIn) -> SettingsOut:
    """Persist the settings (work_dir/settings.json), shared by the worker. An
    empty string clears an override (falls back to the env default). Enabling
    Banquet without valid paths is allowed but flagged not-ready in the response
    (the separation itself then fails gracefully with a clear message)."""
    from rockforge import runtime_settings

    if body.stem_separator not in (None, "", "demucs", "banquet"):
        raise HTTPException(422, "stem_separator must be 'demucs' or 'banquet'")
    updates = dict(runtime_settings.load())
    for key in (
        "stem_separator", "banquet_repo", "banquet_ckpt", "banquet_queries",
        "whisperx_compute_type", "ml_python", "rocksmith_dir",
    ):
        val = getattr(body, key)
        if val is not None:
            updates[key] = val.strip() if isinstance(val, str) else val
    if body.loudness_target is not None:
        updates["loudness_target"] = float(body.loudness_target)
    runtime_settings.save(updates)
    return _settings_out()


@app.post("/gpu-reset", response_model=SettingsOut)
def reset_gpu() -> SettingsOut:
    """Delete the GPU-broken marker so the ML stack (Demucs + WhisperX) retries
    the GPU on the next detection — for after the user fixed their CUDA/cuDNN
    install. Saves them hunting for the hidden marker file in the work dir."""
    from rockforge.interfaces.worker.celery_app import _clear_cuda_broken

    _clear_cuda_broken()
    return _settings_out()


@app.get("/tone-library")
def get_tone_library() -> dict[str, Any]:
    """All tones saved to the cross-project library (work_dir/tone_library.json).
    The UI loads one of these into a project's tone editor to reuse a dialled-in
    gear chain without rebuilding it."""
    from rockforge import tone_library

    return {"tones": tone_library.load()}


@app.post("/tone-library")
def save_tone_to_library(tone: dict[str, Any]) -> dict[str, Any]:
    """Save (or overwrite, by key) one tone in the library. The body is the same
    tone dict the tone editor stores in a job — it must carry an amp and cabinet
    (a tone is meaningless without them) and a key/name to file it under."""
    from rockforge import tone_library
    from rockforge.infrastructure.packaging.gear.gear_catalogue import tone_from_dict

    if tone_from_dict(tone) is None:
        raise HTTPException(422, "a saved tone needs a valid amp and cabinet")
    try:
        tones = tone_library.save_tone(tone)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"tones": tones}


@app.delete("/tone-library/{key}")
def delete_tone_from_library(key: str) -> dict[str, Any]:
    """Remove a tone from the library by its key (a no-op if it isn't there)."""
    from rockforge import tone_library

    return {"tones": tone_library.delete_tone(key)}


class ToneCollectionScanIn(BaseModel):
    folder: str | None = None


def _tone_collection_folder() -> Path | None:
    from rockforge import runtime_settings

    return runtime_settings.rocksmith_dlc_dir()


def _gear_name(gear: object) -> str:
    from rockforge.infrastructure.packaging.gear.gear_catalogue import gear_name

    return gear_name(str(gear.get("key", ""))) if isinstance(gear, dict) else ""


def _tone_collection_status() -> dict[str, Any]:
    from rockforge.i18n import tr
    from rockforge.infrastructure import tone_collection

    status = tone_collection.status()
    if status.get("error") == "psarc":
        status["error"] = tr(
            "Ler os ficheiros .psarc precisa do extra [psarc] "
            "(pip install -e \".[psarc]\").",
            "Reading .psarc files needs the [psarc] extra (pip install -e \".[psarc]\").",
        )
    return status


@app.get("/tone-collection")
def get_tone_collection(
    q: str = "", artist: str = "", offset: int = 0, limit: int = 200,
) -> dict[str, Any]:
    """The tones of every song in the player's Rocksmith dlc folder, as the last
    scan found them (``tone_collection``), filtered by ``q`` and/or one
    ``artist`` and paged — a large library has thousands. Each row is light
    (names only); the full tone is ``/tone-collection/tone``. ``artists`` lists
    every artist of the whole collection, whatever the filter, for the picker."""
    from rockforge.infrastructure import tone_collection

    # The status BEFORE the list: a scan finishing between the two reads would
    # otherwise answer "done" with the list from before it (the next poll
    # would fix it, but a "done" must mean the list is complete).
    status = _tone_collection_status()
    data = tone_collection.load()
    folder = _tone_collection_folder()
    if folder is not None and data.get("folder") not in (None, str(folder)):
        data = {}  # the cache belongs to another folder: nothing scanned here yet
    matched = tone_collection.search(q, data, artist)
    files = data.get("files") or {}
    page = []
    for row in matched[max(0, offset): max(0, offset) + max(1, min(limit, 500))]:
        tone = row["tone"]
        effects = [
            _gear_name(g)
            for slot in ("pre", "post", "racks")
            for g in tone.get(slot) or []
            if isinstance(g, dict)
        ]
        page.append({
            "id": row["id"],
            "name": tone.get("name") or tone.get("key"),
            "key": tone.get("key"),
            "song": row.get("song", ""),
            "artist": row.get("artist", ""),
            "album": row.get("album", ""),
            "arrangements": row.get("arrangements", []),
            "amp": _gear_name(tone.get("amp")),
            "cabinet": _gear_name(tone.get("cabinet")),
            "effects": effects,
            "file": row["file"],
        })
    suggested = tone_collection.suggested_folder()
    return {
        "folder": str(folder) if folder else None,
        "suggested_folder": str(suggested) if suggested else None,
        "status": status,
        "scanned_at": data.get("scanned_at"),
        "files": len(files),
        "unreadable": sum(1 for f in files.values() if isinstance(f, dict) and f.get("error")),
        "tones_total": sum(len((f or {}).get("tones") or []) for f in files.values()),
        "matched": len(matched),
        "artists": tone_collection.artists(data),
        "entries": page,
    }


@app.get("/tone-collection/tone")
def get_tone_collection_tone(id: str) -> dict[str, Any]:
    """One tone of the collection, whole, ready to add to a project or the library."""
    from rockforge.i18n import tr
    from rockforge.infrastructure import tone_collection

    for row in tone_collection.rows():
        if row["id"] == id:
            return {"tone": row["tone"], "song": row.get("song", ""),
                    "artist": row.get("artist", "")}
    raise HTTPException(404, tr(
        "tom não encontrado na coleção", "tone not found in the collection",
    ))


@app.post("/tone-collection/scan", status_code=202)
def scan_tone_collection(body: ToneCollectionScanIn) -> dict[str, Any]:
    """Read the tones of every ``.psarc`` under ``folder`` (or the folder stored
    last time) on a background thread; poll ``GET /tone-collection``. The folder
    is remembered. The archives are only read."""
    from rockforge import runtime_settings
    from rockforge.i18n import tr
    from rockforge.infrastructure import tone_collection

    raw = (body.folder or "").strip().strip('"')
    folder = Path(raw).expanduser() if raw else _tone_collection_folder()
    if folder is None:
        raise HTTPException(422, tr(
            "Indica a pasta dlc do Rocksmith.", "Give the Rocksmith dlc folder.",
        ))
    if not folder.is_dir():
        raise HTTPException(422, tr(
            f"A pasta não existe: {folder}", f"The folder does not exist: {folder}",
        ))
    runtime_settings.save({**runtime_settings.load(), "rocksmith_dlc_dir": str(folder)})
    if not tone_collection.start_scan(folder):
        raise HTTPException(409, tr(
            "Já está a decorrer uma leitura da pasta.", "A scan of the folder is already running.",
        ))
    return {"folder": str(folder), "status": _tone_collection_status()}


@app.get("/jobs/{job_id}/tones")
def get_tones(job_id: str) -> dict[str, Any]:
    """The job's current tone setup (full gear definitions, the base/extra tone
    keys, and the timed changes placed on the partitura). Backs the tone editor."""
    with _session_factory() as session:
        job = _job_or_404(session, job_id)
        params = job.params or {}
        names = params.get("tone_names")
        tones = params.get("tones")
        changes = params.get("tone_changes")
        per_track = params.get("arrangement_tones")
        return {
            "tone_base": params.get("tone_base"),
            "tone_names": list(names) if isinstance(names, list) else [],
            "tones": list(tones) if isinstance(tones, list) else [],
            "tone_changes": list(changes) if isinstance(changes, list) else [],
            # Tracks with their own setup; the rest use the song-level one above.
            "arrangement_tones": dict(per_track) if isinstance(per_track, dict) else {},
        }


@app.get("/jobs/{job_id}/gp-tracks")
def get_gp_tracks(job_id: str) -> dict[str, object]:
    """The GP file's tracks plus the current track→arrangement assignment and
    per-arrangement tuning, so the song settings can re-map them post-creation."""
    from rockforge.infrastructure.gpimport.parser import inspect_gp

    with _session_factory() as session:
        job = _job_or_404(session, job_id)
        if job.source_type != "gp":
            raise HTTPException(422, "not a Guitar Pro job")
        params = dict(job.params or {})
    gp_path = Path(str(params.get("gp_path", "")))
    if not gp_path.exists():
        raise HTTPException(409, "the Guitar Pro file is no longer on the work volume")
    info = inspect_gp(gp_path)
    return {
        "tracks": [
            {"index": t.index, "name": t.name, "string_count": t.string_count,
             "is_percussion": t.is_percussion, "tuning_midi": list(t.tuning_midi)}
            for t in info.tracks
        ],
        "assignment": {
            "lead": params.get("lead_track"), "rhythm": params.get("rhythm_track"),
            "combo": params.get("combo_track"), "alt_lead": params.get("alt_lead_track"),
            "alt_rhythm": params.get("alt_rhythm_track"),
        },
        "tuning_overrides": params.get("tuning_overrides") or {},
    }


def _arrangement_kinds() -> list[Any]:
    from rockforge.domain.arrangement import ArrangementKind

    return list(ArrangementKind)


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


# The GP track each arrangement is built from, as /jobs/gp stores the choice.
_TRACK_PARAM_OF_KIND = {
    "Lead": "lead_track",
    "Rhythm": "rhythm_track",
    "Combined": "combo_track",
    "Alternate Lead": "alt_lead_track",
    "Alternate Rhythm": "alt_rhythm_track",
}


def _track_of_kind(params: dict[str, object], kind: str) -> int | None:
    """The GP track arrangement ``kind`` was built from, as ``gp_pipeline`` assigns
    them: a lone Lead is built as Combined. None when the tracks were auto-picked."""
    assigned = {
        k: v for k, p in _TRACK_PARAM_OF_KIND.items()
        if isinstance(v := params.get(p), int) and not isinstance(v, bool)
    }
    if kind == "Combined" and list(assigned) == ["Lead"]:
        return assigned["Lead"]
    return assigned.get(kind)


@app.get("/jobs/{job_id}/arrangements", response_model=list[ArrangementOut])
def get_arrangements(job_id: str) -> list[ArrangementOut]:
    """Parsed arrangement data for human review (tab viewer, tuning confirmation)."""
    import xml.etree.ElementTree as ET

    with _session_factory() as session:
        job = session.get(Job, job_id)
        if job is None or job.status is not JobStatus.COMPLETED or not job.bundle_dir:
            raise HTTPException(404, "arrangements not available")
        job_params = dict(job.params or {})

    # Per-arrangement tempo scale, falling back to the job-level default.
    raw_default_scale = job_params.get("tempo_scale", 1.0) or 1.0
    default_scale = (
        float(raw_default_scale) if isinstance(raw_default_scale, (int, float, str)) else 1.0
    )
    arr_sync = job_params.get("arrangement_sync") or {}

    raw_note_ov = job_params.get("note_overrides")
    note_ov = raw_note_ov if isinstance(raw_note_ov, dict) else {}

    def committed_note_overrides(kind: str) -> list[NoteOverrideIn]:
        rows = note_ov.get(kind)
        if not isinstance(rows, list):
            return []
        out_rows: list[NoteOverrideIn] = []
        for row in rows:
            if isinstance(row, dict):
                try:
                    out_rows.append(NoteOverrideIn(**row))
                except ValidationError:  # a hand-edited params row; skip it
                    continue
        return out_rows

    def scale_for(kind: str) -> float:
        entry = arr_sync.get(kind) if isinstance(arr_sync, dict) else None
        if isinstance(entry, dict):
            return float(entry.get("tempo_scale", default_scale) or default_scale)
        return default_scale

    raw_estimated = job_params.get("estimated_bars")
    estimated = raw_estimated if isinstance(raw_estimated, dict) else {}

    def estimated_bars_for(kind: str) -> list[int]:
        track = _track_of_kind(job_params, kind)
        bars = estimated.get(str(track)) if track is not None else None
        return [b for b in bars if isinstance(b, int)] if isinstance(bars, list) else []

    synced_kinds = _synced_arrangements(job_params, job.bundle_dir)
    out: list[ArrangementOut] = []
    for xml_path in sorted(Path(job.bundle_dir).glob("arrangement_*.xml")):
        root = ET.parse(xml_path).getroot()
        if root.tag != "song":
            continue  # skip the vocals XML (root <vocals>) — not an instrument tab
        tuning_el = root.find("tuning")
        offsets = (
            [int(tuning_el.get(f"string{i}", "0")) for i in range(6)]
            if tuning_el is not None
            else [0] * 6
        )

        def parse_note(el: ET.Element, chord: bool) -> ArrangementNoteOut:
            techs = [
                t for t in (
                    "hammerOn", "pullOff", "harmonic", "palmMute", "vibrato",
                    "tap", "slap", "pluck", "accent",
                )
                if el.get(t) == "1"
            ]
            bend = el.get("bend", "0")
            try:
                bend_semitones = int(round(float(bend)))
            except ValueError:
                bend_semitones = 0
            if bend_semitones:
                techs.append("bend")
            if el.get("slideTo", "-1") != "-1":
                techs.append("slide")
            slide_to = int(el.get("slideTo", "-1"))
            if slide_to < 0:
                slide_to = int(el.get("slideUnpitchTo", "-1"))
            return ArrangementNoteOut(
                time=float(el.get("time", "0")),
                string=int(el.get("string", "0")),
                fret=int(el.get("fret", "0")),
                sustain=float(el.get("sustain", "0")),
                chord=chord,
                techniques=techs,
                bend_semitones=bend_semitones,
                slide_to=slide_to,
            )

        notes = [parse_note(el, False) for el in root.findall("levels/level/notes/note")]
        # Chords: name each from the pitches its chordNotes actually sound
        # (RockForge stores no authored chord name). pitch = standard open-string
        # MIDI + this arrangement's tuning offset + fret.
        chord_notes: list[ArrangementNoteOut] = []
        for chord_el in root.findall("levels/level/chords/chord"):
            members = [parse_note(el, True) for el in chord_el.findall("chordNote")]
            pitches = [STANDARD_E_MIDI[m.string] + offsets[m.string] + m.fret for m in members]
            cname = name_chord(pitches)
            for m in members:
                m.chord_name = cname
            chord_notes.extend(members)
        all_notes = sorted(notes + chord_notes, key=lambda n: (n.time, n.string))
        kind = _built_arrangement_kind(xml_path, root)
        # Bar downbeats for the viewer's measure numbering: ebeats with a real
        # measure number (>0); off-beats carry measure="-1".
        ebeats = root.findall("ebeats/ebeat")
        bars = [
            BarOut(measure=int(eb.get("measure", "-1")), time=float(eb.get("time", "0")))
            for eb in ebeats
            if int(eb.get("measure", "-1")) > 0
        ]
        if bars and ebeats and int(ebeats[-1].get("measure", "-1")) > 0:
            # The grid ends on the song's closing bar line (``close_beat_grid``):
            # the end of the last bar, not a bar of its own to number or align.
            bars.pop()
        # Every beat (downbeats + off-beats) — the snap grid the tab viewer's
        # note drag quantizes to.
        beats = [float(eb.get("time", "0")) for eb in ebeats]
        # Song-structure markers, for the section editor — the writer always
        # appends a synthetic "noguitar" sentinel at the very end (to mark
        # where the phrase timeline ends); that one is a structural closer,
        # not a user-facing section, so it's excluded here.
        sections = [
            SectionOut(
                time=float(el.get("startTime", "0")),
                name=el.get("name", "?"),
                number=int(el.get("number", "1")),
            )
            for el in root.findall("sections/section")
            if el.get("name") != "noguitar"
        ]
        out.append(
            ArrangementOut(
                kind=kind,
                tuning_offsets=offsets,
                cent_offset=float(root.findtext("centOffset", "0")),
                average_bpm=float(root.findtext("averageTempo", "0")),
                tempo_scale=scale_for(kind),
                note_count=len(notes),
                chord_count=len(root.findall("levels/level/chords/chord")),
                notes=all_notes,
                bars=bars,
                beats=beats,
                sections=sections,
                note_overrides=committed_note_overrides(kind),
                sync_confirmed=kind in synced_kinds,
                estimated_bars=estimated_bars_for(kind),
            )
        )
    # The build's own order (Lead, Rhythm, Combined, the alternates), not the
    # file names' alphabetical one, which put the alternates first.
    order = [k.value for k in _arrangement_kinds()]
    out.sort(key=lambda a: order.index(a.kind) if a.kind in order else len(order))
    # What the game calls each chart ("LEAD 1", "LEAD 2", "RHYTHM") — the same
    # numbering the PSARC's SongPartition carries, so the tabs read as in game.
    from rockforge.domain.arrangement import ArrangementKind, game_names

    known = [a for a in out if a.kind in order]
    for a, name in zip(known, game_names([ArrangementKind(a.kind) for a in known]), strict=True):
        a.game_name = name
    return out


@app.get("/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: str) -> JobOut:
    with _session_factory() as session:
        job = _job_or_404(session, job_id)
        return _to_out(job)


class SyncConfirmedIn(BaseModel):
    confirmed: bool
    # One chart ("Lead", "Alternate Rhythm"…): each track is synchronised on its
    # own. None = the whole song (the checklist's button), i.e. every chart.
    arrangement: str | None = None


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


class SyncMainIn(BaseModel):
    arrangement: str | None = None  # None = no main chart


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


@app.get("/jobs/{job_id}/source-audio")
def get_source_audio(job_id: str) -> FileResponse:
    """The recording, served for the in-app viewer (playback + waveform).

    Prefers the original file (`job.source`, a real path); for a file that has
    moved, or an old row whose source is not a path, falls back to the
    ingested/normalized audio in the job's work dir (normalization doesn't
    change timing, so the notes still line up).
    """
    with _session_factory() as session:
        job = _job_or_404(session, job_id)
        workdir = settings.work_dir / job.id
        candidates: list[Path] = []
        src = Path(job.source)
        if src.is_file():
            candidates.append(src)
        candidates.append(workdir / "normalized.wav")
        candidates.extend(sorted(workdir.glob("input.*")))
        audio = next((c for c in candidates if c.is_file()), None)
        if audio is None:
            raise HTTPException(404, "no playable audio found for this job")
        media_type = mimetypes.guess_type(audio.name)[0] or "application/octet-stream"
        return FileResponse(audio, media_type=media_type)


@app.get("/jobs/{job_id}/bundle")
def download_bundle(job_id: str) -> FileResponse:
    with _session_factory() as session:
        job = session.get(Job, job_id)
        if job is None or job.status is not JobStatus.COMPLETED or not job.bundle_dir:
            raise HTTPException(404, "bundle not available")
        archive = shutil.make_archive(job.bundle_dir, "zip", job.bundle_dir)
        return FileResponse(archive, filename=f"{job.title}-rockforge-bundle.zip")


@app.get("/jobs/{job_id}/psarc")
def download_psarc(job_id: str) -> FileResponse:
    with _session_factory() as session:
        job = session.get(Job, job_id)
        if job is None or not job.psarc_path:
            raise HTTPException(
                404,
                "PSARC not available — Wwise-dependent packing is delegated to DLC Builder; "
                "download the bundle instead",
            )
        return FileResponse(job.psarc_path, filename=Path(job.psarc_path).name)


class PsarcProblemOut(BaseModel):
    code: str
    text: str
    arrangement: str
    count: int
    level: int | None = None  # where it first happens
    time: float | None = None
    detail: str = ""


class PsarcCheckOut(BaseModel):
    ok: bool
    charts: list[str]
    problems: list[PsarcProblemOut]


@app.get("/jobs/{job_id}/psarc-check", response_model=PsarcCheckOut)
def check_psarc(job_id: str) -> PsarcCheckOut:
    """Read the built .psarc back and check every chart in it against the rules
    whose breaking crashed the game before (``psarc/verify.py``). Run on
    request, never stored, so it always describes the file on disk."""
    from rockforge.infrastructure.packaging.psarc.verify import describe, verify_psarc

    with _session_factory() as session:
        job = _job_or_404(session, job_id)
        psarc = job.psarc_path
    if not psarc or not Path(psarc).is_file():
        raise HTTPException(409, i18n.tr("este projeto não tem PSARC", "this project has no PSARC"))
    report = verify_psarc(Path(psarc))
    groups: dict[tuple[str, str], PsarcProblemOut] = {}
    for p in report.problems:
        key = (p.arrangement, p.code)
        if key in groups:
            groups[key].count += 1
            continue
        groups[key] = PsarcProblemOut(
            code=p.code, text=describe(p.code), arrangement=p.arrangement, count=1,
            level=p.level, time=None if p.time is None else round(p.time, 3), detail=p.detail,
        )
    return PsarcCheckOut(ok=report.ok, charts=report.charts, problems=list(groups.values()))


class GameDlcOut(BaseModel):
    dlc_dir: str | None
    folder: str  # the sub-folder RockForge installs into
    target: str | None  # dlc_dir/folder, written by the server's own path rules


@app.get("/game-dlc", response_model=GameDlcOut)
def get_game_dlc() -> GameDlcOut:
    from rockforge.infrastructure import game_install

    dlc = game_install.dlc_folder()
    return GameDlcOut(
        dlc_dir=str(dlc) if dlc else None,
        folder=game_install.SUBFOLDER,
        target=str(dlc / game_install.SUBFOLDER) if dlc else None,
    )


class InstallOut(BaseModel):
    path: str
    removed: str | None
    duplicates: list[str]
    job: JobOut


@app.post("/jobs/{job_id}/install", response_model=InstallOut)
def install_in_game(job_id: str) -> InstallOut:
    """Copy this version's .psarc into the game's dlc folder (``dlc/RockForge``),
    replacing the copy an earlier version of the song installed."""
    from rockforge.infrastructure import game_install

    with _session_factory() as session:
        job = _job_or_404(session, job_id)
        psarc = job.psarc_path
        params = dict(job.params or {})
    if not psarc or not Path(psarc).is_file():
        raise HTTPException(409, i18n.tr("este projeto não tem PSARC", "this project has no PSARC"))
    dlc = game_install.dlc_folder()
    if dlc is None:
        raise HTTPException(404, i18n.tr(
            "não encontrei a pasta dlc do Rocksmith 2014 — indica a pasta do jogo em "
            "Definições → Geral",
            "Rocksmith 2014's dlc folder was not found — set the game folder in "
            "Settings → General",
        ))
    previous = params.get("installed_psarc")
    try:
        result = game_install.install(
            Path(psarc), dlc, Path(previous) if isinstance(previous, str) else None
        )
    except OSError as exc:
        raise HTTPException(409, i18n.tr(
            "não foi possível copiar para {dir} ({error}) — se o jogo está aberto, fecha-o "
            "e tenta outra vez",
            "could not copy into {dir} ({error}) — if the game is open, close it and try "
            "again",
        ).format(dir=dlc, error=exc)) from exc
    with _session_factory() as session:
        job = _job_or_404(session, job_id)
        job.params = {
            **dict(job.params or {}),
            "installed_psarc": str(result.path),
            "installed_from": job_id,
        }
        session.commit()
        out = _to_out(job)
    return InstallOut(
        path=str(result.path),
        removed=str(result.removed) if result.removed else None,
        duplicates=[str(p) for p in result.duplicates],
        job=out,
    )


_COVER_ART_SUFFIXES = {".jpg", ".jpeg", ".png"}


@app.post("/jobs/{job_id}/cover", response_model=JobOut, status_code=202)
def upload_cover_art(job_id: str, file: UploadFile = File(...)) -> JobOut:
    """Upload/replace the album-art image used by the next rebuild (jpg/png).

    Stored as ``<work_dir>/<job_id>/cover<ext>``; referenced via
    ``params["cover_art"]`` and passed through as ``Packager.package(...,
    cover_art=...)``. Does not trigger a rebuild — call ``/rebuild`` after.
    """
    with _session_factory() as session:
        job = _job_or_404(session, job_id)

        suffix = Path(file.filename or "cover").suffix.lower()
        if suffix not in _COVER_ART_SUFFIXES:
            raise HTTPException(415, f"unsupported image format: {suffix or '(none)'}")

        dest = _replace_cover(job, suffix)
        _copy_upload_capped(file, dest)
        _record_cover(job, dest)
        session.commit()
        return _to_out(job)


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


class CoverFromUrlIn(BaseModel):
    url: str = Field(max_length=2000)


@app.post("/jobs/{job_id}/cover-from-url", response_model=JobOut, status_code=202)
def cover_from_url(job_id: str, payload: CoverFromUrlIn) -> JobOut:
    """Use a cover chosen from /album-lookup as the job's album art.

    Only the cover services' own image hosts are fetched from (and redirected
    to), and only a real JPEG/PNG is stored. Like an upload it does not
    rebuild — the next build picks it up.
    """
    from rockforge.infrastructure.album_lookup import (
        AlbumLookupError,
        cover_url_allowed,
        fetch_cover,
    )

    if not cover_url_allowed(payload.url):
        raise HTTPException(422, "url is not from a known cover service")
    with _session_factory() as session:
        job = _job_or_404(session, job_id)
        try:
            data, suffix = fetch_cover(payload.url)
        except AlbumLookupError as exc:
            raise HTTPException(502, str(exc)) from exc
        dest = _replace_cover(job, suffix)
        dest.write_bytes(data)
        _record_cover(job, dest)
        session.commit()
        return _to_out(job)


@app.get("/jobs/{job_id}/cover")
def download_cover_art(job_id: str) -> FileResponse:
    with _session_factory() as session:
        job = session.get(Job, job_id)
        cover_art = (job.params or {}).get("cover_art") if job else None
        if job is None or not cover_art:
            raise HTTPException(404, "no cover art uploaded for this job")
        cover_path = settings.work_dir / job.id / cast(str, cover_art)
        if not cover_path.exists():
            raise HTTPException(404, "cover art file is missing on the work volume")
        media_type = mimetypes.guess_type(cover_path.name)[0] or "application/octet-stream"
        return FileResponse(cover_path, media_type=media_type)


@app.get("/version", include_in_schema=False)
def version() -> dict[str, str]:
    return {"version": app.version}


class RequirementOut(BaseModel):
    """One external dependency and what its absence actually costs."""

    key: str
    name: str
    #: True = present, False = absent, None = NOT CHECKABLE from this process —
    #: a different answer from "absent", and the honest one for the CDLC loader
    #: patch (we do not know where the game is) and for a CUDA build of torch
    #: (only importing it would tell, which the API process must never do).
    found: bool | None
    detail: str
    required: bool
    unlocks: str
    without_it: str
    install: str
    extras: list[str] = []


class SystemCheckOut(BaseModel):
    requirements: list[RequirementOut]
    #: Keys of the required dependencies that are missing — the app cannot
    #: produce anything at all while this is non-empty.
    missing_required: list[str]


@app.get("/system-check", response_model=SystemCheckOut)
def system_check() -> SystemCheckOut:
    """What external software this machine has, and what each gap costs.

    RockForge ships almost none of its dependencies — Wwise cannot legally be
    redistributed, the ML stack is gigabytes, ffmpeg is better taken from the
    system. Each already degrades cleanly on its own, but the symptom always
    surfaces downstream and reads as a bug ("o PSARC não é jogável"), so this
    is the one place that names the cause instead.
    """
    from rockforge.infrastructure import diagnostics
    from rockforge.interfaces.worker.celery_app import _cuda_known_broken

    reqs = diagnostics.check_requirements(settings, gpu_broken=_cuda_known_broken())
    return SystemCheckOut(
        requirements=[RequirementOut(**vars(r)) for r in reqs],
        missing_required=[r.key for r in diagnostics.missing_required(reqs)],
    )


@app.get("/gear-catalogue")
def gear_catalogue() -> dict[str, Any]:
    """The Rocksmith gear catalogue (amps/cabinets/pedals/racks + descriptors)
    that backs the tone-builder UI. Static data — safe to cache client-side."""
    from rockforge.infrastructure.packaging.gear.gear_catalogue import catalogue_for_ui

    return catalogue_for_ui()


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


@app.get("/gear-image/{key}")
def gear_image(key: str) -> FileResponse:
    """Serve a gear image for the tone editor, if one exists.

    Looks first in ``work_dir/gear_images/<key>.<ext>`` (the user's own
    override) then the bundled ``web/gear_images/<key>.<ext>`` shipped in the
    repo. 404 when absent in both; the UI then falls back to the generic panel.
    The key is sanitised to a bare slug so it can't escape the folder."""
    slug = "".join(c for c in key if c.isalnum() or c in "-_")
    if not slug:
        raise HTTPException(404, "no such gear image")
    for folder in _gear_image_dirs():
        for ext in (".png", ".jpg", ".jpeg", ".webp"):
            candidate = folder / f"{slug}{ext}"
            if candidate.is_file():
                media = (
                    "image/jpeg" if ext in (".jpg", ".jpeg") else f"image/{ext[1:]}"
                )
                return FileResponse(candidate, media_type=media)
    raise HTTPException(404, "no gear image for this key")


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
