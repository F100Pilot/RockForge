"""Audio ingestion: uploaded files and (optionally) YouTube URLs.

YouTube ingestion is DISABLED by default: downloading audio violates the
YouTube Terms of Service (docs/research/03-rocksmith-cdlc.md §7), even though
yt-dlp itself is lawfully distributed. Enabling it is an explicit, logged
configuration decision by the operator, and the responsibility is theirs.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from rockforge.domain.errors import FeatureDisabledError, IngestionError

ALLOWED_SUFFIXES = {".mp3", ".flac", ".wav", ".ogg", ".m4a", ".aiff"}


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
            import yt_dlp
        except ImportError as exc:
            raise IngestionError("yt-dlp not installed (pip install 'rockforge[youtube]')") from exc

        workdir.mkdir(parents=True, exist_ok=True)
        opts = {
            "format": "bestaudio/best",
            "outtmpl": str(workdir / "input.%(ext)s"),
            "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "wav"}],
            "quiet": True,
        }
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([source])
        except Exception as exc:  # yt-dlp raises many error types
            raise IngestionError(f"YouTube download failed: {exc}") from exc
        wav = workdir / "input.wav"
        if not wav.exists():
            raise IngestionError("yt-dlp did not produce expected audio file")
        return wav
