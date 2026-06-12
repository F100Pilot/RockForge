"""Audio tag extraction (ID3/Vorbis/MP4) via tinytag (MIT licence).

Used to prefill title/artist/album/year from the uploaded file; user-supplied
form values always take precedence, and missing values are surfaced as a 422
asking the user to fill them in — never silently defaulted.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AudioTags:
    title: str | None = None
    artist: str | None = None
    album: str | None = None
    year: int | None = None


def read_tags(path: Path) -> AudioTags:
    """Best-effort tag read; returns empty AudioTags when the file has none."""
    try:
        from tinytag import TinyTag
    except ImportError:
        return AudioTags()
    try:
        tag = TinyTag.get(str(path))
    except Exception:  # corrupt/unsupported tags must not block the upload
        return AudioTags()

    year: int | None = None
    if tag.year:
        digits = "".join(c for c in str(tag.year)[:4] if c.isdigit())
        year = int(digits) if len(digits) == 4 else None
    return AudioTags(
        title=(tag.title or "").strip() or None,
        artist=(tag.artist or "").strip() or None,
        album=(tag.album or "").strip() or None,
        year=year,
    )
