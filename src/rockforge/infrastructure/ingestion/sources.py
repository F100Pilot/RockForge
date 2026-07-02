"""Audio ingestion: uploaded files and (optionally) YouTube URLs.

YouTube ingestion is DISABLED by default: downloading audio violates the
YouTube Terms of Service (docs/research/03-rocksmith-cdlc.md §7), even though
yt-dlp itself is lawfully distributed. Enabling it is an explicit, logged
configuration decision by the operator, and the responsibility is theirs.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from rockforge.domain.errors import FeatureDisabledError, IngestionError

ALLOWED_SUFFIXES = {".mp3", ".flac", ".wav", ".ogg", ".m4a", ".aiff"}

# Hard ceiling so a stalled download/extraction fails loudly instead of hanging
# the ingest stage forever (a long song download over a slow link stays well
# under this).
YOUTUBE_TIMEOUT_S = 900


class LocalFileIngestor:
    """Implements AudioIngestor for uploaded files."""

    def fetch(self, source: str, workdir: Path) -> Path:
        src = Path(source)
        if not src.exists():
            raise IngestionError(f"file not found: {source}")
        if src.suffix.lower() not in ALLOWED_SUFFIXES:
            raise IngestionError(
                f"unsupported format '{src.suffix}'; allowed: {sorted(ALLOWED_SUFFIXES)}"
            )
        dest = workdir / f"input{src.suffix.lower()}"
        workdir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        return dest


class YouTubeIngestor:
    """Implements AudioIngestor for YouTube URLs via yt-dlp. Disabled unless opted in."""

    def __init__(self, enabled: bool) -> None:
        self._enabled = enabled

    def fetch(self, source: str, workdir: Path) -> Path:
        if not self._enabled:
            raise FeatureDisabledError(
                "YouTube ingestion is disabled (ROCKFORGE_ENABLE_YOUTUBE=false). "
                "Downloading YouTube audio violates the YouTube ToS; enable only "
                "if you accept that responsibility."
            )
        try:
            import yt_dlp  # noqa: F401  (availability check only; run via subprocess)
        except ImportError as exc:
            raise IngestionError(
                "yt-dlp is not installed. Install the YouTube extra: "
                "py -3.11 -m pip install -e \".[youtube]\"  (or: pip install -U yt-dlp)"
            ) from exc

        workdir.mkdir(parents=True, exist_ok=True)
        # Run yt-dlp as an isolated subprocess (like Demucs/ffmpeg elsewhere):
        # - stdin=DEVNULL so its ffmpeg child can never inherit the worker
        #   console's stdin, go interactive and hang (the documented "stuck at
        #   ingest" symptom — see CLAUDE.md).
        # - --no-playlist so a "watch?v=…&list=…" URL downloads ONE video, not
        #   the whole playlist (which looks like an endless hang).
        # - --socket-timeout + an overall timeout so a stalled network fails
        #   loudly instead of blocking forever.
        cmd = [
            sys.executable, "-m", "yt_dlp",
            "-f", "bestaudio/best",
            "-x", "--audio-format", "wav",
            "--no-playlist",
            "--socket-timeout", "30",
            "--no-progress", "--quiet", "--no-warnings",
            "-o", str(workdir / "input.%(ext)s"),
            source,
        ]
        try:
            subprocess.run(
                cmd, check=True, capture_output=True, text=True,
                stdin=subprocess.DEVNULL, timeout=YOUTUBE_TIMEOUT_S,
            )
        except subprocess.TimeoutExpired as exc:
            raise IngestionError(
                f"YouTube download timed out after {YOUTUBE_TIMEOUT_S}s. If the URL is a "
                "playlist, use a single-video link; otherwise the network stalled."
            ) from exc
        except subprocess.CalledProcessError as exc:
            # YouTube changes its player/signatures often and breaks older yt-dlp
            # builds — an out-of-date yt-dlp is by far the most common cause
            # (HTTP 403, "Unable to extract", "Sign in to confirm…").
            tail = (exc.stderr or "").strip()[-600:]
            raise IngestionError(
                f"YouTube download failed: {tail or '(no output)'}. The most common "
                "cause is an out-of-date yt-dlp — update it: py -3.11 -m pip install -U yt-dlp"
            ) from exc
        wav = workdir / "input.wav"
        if not wav.exists():
            raise IngestionError(
                "yt-dlp ran but produced no audio file — check ffmpeg is installed "
                "(the WAV extraction step needs it) and on PATH."
            )
        return wav
