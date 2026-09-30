"""Load the vendored Rocksmith gear catalogue and build domain tones from it.

Two consumers:

* the web UI (via ``GET /gear-catalogue``) — needs the gear list grouped by
  type/category plus each knob's range/default to render the tone builder.
* the worker — turns the lightweight tone dicts the UI sends into fully-formed
  domain :class:`~rockforge.domain.tone.Tone` objects, filling in any knob the
  user did not set from the catalogue's ``DefaultValue`` (exactly what DLC
  Builder does with stock gear).

The catalogue JSON is the source of truth for knob *keys* — never synthesize a
knob key from its display name (e.g. the JCM800 "Presence" knob is
``Amp_MarshallJCM800_Pres``, not ``..._Presence``).
"""

from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources
from typing import Any

from rockforge.domain.tone import Gear, Pedal, Tone

# Rocksmith tone descriptors (``Name`` -> ``$[id]NAME``), from Rocksmith2014.NET
# ToneDescriptors.fs (MIT). Used by the UI dropdown and to validate descriptors.
TONE_DESCRIPTORS: dict[str, str] = {
    "Acoustic": "$[35721]ACOUSTIC",
    "Banjo": "$[27201]BANJO",
    "Bass": "$[35715]BASS",
    "Chorus": "$[35723]CHORUS",
    "Clean": "$[35720]CLEAN",
    "Crunch": "$[27156]CRUNCH",
    "Delay": "$[35753]DELAY",
    "Direct": "$[35752]DIRECT",
    "Distortion": "$[35722]DISTORTION",
    "Echo": "$[35754]ECHO",
    "Effect": "$[35733]EFFECT",
    "Emulated": "$[27119]EMULATED",
    "Filter": "$[35729]FILTER",
    "Flanger": "$[35731]FLANGER",
    "Fuzz": "$[35756]FUZZ",
    "High Gain": "$[35755]HIGH GAIN",
    "Lead": "$[35724]LEAD",
    "Low Output": "$[35732]LOW OUTPUT",
    "Mandolin": "$[27202]MANDOLIN",
    "Multi Effect": "$[35751]MULTI-EFFECT",
    "Octave": "$[35719]OCTAVE",
    "Overdrive": "$[35716]OVERDRIVE",
    "Phaser": "$[35730]PHASER",
    "Piano": "$[29495]PIANO",
    "Processed": "$[35734]PROCESSED",
    "Reverb": "$[35726]REVERB",
    "Rotary": "$[35725]ROTARY",
    "Special Effect": "$[35750]SPECIAL EFFECT",
    "Tremolo": "$[35727]TREMOLO",
    "Ukulele": "$[27204]UKULELE",
    "Vibrato": "$[35728]VIBRATO",
    "Vocal": "$[35718]VOCAL",
}

_DEFAULT_VOLUME = -18.0  # DLC Builder's new-tone default (ToneGear.fs); more negative = louder


@lru_cache(maxsize=1)
def _raw_catalogue() -> list[dict[str, Any]]:
    data = (
        resources.files("rockforge.infrastructure.packaging.gear")
        .joinpath("tone_gear_data.json")
        .read_text(encoding="utf-8")
    )
    parsed: list[dict[str, Any]] = json.loads(data)
    return parsed


@lru_cache(maxsize=1)
def _by_key() -> dict[str, dict[str, Any]]:
    return {g["Key"]: g for g in _raw_catalogue()}


def knob_defaults(key: str) -> dict[str, float]:
    """Every knob of a gear piece at its catalogue ``DefaultValue``."""
    entry = _by_key().get(key)
    if not entry:
        return {}
    return {k["Key"]: float(k["DefaultValue"]) for k in entry.get("Knobs", [])}


def catalogue_for_ui() -> dict[str, Any]:
    """A compact catalogue for the tone-builder UI, grouped by gear type.

    Cabinets are additionally indexed by model so the UI can offer a single
    model picker plus mic/position, instead of 450 flat entries.
    """
    amps: list[dict[str, Any]] = []
    pedals: list[dict[str, Any]] = []
    racks: list[dict[str, Any]] = []
    cabinets: list[dict[str, Any]] = []
    for g in _raw_catalogue():
        knobs = [
            {
                "key": k["Key"],
                "name": k["Name"],
                "unit": k.get("UnitType", "number"),
                "min": k.get("MinValue", 0),
                "max": k.get("MaxValue", 100),
                "step": k.get("ValueStep", 1),
                "default": k.get("DefaultValue", 0),
            }
            for k in g.get("Knobs", [])
        ]
        entry = {
            "key": g["Key"],
            "name": g["Name"],
            "category": g.get("Category"),
            "knobs": knobs,
            "bass": "Bass_" in g["Key"],
        }
        gtype = g["Type"]
        if gtype == "Amps":
            amps.append(entry)
        elif gtype == "Pedals":
            pedals.append(entry)
        elif gtype == "Racks":
            racks.append(entry)
        elif gtype == "Cabinets":
            cabinets.append(entry)
    return {
        "amps": amps,
        "cabinets": cabinets,
        "pedals": pedals,
        "racks": racks,
        "descriptors": TONE_DESCRIPTORS,
    }


def _pedal_from_dict(raw: dict[str, Any] | None) -> Pedal | None:
    """Build a domain :class:`Pedal` from ``{"key": ..., "knobs": {...}}``.

    The gear ``Type`` and ``Category`` come from the catalogue (authoritative);
    any knob the caller omits is filled from the catalogue default.
    """
    if not raw:
        return None
    key = str(raw["key"])
    entry = _by_key().get(key)
    if entry is None:
        return None
    knobs = knob_defaults(key)
    for kk, kv in (raw.get("knobs") or {}).items():
        if kk in knobs:
            knobs[kk] = float(kv)
    # DLC Builder carries a Category only on effects (Pedals/Racks); amps and
    # cabinets identify fully by their Key, so their Category is left unset to
    # match a real captured tone (default_lead.json).
    category = entry.get("Category") if entry["Type"] in ("Pedals", "Racks") else None
    return Pedal(
        gear_type=entry["Type"],
        key=key,
        knob_values=knobs,
        category=category,
    )


def tone_from_dict(raw: dict[str, Any]) -> Tone | None:
    """Build a domain :class:`Tone` from the UI/params dict.

    Shape::

        {"key": str, "name": str, "volume": float, "descriptors": [str],
         "amp": {"key", "knobs"}, "cabinet": {...},
         "pre": [ {...}|null x4 ], "post": [...], "racks": [...]}

    Returns ``None`` when the amp/cabinet are missing or unknown (a tone is
    meaningless without them), so the caller can skip it rather than emit a
    malformed ``ToneDto``.
    """
    amp = _pedal_from_dict(raw.get("amp"))
    cabinet = _pedal_from_dict(raw.get("cabinet"))
    if amp is None or cabinet is None:
        return None

    def slots(name: str) -> tuple[Pedal | None, ...]:
        items = list(raw.get(name) or [])
        pedals = [_pedal_from_dict(it) for it in items][:4]
        pedals += [None] * (4 - len(pedals))
        return tuple(pedals)

    descriptors = tuple(str(d) for d in (raw.get("descriptors") or ()))
    key = str(raw.get("key") or raw.get("name") or "Tone")
    return Tone(
        key=key,
        name=str(raw.get("name") or key),
        gear=Gear(
            amp=amp,
            cabinet=cabinet,
            racks=slots("racks"),
            pre_pedals=slots("pre"),
            post_pedals=slots("post"),
        ),
        descriptors=descriptors,
        volume=float(raw.get("volume", _DEFAULT_VOLUME)),
    )


def tones_from_dicts(rows: list[dict[str, Any]]) -> list[Tone]:
    """Build domain tones from a list of UI dicts, dropping any invalid ones."""
    out: list[Tone] = []
    for row in rows:
        tone = tone_from_dict(row)
        if tone is not None:
            out.append(tone)
    return out
