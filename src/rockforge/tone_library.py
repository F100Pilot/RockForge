"""A cross-project tone library, persisted to ``work_dir/tone_library.json``.

A tone the user builds in one project's tone editor can be saved here and
reloaded into any other project, so a carefully-dialled amp/cabinet/pedal chain
doesn't have to be recreated per song. Entries are the same tone dicts stored in
``Job.params["tones"]`` (the shape ``gear_catalogue.tone_from_dict`` accepts),
identified by the tone's ``key`` — saving a tone whose key already exists
overwrites it.

Persistence mirrors :mod:`rockforge.runtime_settings`: a single JSON file next
to the work dir, atomic writes (temp + ``os.replace``) so a concurrent reader
never sees a truncated file. The library is process-global (not per job), the
same way DLC Builder's tone library is shared across all projects.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from rockforge.config import settings


def _file() -> Path:
    return settings.work_dir / "tone_library.json"


def _tone_key(tone: dict[str, Any]) -> str:
    return str(tone.get("key") or tone.get("name") or "").strip()


def load() -> list[dict[str, Any]]:
    """All saved tones (newest edits kept in insertion order). Never raises."""
    try:
        data = json.loads(_file().read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError, OSError):
        return []
    if not isinstance(data, list):
        return []
    return [t for t in data if isinstance(t, dict) and _tone_key(t)]


def _write(tones: list[dict[str, Any]]) -> list[dict[str, Any]]:
    f = _file()
    f.parent.mkdir(parents=True, exist_ok=True)
    # A UNIQUE temp name, not a fixed "<file>.tmp": the API and the worker both
    # write here, and with a shared name two concurrent writers interleave —
    # A creates it, B overwrites it, A renames it into place and publishes B's
    # content. os.replace is still what makes the swap atomic for readers.
    fd, tmp_name = tempfile.mkstemp(dir=f.parent, prefix=f.name + ".", suffix=".tmp")
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(tones, indent=2, ensure_ascii=False))
        os.replace(tmp, f)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    return tones


def save_tone(tone: dict[str, Any]) -> list[dict[str, Any]]:
    """Upsert ``tone`` by its key; returns the full library. Raises ``ValueError``
    if the tone has no usable key."""
    key = _tone_key(tone)
    if not key:
        raise ValueError("a tone needs a key or name to be saved")
    tones = [t for t in load() if _tone_key(t) != key]
    tones.append(tone)
    return _write(tones)


def delete_tone(key: str) -> list[dict[str, Any]]:
    """Remove the tone with ``key`` (a no-op if absent); returns the library."""
    key = key.strip()
    return _write([t for t in load() if _tone_key(t) != key])
