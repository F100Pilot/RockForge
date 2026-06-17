"""Standalone launcher for RockForge (PyInstaller entry point).

Runs the API + in-process worker in a single process — no Redis, no Celery
worker, no external services except ffmpeg (bundled alongside the .exe).

Environment variables are set before any rockforge import so the config
module picks them up via pydantic-settings.
"""

import os
import sys
import webbrowser

# When running from a PyInstaller bundle, _MEIPASS holds the temp directory
# containing bundled data files. Add the bundled ffmpeg to PATH so subprocess
# calls find it.
_bundle_dir = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
_ffmpeg_dir = os.path.join(_bundle_dir, "ffmpeg")
if os.path.isdir(_ffmpeg_dir):
    os.environ["PATH"] = _ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")

# Force in-process worker mode (no Redis needed).
os.environ.setdefault("ROCKFORGE_WORKER_MODE", "inprocess")
# Idle-shutdown when the browser tab closes (same as start.bat).
os.environ.setdefault("ROCKFORGE_IDLE_SHUTDOWN_S", "30")

HOST = "127.0.0.1"
PORT = int(os.environ.get("ROCKFORGE_PORT", "8000"))


def main() -> None:
    import uvicorn

    print(f"RockForge standalone — opening http://{HOST}:{PORT}")
    webbrowser.open(f"http://{HOST}:{PORT}")
    uvicorn.run(
        "rockforge.interfaces.api.app:app",
        host=HOST,
        port=PORT,
        log_level="info",
    )


if __name__ == "__main__":
    main()
