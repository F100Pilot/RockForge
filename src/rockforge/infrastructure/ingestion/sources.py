"""Audio ingestion: uploaded/local files.

Used by the GP pipeline to resolve the recording the arrangement syncs against.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from rockforge.domain.errors import IngestionError

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
