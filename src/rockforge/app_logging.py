"""The technical log: what happened, when, where — never the user's secrets.

``<work_dir>/logs/rockforge.log`` (the API) and ``rockforge-worker.log`` (a
Celery worker, a process of its own), each rotated at ``MAX_BYTES`` with
``BACKUPS`` older copies kept — about 12 MB at most, whatever the app does.
Every line: time, level, component (the logger's name), the request it belongs
to when there is one, and the message. The level is ``ROCKFORGE_LOG_LEVEL``
(INFO by default).

Redacted before anything is written (``redact``): the API token, HTTP
credentials (``Authorization``, cookies), ``password=``/``token=`` values, and
the user's home folder and account name in paths. A path to a song is useful
to diagnose a problem; the name of the person's Windows account is not.

This log records what was OBSERVED. It does not decide anything: a bug is a
bug once someone triages it into tracking/bugs.json (docs/VERSIONING.md).

Logging must never break the app: ``logging.raiseExceptions`` is off (a full
disk drops a line instead of raising into a request), and ``configure`` gives
up quietly when the folder cannot be written.
"""

from __future__ import annotations

import contextvars
import logging
import logging.handlers
import os
import platform
import re
import sys
from pathlib import Path

MAX_BYTES = 2_000_000
BACKUPS = 5
FORMAT = "%(asctime)s %(levelname)-7s [%(name)s] %(request)s%(message)s"
_HANDLER_NAME = "rockforge-file"

# The request a line belongs to (set by the API's middleware), shown as "[ab12cd34] ".
request_id: contextvars.ContextVar[str] = contextvars.ContextVar("rockforge_request_id",
                                                                 default="")

_SECRET_PATTERNS = [
    (re.compile(r"(?i)\b(authorization|proxy-authorization)(\s*[:=]\s*)(\S+\s+)?\S+"),
     r"\1\2<redacted>"),
    (re.compile(r"(?i)\b(cookie|set-cookie)(\s*[:=]\s*)\S+"), r"\1\2<redacted>"),
    (re.compile(r"(?i)\b(password|passwd|token|api[_-]?key|secret)(\s*[:=]\s*)[^\s&,;'\"]+"),
     r"\1\2<redacted>"),
    (re.compile(r"(?i)\b(basic|bearer)\s+[A-Za-z0-9+/=._-]{8,}"), r"\1 <redacted>"),
]
_USER_IN_PATH = re.compile(r"(?i)([\\/](?:users|home)[\\/])[^\\/\s'\"]+")


def _secrets() -> list[str]:
    try:
        from rockforge import config

        token = config.settings.api_token
    except Exception:  # noqa: BLE001 — no settings, nothing extra to hide
        token = None
    return [token] if token else []


def redact(text: str) -> str:
    """The text with secrets and the account name taken out."""
    for value in _secrets():
        text = text.replace(value, "<redacted>")
    for pattern, repl in _SECRET_PATTERNS:
        text = pattern.sub(repl, text)
    home = str(Path.home())
    if len(home) > 3:
        text = text.replace(home, "~")
    return _USER_IN_PATH.sub(r"\1<user>", text)


class _RedactingFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        rid = request_id.get()
        record.request = f"[{rid}] " if rid else ""
        return redact(super().format(record))


def log_dir(work_dir: Path) -> Path:
    return Path(work_dir) / "logs"


def configure(work_dir: Path, *, level: str = "INFO", file_name: str = "rockforge.log",
              loggers: tuple[str, ...] = ("", "uvicorn")) -> Path | None:
    """Send the named loggers (the root, and uvicorn's own, which does not
    propagate) to the rotating file. Calling it again replaces the handler, so a
    reload never writes every line twice. Returns the file, or None when it
    cannot be written."""
    logging.raiseExceptions = False
    path = log_dir(work_dir) / file_name
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        handler = logging.handlers.RotatingFileHandler(
            path, maxBytes=MAX_BYTES, backupCount=BACKUPS, encoding="utf-8", delay=True)
    except OSError:
        return None
    handler.name = _HANDLER_NAME
    handler.setFormatter(_RedactingFormatter(FORMAT))
    numeric = logging.getLevelName(level.upper()) if isinstance(level, str) else level
    if not isinstance(numeric, int):
        numeric = logging.INFO
    for name in loggers:
        logger = logging.getLogger(name)
        for old in [h for h in logger.handlers if h.name == _HANDLER_NAME]:
            logger.removeHandler(old)
            old.close()
        logger.addHandler(handler)
        if not name:
            logger.setLevel(numeric)
    return path


def startup_lines(component: str) -> list[str]:
    """What identifies a run: the build, the system, how it was started."""
    from rockforge.build_info import summary

    lines = [f"{component} starting — {summary()}",
             f"Python {platform.python_version()} on {platform.platform()}"
             + (" (frozen .exe)" if getattr(sys, "frozen", False) else "")]
    mode = os.environ.get("ROCKFORGE_WORKER_MODE")
    if mode:
        lines.append(f"worker mode {mode}")
    return lines


def tail(path: Path, lines: int = 80) -> list[str]:
    """The last lines of a log (already redacted when written; redacted again
    in case it was written by an older version)."""
    try:
        with path.open("rb") as fh:
            fh.seek(0, os.SEEK_END)
            size = fh.tell()
            fh.seek(max(0, size - 64_000))
            data = fh.read().decode("utf-8", errors="replace")
    except OSError:
        return []
    return [redact(line) for line in data.splitlines()[-lines:]]
