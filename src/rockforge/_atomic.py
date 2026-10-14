"""Atomic file writes shared by the small JSON stores in the work dir."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


def write_text_atomic(path: Path, text: str) -> None:
    """Write ``text`` to ``path`` so a reader sees the old file or the new one,
    never half of it.

    A UNIQUE temp name, not a fixed "<file>.tmp": the API and the worker both
    write these stores, and with a shared name two concurrent writers
    interleave — A creates it, B overwrites it, A renames it into place and
    publishes B's content. ``os.replace`` is what makes the swap atomic."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
