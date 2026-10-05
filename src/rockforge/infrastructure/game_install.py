"""Copy a built ``.psarc`` into Rocksmith 2014's ``dlc`` folder.

Rebuild → download → copy by hand was the step between every change and the
game. The game folder is already known (Definições → "Pasta do Rocksmith
2014", else the tone collection's dlc folder, else the Steam libraries), so
the copy is one button.

Our files go in ``dlc/RockForge/``: Rocksmith loads ``.psarc`` files from
sub-folders of ``dlc`` (CustomsForge Song Manager organises libraries that
way), and a folder of our own makes it plain which files RockForge put there
— the only ones it will ever delete. The copy is written beside the target
and renamed over it, so the game never sees half a file.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path

SUBFOLDER = "RockForge"


def dlc_folder() -> Path | None:
    """The game's ``dlc`` folder: in the game folder set in Definições, else the
    dlc folder the tone collection was pointed at, else a Steam library's."""
    from rockforge import runtime_settings
    from rockforge.infrastructure.tone_collection import (
        configured_game_folder,
        suggested_folder,
    )

    configured = configured_game_folder()
    if configured is not None:
        return configured / "dlc" if (configured / "dlc").is_dir() else None
    stored = runtime_settings.load().get("rocksmith_dlc_dir")
    if stored and Path(str(stored)).is_dir() and Path(str(stored)).name.lower() == "dlc":
        return Path(str(stored))
    return suggested_folder()


@dataclass(frozen=True)
class InstallResult:
    path: Path
    removed: Path | None
    # Copies of the same file elsewhere in dlc (put there by hand): the game
    # would list the song twice, so the user is told to delete them.
    duplicates: tuple[Path, ...] = ()


def _ours(path: Path, dlc: Path) -> bool:
    """A file RockForge itself installed: a .psarc in our own sub-folder."""
    try:
        return (
            path.suffix.lower() == ".psarc"
            and path.resolve().parent == (dlc / SUBFOLDER).resolve()
        )
    except OSError:
        return False


def install(psarc: Path, dlc: Path, previous: Path | None = None) -> InstallResult:
    """Copy ``psarc`` into ``dlc/RockForge/`` and remove ``previous`` — the copy
    this song had before under another name (its title changed, so its key
    did) — when it is one of ours and not the file just written."""
    target_dir = dlc / SUBFOLDER
    target_dir.mkdir(parents=True, exist_ok=True)
    dest = target_dir / psarc.name
    partial = target_dir / f".{psarc.name}.part"
    try:
        shutil.copyfile(psarc, partial)
        os.replace(partial, dest)
    finally:
        partial.unlink(missing_ok=True)
    removed: Path | None = None
    if (
        previous is not None
        and previous.is_file()
        and _ours(previous, dlc)
        and previous.resolve() != dest.resolve()
    ):
        previous.unlink()
        removed = previous
    duplicates = tuple(
        p for p in dlc.rglob(psarc.name)
        if p.is_file() and p.resolve() != dest.resolve()
    )
    return InstallResult(path=dest, removed=removed, duplicates=duplicates)
