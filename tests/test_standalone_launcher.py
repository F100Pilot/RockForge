"""The standalone launcher's decisions, without a GUI.

`start_standalone.py` is shipped code that nothing used to look at — the same
gap that let the PyInstaller spec ship an .exe with no `app.js` (see
`test_standalone_spec.py`). None of this needs pywebview installed: every
decision is a plain function, and the GUI-shaped ones take their dependency as
an argument.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import start_standalone as launcher  # noqa: E402


def test_importing_the_launcher_touches_nothing() -> None:
    """The environment is configured in a FUNCTION, not at import: it has to be
    set before anything imports `rockforge.config` (pydantic-settings reads the
    environment once, at import), and a module that did it on the way in could
    not be tested — nor imported by anything else — without side effects."""
    import importlib

    before = dict(__import__("os").environ)
    importlib.reload(launcher)
    assert dict(__import__("os").environ) == before


def test_windowed_mode_disables_the_idle_shutdown_watchdog(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The watchdog infers "the user left" from missing heartbeats, which a
    backgrounded tab also stops sending — a whole guard exists for that. A
    window close is unambiguous, so the window drives shutdown instead and the
    watchdog would only race it."""
    monkeypatch.delenv("ROCKFORGE_IDLE_SHUTDOWN_S", raising=False)
    monkeypatch.delenv("ROCKFORGE_WORKER_MODE", raising=False)

    launcher.configure_environment(windowed=True)
    import os

    assert os.environ["ROCKFORGE_IDLE_SHUTDOWN_S"] == "0"
    assert os.environ["ROCKFORGE_WORKER_MODE"] == "inprocess", "no Redis in the .exe"


def test_browser_fallback_keeps_the_watchdog(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ROCKFORGE_IDLE_SHUTDOWN_S", raising=False)
    launcher.configure_environment(windowed=False)
    import os

    assert os.environ["ROCKFORGE_IDLE_SHUTDOWN_S"] == "30"


def test_an_explicit_setting_is_never_overridden(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`setdefault`, not assignment — a user's own ROCKFORGE_* or .env wins."""
    monkeypatch.setenv("ROCKFORGE_IDLE_SHUTDOWN_S", "120")
    monkeypatch.setenv("ROCKFORGE_WORKER_MODE", "celery")
    launcher.configure_environment(windowed=True)
    import os

    assert os.environ["ROCKFORGE_IDLE_SHUTDOWN_S"] == "120"
    assert os.environ["ROCKFORGE_WORKER_MODE"] == "celery"


def test_closing_with_nothing_running_does_not_interrogate_the_user() -> None:
    asked: list[tuple[str, str]] = []

    def confirm(title: str, message: str) -> bool:
        asked.append((title, message))
        return False

    assert launcher.should_close_now(False, confirm) is True
    assert asked == [], "an idle app must just close"


def test_closing_mid_build_asks_and_obeys_the_answer() -> None:
    """In `inprocess` mode the worker runs in the API's OWN process, so exiting
    aborts the build and leaves the job stuck at RUNNING. The user is right
    there, so ask — don't silently discard the work, and don't refuse to close
    (a 20-minute separation would trap them)."""
    asked: list[tuple[str, str]] = []

    def refuse(title: str, message: str) -> bool:
        asked.append((title, message))
        return False

    assert launcher.should_close_now(True, refuse) is False
    assert len(asked) == 1
    assert "trabalho" in asked[0][1].lower()

    assert launcher.should_close_now(True, lambda *_: True) is True


def test_work_in_flight_is_false_when_the_worker_cannot_be_reached(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Refusing to close the window because a status check broke would be worse
    than closing, so every failure reads as idle."""
    monkeypatch.setitem(sys.modules, "rockforge.interfaces.worker.inprocess", None)
    assert launcher.work_in_flight() is False


def test_wait_until_serving_gives_up_instead_of_hanging(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The window must never open on a connection error, and a failed start must
    surface rather than hang forever."""
    import socket

    def refuse(*_a: Any, **_k: Any) -> Any:
        raise OSError("nothing listening")

    monkeypatch.setattr(socket, "create_connection", refuse)
    clock = iter([0.0, 0.5, 1.5, 9.9])
    assert launcher.wait_until_serving(
        "127.0.0.1", 1, timeout_s=1.0, now=lambda: next(clock), sleep=lambda _s: None
    ) is False


def test_wait_until_serving_returns_as_soon_as_the_port_answers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import socket

    class _Sock:
        def __enter__(self) -> _Sock:
            return self

        def __exit__(self, *_exc: object) -> None:
            return None

    monkeypatch.setattr(socket, "create_connection", lambda *_a, **_k: _Sock())
    assert launcher.wait_until_serving("127.0.0.1", 1, now=lambda: 0.0) is True


def test_bundled_ffmpeg_goes_to_the_front_of_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The .exe ships its own ffmpeg; a system copy must not shadow it."""
    monkeypatch.setenv("PATH", "/usr/bin")
    (tmp_path / "ffmpeg").mkdir()
    assert launcher.add_bundled_ffmpeg_to_path(tmp_path) is True
    import os

    assert os.environ["PATH"].split(os.pathsep)[0] == str(tmp_path / "ffmpeg")


def test_no_bundled_ffmpeg_leaves_path_alone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PATH", "/usr/bin")
    assert launcher.add_bundled_ffmpeg_to_path(tmp_path) is False
    import os

    assert os.environ["PATH"] == "/usr/bin"


def test_a_windowed_build_always_has_somewhere_to_log(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A windowed PyInstaller build has NO stdout/stderr, so a crash with no log
    is unreportable. The work dir is the normal home for it; if settings cannot
    even load, a temp file still has to come back."""
    written = launcher.default_log_path()
    assert written.name == "rockforge.log"

    import builtins

    real_import = builtins.__import__

    def explode(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "rockforge.config":
            raise RuntimeError("settings are broken")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", explode)
    monkeypatch.delitem(sys.modules, "rockforge.config", raising=False)
    fallback = launcher.default_log_path()
    monkeypatch.undo()
    assert fallback.name == "rockforge.log"


def test_redirect_sends_both_streams_to_the_file(tmp_path: Path) -> None:
    log = tmp_path / "sub" / "rockforge.log"
    real_out, real_err = sys.stdout, sys.stderr
    try:
        launcher.redirect_output_to_log(log)
        print("hello")
        print("bad", file=sys.stderr)
        sys.stdout.flush()
    finally:
        sys.stdout.close()
        sys.stdout, sys.stderr = real_out, real_err
    body = log.read_text(encoding="utf-8")
    assert "hello" in body and "bad" in body


def test_port_falls_back_when_the_override_is_nonsense(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ROCKFORGE_PORT", raising=False)
    assert launcher.port() == launcher.DEFAULT_PORT
    monkeypatch.setenv("ROCKFORGE_PORT", "9123")
    assert launcher.port() == 9123
    monkeypatch.setenv("ROCKFORGE_PORT", "not-a-port")
    assert launcher.port() == launcher.DEFAULT_PORT


class _FakeEvent:
    """pywebview's `closing` event: `+=` registers a handler, and a handler
    returning False vetoes the close (webview/event.py collects return values
    and cancels on any False)."""

    def __init__(self) -> None:
        self.handlers: list[Any] = []

    def __iadd__(self, handler: Any) -> _FakeEvent:
        self.handlers.append(handler)
        return self


class _FakeWindow:
    def __init__(self, title: str, url: str, **kwargs: Any) -> None:
        self.title, self.url, self.kwargs = title, url, kwargs
        self.events = type("Events", (), {})()
        self.events.closing = _FakeEvent()
        self.confirmed: list[tuple[str, str]] = []

    def create_confirmation_dialog(self, title: str, message: str) -> bool:
        self.confirmed.append((title, message))
        return True


def _fake_webview(monkeypatch: pytest.MonkeyPatch, *, start_raises: bool = False) -> Any:
    import types

    module = types.ModuleType("webview")
    made: list[_FakeWindow] = []

    def create_window(title: str, url: str, **kwargs: Any) -> _FakeWindow:
        window = _FakeWindow(title, url, **kwargs)
        made.append(window)
        return window

    def start(*_a: Any, **_k: Any) -> None:
        if start_raises:
            raise RuntimeError("no GUI backend")

    module.create_window = create_window  # type: ignore[attr-defined]
    module.start = start  # type: ignore[attr-defined]
    module.windows = made  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "webview", module)
    return module


class _FakeServer:
    def __init__(self) -> None:
        self.should_exit = False


def _stub_server(monkeypatch: pytest.MonkeyPatch) -> _FakeServer:
    """Replace the uvicorn thread — the API is exercised everywhere else; what
    is under test here is that the window starts it and then stops it."""
    import threading

    server = _FakeServer()
    thread = threading.Thread(target=lambda: None)
    thread.start()
    monkeypatch.setattr(launcher, "_serve_in_background", lambda *_a: (server, thread))
    monkeypatch.setattr(launcher, "wait_until_serving", lambda *_a, **_k: True)
    return server


def test_the_window_opens_on_the_local_api_and_stops_the_server_on_close(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    webview = _fake_webview(monkeypatch)
    server = _stub_server(monkeypatch)

    assert launcher.run_windowed("127.0.0.1", 8123) is True
    window = webview.windows[0]
    assert window.url == "http://127.0.0.1:8123"
    assert window.title == launcher.WINDOW_TITLE
    # Graceful, so the lifespan teardown runs and `inprocess.shutdown()` with it.
    assert server.should_exit is True


def test_the_close_handler_is_wired_to_the_work_in_flight_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The registered handler is what actually protects a running build: a
    window that closed unconditionally would abort it and leave the job at
    RUNNING, which is the same failure `_should_shutdown(work_in_flight)`
    exists to prevent on the browser path."""
    webview = _fake_webview(monkeypatch)
    _stub_server(monkeypatch)
    launcher.run_windowed("127.0.0.1", 8123)
    window = webview.windows[0]
    assert len(window.events.closing.handlers) == 1, "nothing guards the close"
    handler = window.events.closing.handlers[0]

    monkeypatch.setattr(launcher, "work_in_flight", lambda: False)
    assert handler() is True
    assert window.confirmed == [], "an idle app closes without asking"

    monkeypatch.setattr(launcher, "work_in_flight", lambda: True)
    assert handler() is True  # the fake dialog answers yes
    assert len(window.confirmed) == 1, "a busy app must ask first"


def test_a_window_that_cannot_start_falls_back_to_the_browser(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """pywebview importing is not proof its backend works — no WebView2 runtime,
    no display. The port must be released, or the fallback cannot bind it."""
    _fake_webview(monkeypatch, start_raises=True)
    server = _stub_server(monkeypatch)
    assert launcher.run_windowed("127.0.0.1", 8123) is False
    assert server.should_exit is True, "the port must not stay held"


def test_a_server_that_never_comes_up_releases_the_port_too(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fake_webview(monkeypatch)
    server = _stub_server(monkeypatch)
    monkeypatch.setattr(launcher, "wait_until_serving", lambda *_a, **_k: False)
    assert launcher.run_windowed("127.0.0.1", 8123) is False
    assert server.should_exit is True
