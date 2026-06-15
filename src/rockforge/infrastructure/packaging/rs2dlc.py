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

Honest limits (CLAUDE.md): RockForge has no tone-gear model, so ``Tones`` is
emitted empty and instrumentals carry an empty ``BaseTone`` — DLC Builder shows
a "tone missing" issue the user resolves with its tone library. ``Volume`` uses
a neutral default (DLC Builder's "Calculate Volumes" recomputes it), and the
audio preview is left empty (DLC Builder's "Create Preview Audio" generates it).
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from random import SystemRandom

from rockforge.domain.arrangement import Arrangement, ArrangementKind

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
    return {
        "ID": guid,
        "XML": xml_name,
        "Name": _ARRANGEMENT_NAME[arr.kind],
        "RouteMask": _ROUTE_MASK[arr.kind],
        "Priority": 0,  # ArrangementPriority.Main
        "ScrollSpeed": _DEFAULT_SCROLL_SPEED,
        "BassPicked": False,
        "Tuning": list(arr.tuning.offsets_from_standard()),
        "TuningPitch": _tuning_pitch(arr.tuning.cent_offset),
        "BaseTone": arr.tone_base or "",
        "Tones": list(arr.tone_names),
        "MasterID": _master_id(),
        "PersistentID": guid,
    }


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
        "Tones": [],
    }
    if meta.song_length > 0:
        project["AudioFileLength"] = round(meta.song_length, 3)
    return project


def write_rs2dlc(
    arrangements: list[Arrangement],
    instrumental_xml_names: list[str],
    audio_name: str,
    dlc_key: str,
    out_path: Path,
    vocals_xml_name: str | None = None,
    cover_art_name: str | None = None,
) -> Path:
    """Write a ``.rs2dlc`` DLC Builder project file; returns *out_path*."""
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
    return out_path
