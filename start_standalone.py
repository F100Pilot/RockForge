"""Standalone launcher for RockForge (PyInstaller entry point).

Runs the API + in-process worker in a single process — no Redis, no Celery
worker, no external services except ffmpeg (bundled alongside the .exe).

**It opens a native window, not a browser tab.** pywebview wraps the platform's
own webview (Edge WebView2 on Windows, which ships with the OS), so this costs a
few MB rather than bundling a second browser the way Electron would, and the
whole `web/` UI is served and rendered unchanged. When pywebview is missing or
its backend cannot start, it falls back to the previous behaviour — serve and
open the default browser — so a build without the `[desktop]` extra still works.

A native window also makes shutdown honest: `ROCKFORGE_IDLE_SHUTDOWN_S` exists
only because "the browser tab closed" is ambiguous (see CLAUDE.md), and a window
close is not. Windowed mode therefore disables that watchdog and drives the
shutdown from the window itself, while still refusing to abandon a build or a
separation mid-flight (`should_close_now`).

Nothing here runs at import time: the environment has to be configured before
anything imports `rockforge.config`, and doing that in a function keeps the
module importable from the tests without side effects.
"""

from __future__ import annotations

import contextlib
import os
import sys
import threading
import time
import webbrowser
from collections.abc import Callable
from pathlib import Path
from typing import Any

HOST = "127.0.0.1"
DEFAULT_PORT = 8000
WINDOW_TITLE = "RockForge"
WINDOW_SIZE = (1280, 860)
WINDOW_MIN_SIZE = (900, 600)
# The API is local and in-process, so it is listening within a second or so;
# this ceiling only exists so a failed start surfaces instead of hanging.
READY_TIMEOUT_S = 30.0
READY_POLL_S = 0.1
# Long enough for uvicorn's graceful shutdown (which runs the lifespan teardown,
# and with it `inprocess.shutdown()`), short enough not to hang on exit.
SERVER_STOP_TIMEOUT_S = 10.0


def busy_message() -> str:
    """The close-confirmation text, in the language saved in the settings.
    Imported at call time: nothing may import ``rockforge.config`` before
    ``configure_environment`` has run."""
    from rockforge.i18n import tr

    return tr(
        "RockForge ainda está a trabalhar (a construir, a separar áudio ou a "
        "instalar componentes).\n\n"
        "Se sair agora, esse trabalho é perdido e o job fica por terminar.\n\n"
        "Sair mesmo assim?",
        "RockForge is still working (building, separating audio or installing "
        "components).\n\n"
        "If you quit now, that work is lost and the job is left unfinished.\n\n"
        "Quit anyway?",
    )


def bundle_dir() -> Path:
    """The directory bundled data lives in — `sys._MEIPASS` under PyInstaller,
    the script's own directory otherwise."""
    meipass = getattr(sys, "_MEIPASS", None)
    return Path(meipass) if meipass else Path(__file__).resolve().parent


def add_bundled_ffmpeg_to_path(base: Path | None = None) -> bool:
    """Put the bundled ffmpeg ahead of `$PATH` so subprocess calls find it."""
    ffmpeg_dir = (base or bundle_dir()) / "ffmpeg"
    if not ffmpeg_dir.is_dir():
        return False
    os.environ["PATH"] = str(ffmpeg_dir) + os.pathsep + os.environ.get("PATH", "")
    return True


def add_components_to_path() -> bool:
    """Put the extra components' tools (Deno, for yt-dlp) on PATH. Imported at
    call time: ``components`` reads ``rockforge.config`` only for a fallback
    folder, after ``configure_environment`` has run."""
    if sys.platform != "win32":
        return False
    try:
        from rockforge.infrastructure import components

        return components.add_tools_to_path()
    except Exception:
        return False


def components_flag(argv: list[str]) -> None:
    """The installer's «install the extra components» task starts the app with
    ``--install-components``; the page then installs them by itself."""
    if "--install-components" in argv:
        os.environ["ROCKFORGE_INSTALL_COMPONENTS"] = "1"


# Windows process-creation flags (winbase.h). A console program started from
# this windowless app — ffmpeg, the components' python.exe, nvidia-smi, yt-dlp —
# gets a console window of its own, which flashed black for a moment on every
# button that runs one ("aparece durante uma fração de segundo um ecrã preto").
_CREATE_NO_WINDOW = 0x08000000
# A child that asks for a console of its own, or none at all, is left as asked
# (CREATE_NO_WINDOW is ignored with either, and refused with the first).
_CREATE_NEW_CONSOLE = 0x00000010
_DETACHED_PROCESS = 0x00000008


def hide_child_consoles(popen: Any = None, platform: str | None = None) -> bool:
    """Start every child process without a console window, on Windows.

    Done once, on ``Popen`` itself, rather than at each of the dozen call
    sites (ffmpeg, Demucs, WhisperX, librosa, the probes, yt-dlp, Wwise, the
    components install): a new call site added later is covered too. The
    child still has its own hidden console, so ITS children (pip, ffmpeg run
    by the ML Python) inherit that and stay hidden as well."""
    if (sys.platform if platform is None else platform) != "win32":
        return False
    if popen is None:
        import subprocess

        popen = subprocess.Popen
    if getattr(popen, "_rockforge_no_window", False):
        return True
    original = popen.__init__

    def __init__(self: Any, *args: Any, **kwargs: Any) -> None:
        flags = kwargs.get("creationflags") or 0
        if not flags & (_CREATE_NEW_CONSOLE | _DETACHED_PROCESS):
            kwargs["creationflags"] = flags | _CREATE_NO_WINDOW
        original(self, *args, **kwargs)

    popen.__init__ = __init__
    popen._rockforge_no_window = True
    return True


def configure_environment(*, windowed: bool) -> None:
    """Set the defaults the standalone build runs under, before anything imports
    `rockforge.config` (pydantic-settings reads the environment at import).

    `setdefault`, never assignment: an explicit `ROCKFORGE_*` from the user or a
    `.env` still wins.
    """
    os.environ.setdefault("ROCKFORGE_WORKER_MODE", "inprocess")
    # The idle-shutdown watchdog infers "the user left" from heartbeats, which a
    # backgrounded browser tab stops sending — a whole guard exists for that. A
    # window close is unambiguous, so windowed mode turns the watchdog off and
    # lets the window drive shutdown instead of racing it.
    os.environ.setdefault("ROCKFORGE_IDLE_SHUTDOWN_S", "0" if windowed else "30")


def port() -> int:
    try:
        return int(os.environ.get("ROCKFORGE_PORT", "") or DEFAULT_PORT)
    except ValueError:
        return DEFAULT_PORT


def webview_available() -> bool:
    """Whether the native-window backend can be imported at all.

    Importing is not proof its GUI backend will start (that only fails at
    `webview.start()`, and on a machine without a WebView2 runtime), so `main`
    still falls back if the window itself raises.
    """
    try:
        import webview  # noqa: F401
    except Exception:
        return False
    return True


def redirect_output_to_log(log_path: Path) -> None:
    """Point stdout/stderr at a log file.

    A windowed PyInstaller build (`console=False`) has **no** stdout or stderr —
    they are `None` — and uvicorn's logging writes to them, which raises on the
    first log line. Sending both to a file keeps the app quiet and still leaves
    something to read when it misbehaves.
    """
    log_path.parent.mkdir(parents=True, exist_ok=True)
    stream = open(log_path, "a", encoding="utf-8", buffering=1)  # noqa: SIM115
    sys.stdout = stream
    sys.stderr = stream


def wait_until_serving(
    host: str,
    port_: int,
    *,
    timeout_s: float = READY_TIMEOUT_S,
    poll_s: float = READY_POLL_S,
    now: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> bool:
    """Poll until the API accepts a TCP connection, so the window never opens on
    a connection error."""
    import socket

    deadline = now() + timeout_s
    while now() < deadline:
        try:
            with socket.create_connection((host, port_), timeout=poll_s):
                return True
        except OSError:
            sleep(poll_s)
    return False


def work_in_flight() -> bool:
    """Whether the in-process worker is busy. False on any failure — refusing to
    close a window because a status check broke would be worse than closing."""
    try:
        from rockforge.infrastructure import components
        from rockforge.interfaces.worker import inprocess

        return bool(inprocess.work_in_flight() or components.busy())
    except Exception:
        return False


def should_close_now(busy: bool, confirm: Callable[[str, str], bool]) -> bool:
    """Whether the window may close. Split out from the event handler so the
    decision is testable without a GUI.

    In `inprocess` mode the worker runs in the API's own process, so exiting
    aborts whatever it is doing and leaves that job stuck at RUNNING — the same
    reason `_should_shutdown` takes `work_in_flight`. Here the user is present,
    so the honest move is to ask rather than to block the close or to discard
    their work silently.
    """
    if not busy:
        return True
    return bool(confirm(WINDOW_TITLE, busy_message()))


def _serve_in_background(host: str, port_: int) -> tuple[Any, threading.Thread]:
    """Start uvicorn on a daemon thread and return (server, thread).

    The GUI loop must own the main thread (`webview.start()` requires it), so
    the server is what moves aside. A `Server` instance rather than
    `uvicorn.run` because the window needs a handle to stop it gracefully.
    """
    import uvicorn

    config = uvicorn.Config(
        "rockforge.interfaces.api.app:app", host=host, port=port_, log_level="info"
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, name="rockforge-api", daemon=True)
    thread.start()
    return server, thread


def _stop(server: Any, thread: threading.Thread) -> None:
    """Graceful, so the lifespan teardown runs and the worker pool is closed."""
    server.should_exit = True
    thread.join(timeout=SERVER_STOP_TIMEOUT_S)


def allow_downloads(webview: Any) -> bool:
    """Let the window save files. pywebview CANCELS every download by default
    (``settings['ALLOW_DOWNLOADS'] = False``, edgechromium's
    ``on_download_starting``: ``args.Cancel = True``) — silently, so the
    .psarc/bundle "Download" buttons did nothing at all in the .exe (reported
    by a user). With it on, WebView2 shows the Save As dialog."""
    settings = getattr(webview, "settings", None)
    try:
        settings["ALLOW_DOWNLOADS"] = True  # type: ignore[index]
    except (KeyError, TypeError):
        return False
    return True


def run_windowed(host: str, port_: int) -> bool:
    """Serve and show the native window. Returns False if the window could not
    be created — having released the port, so the browser fallback can bind it."""
    import webview

    allow_downloads(webview)
    server, thread = _serve_in_background(host, port_)
    try:
        if not wait_until_serving(host, port_):
            print(f"RockForge: the API did not start on http://{host}:{port_}")
            return False
        window = webview.create_window(
            WINDOW_TITLE,
            f"http://{host}:{port_}",
            width=WINDOW_SIZE[0],
            height=WINDOW_SIZE[1],
            min_size=WINDOW_MIN_SIZE,
        )
        # `closing` is a cancellable event: returning False vetoes the close.
        window.events.closing += lambda: should_close_now(
            work_in_flight(), window.create_confirmation_dialog
        )
        webview.start()
    except Exception as exc:  # no GUI backend / no WebView2 runtime
        print(f"RockForge: could not open a native window ({exc}); using the browser")
        return False
    finally:
        _stop(server, thread)
    return True


def run_in_browser(host: str, port_: int) -> None:
    """The original behaviour: serve in the foreground, open the default
    browser, and let `ROCKFORGE_IDLE_SHUTDOWN_S` handle the tab closing."""
    import uvicorn

    print(f"RockForge standalone — opening http://{host}:{port_}")
    webbrowser.open(f"http://{host}:{port_}")
    uvicorn.run(
        "rockforge.interfaces.api.app:app", host=host, port=port_, log_level="info"
    )


def default_log_path() -> Path:
    """Where a windowed build writes its output. The work dir, so the log sits
    with everything else the app produces; a temp file if settings cannot even
    be loaded, because a crash with no console and no log is unreportable."""
    try:
        from rockforge.config import settings

        return Path(settings.work_dir) / "rockforge.log"
    except Exception:
        import tempfile

        return Path(tempfile.gettempdir()) / "rockforge.log"


def main() -> None:
    hide_child_consoles()  # before anything can start a child process
    windowed = webview_available()
    configure_environment(windowed=windowed)
    components_flag(sys.argv[1:])
    add_bundled_ffmpeg_to_path()

    if sys.stdout is None or sys.stderr is None:
        # A windowed build has no console to write to; see redirect_output_to_log.
        # An unwritable log must not stop the app from running.
        with contextlib.suppress(OSError):
            redirect_output_to_log(default_log_path())

    add_components_to_path()
    port_ = port()
    if windowed and run_windowed(HOST, port_):
        return
    run_in_browser(HOST, port_)


if __name__ == "__main__":
    # The PDF converter (PDF-to-GP5) parses each file in a child process. In a
    # frozen build that child is this same .exe started again with special
    # arguments; freeze_support() recognises them and runs the child's work
    # instead of opening a second RockForge. It must be the first thing here.
    import multiprocessing

    multiprocessing.freeze_support()
    main()
