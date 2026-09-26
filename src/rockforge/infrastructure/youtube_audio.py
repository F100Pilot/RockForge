"""The audio of ONE YouTube video, fetched with yt-dlp — for Songsterr's bar times.

Songsterr's per-measure times belong to a specific YouTube video, so the
recording that lines up with them is that video's own audio. Asking the user
to convert it by hand was the one manual step left in "paste a Songsterr link,
get a synced chart", and the user asked for it to go. This fetches exactly
what ``teaqu/guitar-pro-youtube-sync`` fetches, with the same tool (yt-dlp),
and nothing else: one video, by its 11-character id, audio only.

- **yt-dlp is an optional extra** (``pip install -e ".[youtube]"``), found the
  same way the ML stages find their interpreter: this process's own module
  when it has one, else a ``yt-dlp`` program on PATH, else the configured ML
  Python (``ml_python``) — so the standalone ``.exe`` works with any of them.
  It is run as a SUBPROCESS, never imported here, and gets no stdin (the hard
  rule for console tools).
- **Only a video id goes in**, validated to ``[A-Za-z0-9_-]{11}``, and becomes
  a ``youtu.be`` URL we build; no client URL is ever handed to the tool.
- **YouTube often refuses anonymous downloads** (HTTP 403 / "Sign in to
  confirm"). yt-dlp can reuse the login of a browser on this machine
  (``--cookies-from-browser``); the browser name is checked against a fixed
  list. The reference tool offers the same retry.
- The best audio stream is kept AS IS (m4a preferred, no re-encode); the
  build's ffmpeg normalisation reads any of them.

Downloading from YouTube is against YouTube's terms of service except where
YouTube offers it; like the reference tool, this is for personal use with
music the user is entitled to. Never run against YouTube from here (the
sandbox blocks it) — tested with a fake runner.
"""

from __future__ import annotations

import importlib.util
import re
import shutil
import subprocess
import sys
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

from rockforge.domain.errors import IngestionError

VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
COOKIE_BROWSERS = ("chrome", "firefox", "edge", "brave", "safari", "opera", "vivaldi", "chromium")
DOWNLOAD_TIMEOUT_S = 600
MAX_FILESIZE = "300M"
# The stored name starts with this, which is also what /jobs/gp checks a token
# against: only files this module wrote can be claimed as a recording.
FILE_PREFIX = "yt-"


class YouTubeAudioError(IngestionError):
    """The audio could not be fetched; ``needs_cookies`` when YouTube wants a login."""

    def __init__(self, message: str, *, needs_cookies: bool = False) -> None:
        super().__init__(message)
        self.needs_cookies = needs_cookies


class YtDlpMissingError(YouTubeAudioError):
    """No yt-dlp to run."""


def _has_module(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def ytdlp_command() -> list[str] | None:
    """How to run yt-dlp here, or None when there is none to run."""
    if not getattr(sys, "frozen", False) and _has_module("yt_dlp"):
        return [sys.executable, "-m", "yt_dlp"]
    exe = shutil.which("yt-dlp")
    if exe:
        return [exe]
    from rockforge.infrastructure import ml_python

    configured = ml_python.configured()
    if configured is not None:
        return [str(configured), "-m", "yt_dlp"]
    return None


def build_args(
    base: list[str], video_id: str, template: Path, cookies_browser: str | None
) -> list[str]:
    """The full yt-dlp command line for one video's audio."""
    if not VIDEO_ID.match(video_id):
        raise YouTubeAudioError("identificador de vídeo do YouTube inválido")
    args = [
        *base,
        "--no-playlist", "--no-progress", "--no-warnings",
        "-f", "bestaudio[ext=m4a]/bestaudio/best",
        "--max-filesize", MAX_FILESIZE,
        "-o", str(template),
        "--print", "after_move:filepath",
    ]
    if cookies_browser:
        if cookies_browser not in COOKIE_BROWSERS:
            raise YouTubeAudioError(f"browser desconhecido: {cookies_browser}")
        args += ["--cookies-from-browser", cookies_browser]
    return [*args, f"https://youtu.be/{video_id}"]


_LOGIN_HINTS = ("403", "sign in to confirm", "confirm you’re not a bot",
                "confirm you're not a bot", "cookies")


def download_audio(
    video_id: str,
    dest_dir: Path,
    *,
    cookies_browser: str | None = None,
    command: list[str] | None = None,
    run: Callable[..., Any] = subprocess.run,
) -> Path:
    """Fetch a video's audio into ``dest_dir``; returns the stored file."""
    base = command if command is not None else ytdlp_command()
    if base is None:
        raise YtDlpMissingError(
            "o yt-dlp não está instalado — instala com pip install yt-dlp "
            "(ou pip install -e \".[youtube]\") e tenta de novo"
        )
    dest_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{FILE_PREFIX}{uuid.uuid4()}"
    args = build_args(base, video_id, dest_dir / f"{stem}.%(ext)s", cookies_browser)
    try:
        proc = run(args, capture_output=True, text=True, stdin=subprocess.DEVNULL,
                   timeout=DOWNLOAD_TIMEOUT_S)
    except subprocess.TimeoutExpired as exc:
        raise YouTubeAudioError("o download do áudio demorou demasiado") from exc
    except OSError as exc:
        raise YtDlpMissingError(f"não consegui executar o yt-dlp ({exc})") from exc
    if proc.returncode != 0:
        tail = (proc.stderr or "").strip().splitlines()[-3:]
        message = " / ".join(tail) or f"o yt-dlp terminou com o código {proc.returncode}"
        needs_cookies = any(h in message.lower() for h in _LOGIN_HINTS)
        raise YouTubeAudioError(message, needs_cookies=needs_cookies)
    # The file it reports, but only if it really is ours, in dest_dir.
    reported = [ln.strip() for ln in (proc.stdout or "").splitlines() if ln.strip()]
    candidates = [Path(p) for p in reported[-1:]] + sorted(dest_dir.glob(f"{stem}.*"))
    for c in candidates:
        if c.is_file() and c.parent.resolve() == dest_dir.resolve() and c.name.startswith(stem):
            return c
    raise YouTubeAudioError("o yt-dlp terminou mas não encontrei o ficheiro de áudio")
