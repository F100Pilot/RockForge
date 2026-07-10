"""Serialize a domain :class:`Tone` into the Rocksmith ``ToneDto`` dict.

This is the shared source of truth for the tone gear serialization used by both
the DLC Builder project file (``rs2dlc.py`` ``Tones`` array) and the native
PSARC's runtime manifest (``manifest.py`` per-arrangement ``Tones``). A DLC
Builder build of one of our own tones serializes to exactly this shape in both
places (verified by decoding ``emphaticpride_lead.json``'s ``Tones``), so a
single implementation keeps them in lock-step.

Field order and the ``PedalKey -> "Key"`` rename match Rocksmith2014.NET
``Tone.fs`` (MIT); ``System.Text.Json`` drops null members, so unset optional
fields (``Category``) are omitted rather than emitted as ``null``.
"""

from __future__ import annotations

from rockforge.domain.tone import Pedal, Tone


def pedal_dto(pedal: Pedal) -> dict[str, object]:
    """A ``PedalDto`` dict (Type, KnobValues, Key, optional Category)."""
    dto: dict[str, object] = {
        "Type": pedal.gear_type,
        "KnobValues": {k: round(v, 4) for k, v in pedal.knob_values.items()},
        "Key": pedal.key,
    }
    if pedal.category is not None:
        dto["Category"] = pedal.category
    return dto


def gear_dto(tone: Tone) -> dict[str, object]:
    """A ``GearDto`` dict: Amp + Cabinet plus only the populated pedal/rack slots
    (DLC Builder names them Rack1-4 / PrePedal1-4 / PostPedal1-4 and omits empty
    ones)."""
    gear = tone.gear
    dto: dict[str, object] = {
        "Amp": pedal_dto(gear.amp),
        "Cabinet": pedal_dto(gear.cabinet),
    }
    for prefix, slots in (
        ("PrePedal", gear.pre_pedals),
        ("PostPedal", gear.post_pedals),
        ("Rack", gear.racks),
    ):
        for i, pedal in enumerate(slots, start=1):
            if pedal is not None:
                dto[f"{prefix}{i}"] = pedal_dto(pedal)
    return dto


def tone_dto(tone: Tone) -> dict[str, object]:
    """A ``ToneDto`` dict, as ``Tone.toDto`` serializes it.

    ``Volume`` is a string formatted ``0.000`` (Rocksmith2014.NET
    ``volumeToString``); ``IsCustom`` is always ``true`` (matching ``toDto``)."""
    return {
        "GearList": gear_dto(tone),
        "ToneDescriptors": list(tone.descriptors),
        "NameSeparator": " - ",
        "IsCustom": True,
        "Volume": f"{tone.volume:.3f}",
        "Key": tone.key,
        "Name": tone.name,
    }


def unique_tone_dtos(tones: list[Tone]) -> list[dict[str, object]]:
    """``ToneDto`` dicts for ``tones``, de-duplicated by tone ``key`` (the same
    tone shared by Lead/Rhythm is emitted once), preserving order."""
    seen: dict[str, dict[str, object]] = {}
    for tone in tones:
        if tone.key not in seen:
            seen[tone.key] = tone_dto(tone)
    return list(seen.values())
