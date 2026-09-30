"""DLC Builder's default tones, for an arrangement that has none of its own.

DLC Builder never builds a package whose arrangement has no tone definition:
``addDefaultTonesIfNeeded`` (Rocksmith2014.NET ``DLCBuilder.Domain/Utils.fs``)
gives it the path's default tone — ``default_lead.json`` for the lead route
(which a Combo arrangement also takes), ``default_rhythm.json`` otherwise —
under the arrangement's own base-tone key. RockForge's native PSARC shipped
such an arrangement with an EMPTY ``Tones`` and ``Tone_Base``, leaving the game
nothing to build the player's sound from: "mesmo sem os tons, os PSARC criados
pelo rockforge têm algum ruído e não têm uma tonalidade limpa". The two JSON
files are copied verbatim from ``samples/DLCBuilder.Domain/Tones/`` (MIT).
"""

from __future__ import annotations

import json
from dataclasses import replace
from functools import cache
from pathlib import Path
from typing import Any

from rockforge.domain.arrangement import ArrangementKind
from rockforge.domain.tone import Pedal, Tone
from rockforge.infrastructure.packaging.gear.gear_catalogue import tone_from_dict

_DIR = Path(__file__).with_name("default_tones")
_SLOTS = (("pre", "PrePedal"), ("post", "PostPedal"), ("racks", "Rack"))


@cache
def _load(route: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((_DIR / f"default_{route}.json").read_text("utf-8"))
    return data


def _route(kind: ArrangementKind) -> str:
    # Rocksmith's RouteMask: Lead and Combo play the lead route (rs2dlc.py).
    base = kind.base_kind
    return "lead" if base in (ArrangementKind.LEAD, ArrangementKind.COMBINED) else "rhythm"


def default_tone(kind: ArrangementKind, key: str | None = None) -> Tone:
    """The default tone DLC Builder would give ``kind``, keyed ``key`` (the
    arrangement's base-tone name) or the file's own key."""
    raw = _load(_route(kind))
    gear = raw["GearList"]

    def pedal(slot: str) -> dict[str, Any] | None:
        entry = gear.get(slot)
        return {"key": entry["Key"], "knobs": entry.get("KnobValues", {})} if entry else None

    as_dict: dict[str, Any] = {
        "key": key or raw["Key"],
        "name": raw["Name"],
        "volume": float(raw["Volume"]),
        "descriptors": list(raw.get("ToneDescriptors", [])),
        "amp": pedal("Amp"),
        "cabinet": pedal("Cabinet"),
    }
    for field, prefix in _SLOTS:
        as_dict[field] = [pedal(f"{prefix}{i}") for i in range(1, 5)]
    tone = tone_from_dict(as_dict)
    if tone is None:  # the vendored file names gear the catalogue lacks
        raise ValueError(f"default {_route(kind)} tone does not resolve against the gear catalogue")

    # The file's own Category, not the catalogue's (they differ on two pieces:
    # the studio EQ has none there, the mod delay "30779"): this tone is
    # reproduced exactly as DLC Builder ships it.
    def own(p: Pedal | None, slot: str) -> Pedal | None:
        entry = gear.get(slot)
        return None if p is None or not entry else replace(p, category=entry.get("Category"))

    g = tone.gear
    return replace(tone, gear=replace(
        g,
        pre_pedals=tuple(own(p, f"PrePedal{i}") for i, p in enumerate(g.pre_pedals, 1)),
        post_pedals=tuple(own(p, f"PostPedal{i}") for i, p in enumerate(g.post_pedals, 1)),
        racks=tuple(own(p, f"Rack{i}") for i, p in enumerate(g.racks, 1)),
    ))
