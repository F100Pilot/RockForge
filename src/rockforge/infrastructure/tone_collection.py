"""The tones of every song in the player's Rocksmith ``dlc`` folder.

DLC Builder's tone collection lists the tones of the songs a player already
has, so a tone heard in game can be reused. Every song's per-arrangement
manifest (``manifests/<…>/<key>_<arr>.json`` inside its ``.psarc``) carries its
``Tones`` as ``ToneDto`` dicts — the same shape ``tone_dto.py`` writes — so
reading them back needs only the archive's TOC and those small manifests
(``container.read_entries``), never its audio. Official DLC, the on-disc
``songs.psarc`` and CDLC all use that one layout.

Each archive is read once: the result is cached in
``work_dir/tone_collection.json`` by path, size and modification time, so a
rescan only opens files that are new or changed. The archives are only ever
read. A scan runs on a background thread in the API process (it is plain file
I/O, minutes for a large library, no ML) and reports its progress through
:func:`status`.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import tempfile
import threading
import time
import unicodedata
from collections.abc import Callable
from pathlib import Path
from typing import Any

from rockforge import config

logger = logging.getLogger(__name__)

_PEDAL_SLOTS = (("PrePedal", "pre"), ("PostPedal", "post"), ("Rack", "racks"))
_SAVE_EVERY = 25

_lock = threading.Lock()
_status: dict[str, Any] = {"state": "idle", "done": 0, "total": 0, "current": "", "error": ""}
_thread: threading.Thread | None = None


def _file() -> Path:
    return config.settings.work_dir / "tone_collection.json"


def suggested_folder() -> Path | None:
    """Where Steam installs Rocksmith 2014's ``dlc`` folder by default, when it
    exists on this machine (a library on another drive is not searched)."""
    home = Path.home()
    roots = [
        Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")) / "Steam",
        Path(os.environ.get("PROGRAMFILES", r"C:\Program Files")) / "Steam",
        home / "Library" / "Application Support" / "Steam",
        home / ".steam" / "steam",
        home / ".local" / "share" / "Steam",
    ]
    for root in roots:
        candidate = root / "steamapps" / "common" / "Rocksmith2014" / "dlc"
        if candidate.is_dir():
            return candidate
    return None


def _gear(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    key = raw.get("Key") or raw.get("PedalKey")
    if not key:
        return None
    knobs = raw.get("KnobValues")
    if not isinstance(knobs, dict):
        knobs = {}
    return {"key": str(key), "knobs": {str(k): float(v) for k, v in knobs.items()}}


def tone_from_dto(dto: Any) -> dict[str, Any] | None:
    """A Rocksmith ``ToneDto`` (as a manifest carries it) as the tone dict the
    tone editor and ``gear_catalogue.tone_from_dict`` use, or None when it has
    no amp/cabinet the catalogue knows. ``Volume`` is a string in manifests
    (``"-19.5"``) and a number in some older tools; both are read. Pedals stay in
    their slot (PrePedal2 is the second pre-pedal)."""
    from rockforge.infrastructure.packaging.gear.gear_catalogue import tone_from_dict

    if not isinstance(dto, dict) or not isinstance(dto.get("GearList"), dict):
        return None
    gear = dto["GearList"]
    key = str(dto.get("Key") or dto.get("Name") or "").strip()
    if not key:
        return None
    try:
        volume = float(dto.get("Volume"))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        volume = -18.0
    tone: dict[str, Any] = {
        "key": key,
        "name": str(dto.get("Name") or key),
        "volume": volume,
        "descriptors": [str(d) for d in dto.get("ToneDescriptors") or []],
        "amp": _gear(gear.get("Amp")),
        "cabinet": _gear(gear.get("Cabinet")),
    }
    for prefix, slot in _PEDAL_SLOTS:
        tone[slot] = [_gear(gear.get(f"{prefix}{i}")) for i in range(1, 5)]
    try:
        if tone_from_dict(tone) is None:
            return None
    except (KeyError, TypeError, ValueError):
        return None
    return tone


def read_psarc_tones(path: Path) -> dict[str, Any]:
    """``{"tones": [...], "skipped": n}`` for one archive — every distinct tone
    (by key) of its songs, with the song, artist, album and the arrangements
    that use it — or ``{"error": message}`` when it cannot be read."""
    from rockforge.infrastructure.packaging.psarc.container import read_entries

    try:
        manifests = read_entries(
            path, lambda name: name.startswith("manifests/") and name.endswith(".json")
        )
    except ImportError:
        raise
    except Exception as exc:  # noqa: BLE001 — one bad archive must not stop the scan
        return {"error": f"{type(exc).__name__}: {exc}"}
    by_key: dict[str, dict[str, Any]] = {}
    skipped = 0
    for raw in manifests.values():
        try:
            doc = json.loads(raw.decode("utf-8-sig"))
        except (UnicodeDecodeError, ValueError):
            continue
        entries = doc.get("Entries") if isinstance(doc, dict) else None
        for entry in (entries or {}).values():
            attrs = entry.get("Attributes") if isinstance(entry, dict) else None
            if not isinstance(attrs, dict):
                continue
            arrangement = str(attrs.get("ArrangementName") or "")
            for dto in attrs.get("Tones") or []:
                tone = tone_from_dto(dto)
                if tone is None:
                    skipped += 1
                    continue
                row = by_key.setdefault(tone["key"], {
                    "tone": tone,
                    "song": str(attrs.get("SongName") or ""),
                    "artist": str(attrs.get("ArtistName") or ""),
                    "album": str(attrs.get("AlbumName") or ""),
                    "arrangements": [],
                })
                if arrangement and arrangement not in row["arrangements"]:
                    row["arrangements"].append(arrangement)
    return {"tones": list(by_key.values()), "skipped": skipped}


def _psarcs(folder: Path) -> list[Path]:
    """Every ``.psarc`` under ``folder``, minus a Mac copy (``_m``) of a song
    whose PC copy (``_p``) is beside it — the same song, the same tones."""
    found = sorted(p for p in folder.rglob("*") if p.is_file() and p.suffix.lower() == ".psarc")
    names = {p.name.lower() for p in found}
    return [
        p for p in found
        if not (p.stem.lower().endswith("_m") and f"{p.stem[:-2]}_p.psarc".lower() in names)
    ]


def load() -> dict[str, Any]:
    try:
        data = json.loads(_file().read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def _write(data: dict[str, Any]) -> None:
    f = _file()
    f.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=f.parent, prefix=f.name + ".", suffix=".tmp")
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(data, ensure_ascii=False))
        os.replace(tmp, f)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def scan(folder: Path, progress: Callable[[int, int, str], None] | None = None) -> dict[str, Any]:
    """Read every archive under ``folder`` not already cached with the same size
    and modification time, drop the ones that are gone, and store the result.
    A scan of a different folder starts from nothing."""
    cache = load()
    previous = cache.get("files") if cache.get("folder") == str(folder) else None
    previous = previous if isinstance(previous, dict) else {}
    paths = _psarcs(folder)
    files: dict[str, Any] = {}
    for i, path in enumerate(paths, start=1):
        rel = path.relative_to(folder).as_posix()
        if progress:
            progress(i - 1, len(paths), rel)
        st = path.stat()
        old = previous.get(rel)
        if isinstance(old, dict) and old.get("size") == st.st_size \
                and old.get("mtime") == st.st_mtime:
            files[rel] = old
        else:
            files[rel] = {"size": st.st_size, "mtime": st.st_mtime, **read_psarc_tones(path)}
        if i % _SAVE_EVERY == 0:  # a scan cut short keeps what it read
            _write({"folder": str(folder), "files": {**previous, **files}})
    data = {"folder": str(folder), "scanned_at": time.time(), "files": files}
    _write(data)
    if progress:
        progress(len(paths), len(paths), "")
    return data


def status() -> dict[str, Any]:
    with _lock:
        return dict(_status)


def _set(**values: Any) -> None:
    with _lock:
        _status.update(values)


def start_scan(folder: Path) -> bool:
    """Scan ``folder`` on a background thread; False when one is already running."""
    global _thread
    with _lock:
        if _thread is not None and _thread.is_alive():
            return False
        _status.update(state="scanning", done=0, total=0, current="", error="")

        def run() -> None:
            try:
                scan(folder, lambda done, total, current: _set(
                    done=done, total=total, current=current))
                _set(state="done", current="")
            except ImportError:
                _set(state="error", error="psarc")
            except Exception as exc:  # noqa: BLE001 — reported to the UI, not raised
                logger.warning("tone collection scan failed", exc_info=True)
                _set(state="error", error=f"{type(exc).__name__}: {exc}")

        _thread = threading.Thread(target=run, name="tone-collection-scan", daemon=True)
        _thread.start()
    return True


def _fold(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", text.casefold()) if not unicodedata.combining(c)
    )


def tone_id(rel: str, key: str) -> str:
    return hashlib.sha1(f"{rel}\n{key}".encode()).hexdigest()[:16]


def rows(data: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Every cached tone as one row (with its archive and a stable id), sorted
    by artist, song and tone name."""
    data = load() if data is None else data
    out: list[dict[str, Any]] = []
    for rel, info in (data.get("files") or {}).items():
        for row in (info or {}).get("tones") or []:
            tone = row.get("tone") or {}
            out.append({**row, "file": rel, "id": tone_id(rel, str(tone.get("key", "")))})
    out.sort(key=lambda r: (
        _fold(r.get("artist", "")), _fold(r.get("song", "")),
        _fold(str((r.get("tone") or {}).get("name", ""))),
    ))
    return out


def artists(data: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Every artist in the collection with how many songs and tones it has,
    sorted by name. Spellings that differ only in case or accents ("Motörhead",
    "MOTORHEAD") are one artist, shown as its most common spelling."""
    groups: dict[str, dict[str, Any]] = {}
    for row in rows(data):
        name = str(row.get("artist", "")).strip()
        if not name:
            continue
        group = groups.setdefault(_fold(name), {"spellings": {}, "songs": set(), "tones": 0})
        group["spellings"][name] = group["spellings"].get(name, 0) + 1
        group["songs"].add(_fold(str(row.get("song", ""))))
        group["tones"] += 1
    return [
        {"name": max(g["spellings"], key=g["spellings"].get), "songs": len(g["songs"]),
         "tones": g["tones"]}
        for _, g in sorted(groups.items())
    ]


def search(
    query: str, data: dict[str, Any] | None = None, artist: str = "",
) -> list[dict[str, Any]]:
    """The rows whose song, artist, album, tone name or gear contain every word
    of ``query`` (case and accents ignored), and — when ``artist`` is given —
    that are that artist's (the whole name, case and accents ignored)."""
    words = _fold(query).split()
    wanted = _fold(artist.strip())
    found = [
        r for r in rows(data)
        if not wanted or _fold(str(r.get("artist", "")).strip()) == wanted
    ]
    if not words:
        return found

    def haystack(row: dict[str, Any]) -> str:
        tone = row.get("tone") or {}
        gear = [tone.get("amp"), tone.get("cabinet"),
                *(tone.get("pre") or []), *(tone.get("post") or []), *(tone.get("racks") or [])]
        parts = [row.get("song", ""), row.get("artist", ""), row.get("album", ""),
                 str(tone.get("name", "")), str(tone.get("key", "")),
                 *(str(g.get("key", "")) for g in gear if isinstance(g, dict))]
        return _fold(" ".join(parts))

    return [r for r in found if all(w in haystack(r) for w in words)]
