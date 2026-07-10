"""Generate a DLC Builder project file (``.rs2dlc``) for one-shot import.

The bundle's ``rockforge_project.json`` is RockForge's *own* descriptor — DLC
Builder cannot open it, so the user otherwise has to recreate a project and add
each arrangement XML by hand ("Add Arrangement", one by one). This module emits
the **real** DLC Builder project format instead, so the whole song (every
arrangement, vocals, audio and cover) loads in a single "Open project".

Format reverse-engineered from a real DLC Builder ``.rs2dlc`` plus the
Rocksmith2014.NET source (``Rocksmith2014.DLCProject/DLCProject.fs`` &
``Arrangement.fs``). It is the ``DLCProject.Dto`` serialized with
System.Text.Json + FSharp.SystemTextJson default options:

- Discriminated-union arrangements use the adjacent-tag encoding
  ``{"Case": "Instrumental"|"Vocals"|"Showlights", "Fields": [ {…} ]}``.
- ``null`` members are omitted (``ignoreNull = true``); we mirror that by
  dropping ``None`` values.
- ``SortableString`` is ``{"Value": str, "SortValue": str}``; ``AudioFile`` is
  ``{"Path": str, "Volume": float}``.

Tones: when an arrangement carries full gear definitions (``Arrangement.tones``,
built in the tone editor), they are serialized into the project ``Tones`` array
as ``ToneDto`` objects (``Tone.toDto`` in Rocksmith2014.NET ``Tone.fs``, MIT) so
the tone loads and plays in-game with no further editing. With no gear
definitions, ``Tones`` stays empty and ``BaseTone``/``Tones`` carry bare names
DLC Builder resolves from its own library (the original honest fallback).

Other honest limits (CLAUDE.md): ``Volume`` on the audio file uses a neutral
default (DLC Builder's "Calculate Volumes" recomputes it), and the audio preview
is left empty (DLC Builder's "Create Preview Audio" generates it).
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from random import SystemRandom
from typing import cast

from rockforge.domain.arrangement import Arrangement, ArrangementKind
from rockforge.domain.tone import Tone
from rockforge.infrastructure.packaging.tone_dto import unique_tone_dtos

# ArrangementName / RouteMask integer values from Rocksmith2014.NET Arrangement.fs.
_ARRANGEMENT_NAME = {
    ArrangementKind.LEAD: 0,  # Lead
    ArrangementKind.COMBINED: 1,  # Combo
    ArrangementKind.RHYTHM: 2,  # Rhythm
}
_ROUTE_MASK = {
    ArrangementKind.LEAD: 1,  # RouteMask.Lead
    ArrangementKind.COMBINED: 1,  # combo plays the lead path
    ArrangementKind.RHYTHM: 2,  # RouteMask.Rhythm
}

# Neutral defaults for fields RockForge cannot derive; DLC Builder lets the user
# recompute/author them (see module docstring).
_DEFAULT_VOLUME = 0.0
_DEFAULT_SCROLL_SPEED = 1.3

_rng = SystemRandom()


def _new_guid() -> str:
    """Lowercase hyphenated GUID, matching DLC Builder's ID/PersistentID format."""
    return str(uuid.uuid4())


def _master_id() -> int:
    """A positive 32-bit MasterID, as DLC Builder assigns randomly per arrangement."""
    return _rng.randint(1, 2_000_000_000)


def _sortable(value: str) -> dict[str, str]:
    return {"Value": value, "SortValue": ""}


def _tuning_pitch(cent_offset: float) -> float:
    return round(440.0 * 2 ** (cent_offset / 1200.0), 3)


def _instrumental_dto(arr: Arrangement, xml_name: str) -> dict[str, object]:
    guid = _new_guid()
    # ArrangementPriority: Main=0, Alternative=1, Bonus=2. An alternate arrangement
    # is a non-representative second chart on the same path — encoded as Bonus, the
    # way a decoded DLC Builder CDLC (AAL "Tempting Time" lead2) does it.
    priority = 2 if arr.kind.is_alternate else 0
    return {
        "ID": guid,
        "XML": xml_name,
        "Name": _ARRANGEMENT_NAME[arr.kind.base_kind],
        "RouteMask": _ROUTE_MASK[arr.kind.base_kind],
        "Priority": priority,
        "ScrollSpeed": _DEFAULT_SCROLL_SPEED,
        "BassPicked": False,
        "Tuning": list(arr.tuning.offsets_from_standard()),
        "TuningPitch": _tuning_pitch(arr.tuning.cent_offset),
        "BaseTone": arr.tone_base or "",
        "Tones": list(arr.tone_names),
        "MasterID": _master_id(),
        "PersistentID": guid,
    }


def _collect_tones(arrangements: list[Arrangement]) -> list[dict[str, object]]:
    """Unique ``ToneDto`` dicts across all arrangements, keyed by tone ``key``
    (the same tone shared by Lead/Rhythm is emitted once)."""
    tones: list[Tone] = [tone for arr in arrangements for tone in arr.tones]
    return unique_tone_dtos(tones)


def _vocals_dto(xml_name: str) -> dict[str, object]:
    guid = _new_guid()
    return {
        "ID": guid,
        "XML": xml_name,
        "Japanese": False,
        "MasterID": _master_id(),
        "PersistentID": guid,
    }


def build_rs2dlc(
    arrangements: list[Arrangement],
    instrumental_xml_names: list[str],
    audio_name: str,
    dlc_key: str,
    vocals_xml_name: str | None = None,
    cover_art_name: str | None = None,
) -> dict[str, object]:
    """Build the ``DLCProject.Dto`` dict for ``arrangements`` (parallel to
    *instrumental_xml_names*). Paths are bundle-relative filenames."""
    meta = arrangements[0].metadata

    dto_arrangements: list[dict[str, object]] = [
        {"Case": "Instrumental", "Fields": [_instrumental_dto(arr, xml)]}
        for arr, xml in zip(arrangements, instrumental_xml_names, strict=True)
    ]
    if vocals_xml_name is not None:
        dto_arrangements.append(
            {"Case": "Vocals", "Fields": [_vocals_dto(vocals_xml_name)]}
        )

    project: dict[str, object] = {
        "Version": "1",
        "DLCKey": dlc_key,
        "ArtistName": _sortable(meta.artist),
        "Title": _sortable(meta.title),
        "AlbumName": _sortable(meta.album),
        "Year": meta.year or 0,
        "AlbumArtFile": cover_art_name or "",
        "AudioFile": {"Path": audio_name, "Volume": _DEFAULT_VOLUME},
        "AudioPreviewFile": {"Path": "", "Volume": _DEFAULT_VOLUME},
        "IgnoredIssues": [],
        "Arrangements": dto_arrangements,
        "Tones": _collect_tones(arrangements),
    }
    if meta.song_length > 0:
        project["AudioFileLength"] = round(meta.song_length, 3)
    return project


def _write_phrase_levels(project: dict[str, object], out_dir: Path) -> Path:
    """Write a ``.phrase-levels`` file alongside the ``.rs2dlc``.

    DLC Builder reads this during build (``PhraseLevelComparer.compareToExisting``)
    to decide whether arrangement IDs need regeneration.  Without it, DLC Builder
    may fail with a FileNotFoundException when building the project.  RockForge
    has no dynamic difficulty, so every phrase has maxDifficulty 0.
    """
    levels: dict[str, dict[str, int]] = {}
    arr_list = cast("list[dict[str, object]]", project.get("Arrangements", []))
    for arr_dto in arr_list:
        if arr_dto.get("Case") != "Instrumental":
            continue
        fields = cast("list[dict[str, object]]", arr_dto.get("Fields", []))
        if not fields:
            continue
        persistent_id = cast(str, fields[0].get("PersistentID", ""))
        if persistent_id:
            levels[persistent_id] = {"COUNT": 0, "default": 0, "END": 0}
    path = out_dir / ".phrase-levels"
    path.write_text(json.dumps(levels, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def write_rs2dlc(
    arrangements: list[Arrangement],
    instrumental_xml_names: list[str],
    audio_name: str,
    dlc_key: str,
    out_path: Path,
    vocals_xml_name: str | None = None,
    cover_art_name: str | None = None,
) -> Path:
    """Write a ``.rs2dlc`` DLC Builder project file; returns *out_path*.

    Also writes a ``.phrase-levels`` companion in the same directory so DLC
    Builder's build-time phrase-level comparison works from the first build.
    """
    project = build_rs2dlc(
        arrangements,
        instrumental_xml_names,
        audio_name,
        dlc_key,
        vocals_xml_name=vocals_xml_name,
        cover_art_name=cover_art_name,
    )
    out_path.write_text(
        json.dumps(project, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    _write_phrase_levels(project, out_path.parent)
    return out_path
