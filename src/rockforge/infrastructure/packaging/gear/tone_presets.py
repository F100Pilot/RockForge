"""Curated tone presets mapped to the Rocksmith gear catalogue.

Each preset is a tone dict in the shape ``tone_from_dict`` expects, using
real catalogue gear keys (from ``tone_gear_data.json``). Knobs omitted here
are filled from catalogue defaults by ``tone_from_dict``.

Presets are organized by gain category (clean / crunch / high_gain) and
role (lead / rhythm). ``suggest_tones`` picks the single best preset per
category (legacy path); ``rank_tones`` returns the whole library ranked by
spectral distance to the detected profile, so the user can browse SEVERAL
"similar tones" — not one guess — when the closest amp is hard to find.

Each preset carries a ``_fp`` fingerprint ``(gain, bright, low)`` in 0-1
describing the sound it targets; ranking is a weighted distance from the
analyzer's :class:`ToneProfile`. This does NOT identify the real amp — it
proposes plausible catalogue matches the user auditions and adjusts.
"""

from __future__ import annotations

from typing import Any

from rockforge.infrastructure.packaging.gear.gear_catalogue import (
    TONE_DESCRIPTORS,
    knob_defaults,
    tone_from_dict,
)

# A tone's Volume gets LOUDER as it gets more negative: DLC Builder's editor
# shows ``-Volume`` on a 0.1..36 slider with the loud icon at 36
# (Rocksmith2014.NET ``ToneDetails.fs``/``EditFunctions.SetVolume``), its own
# default tones sit at -18.6/-19.5 and a new tone at -18 (``ToneGear.fs``). The
# first presets used -13..-16, quieter than any of those, and in game they could
# hardly be heard. Each preset maps to every volume it has shipped with before,
# oldest first, so a project still carrying one untouched can be brought up
# (``app._backfill_preset_tones``). The Orange crunch and the Overdrive were
# raised again after the user heard them in game (2026-10-01: the crunch "muito
# baixo", the overdrive "só um pouco baixo").
PRESET_VOLUMES_BEFORE: dict[str, tuple[float, ...]] = {
    "RFLead_Clean": (-15.0,), "RFLead_CleanBright": (-15.0,), "RFLead_Crunch": (-14.0,),
    "RFLead_Plexi": (-14.0,), "RFLead_Overdrive": (-13.0, -19.5),
    "RFLead_HighGain": (-13.0,), "RFLead_Metal": (-13.0,), "RFRhythm_Clean": (-16.0,),
    "RFRhythm_Crunch": (-15.0,), "RFRhythm_Plexi": (-15.0,),
    "RFRhythm_Orange": (-14.0, -20.0), "RFRhythm_HighGain": (-14.0,),
    "RFRhythm_Metal": (-14.0,),
}

# A noise gate opens every preset with drive. Gain amplifies whatever the
# player's guitar feeds in when it is NOT playing — pickup hum, string noise —
# so a crunch/high-gain tone left a hiss under the end of every note and after
# the last one ("os detetados ainda ficam com um pouco de ruído no final"),
# while DLC Builder's default tones (a Plexi + drive pedal, an Orange at gain
# 25) were quiet enough without one. ``Pedal_NoiseGate`` is the catalogue's own
# (Threshold -90..-40 dB, default -55; Rate default 81), first in the chain so
# it gates the input before the drive, as the game's own metal tones place it.
# A higher threshold cuts more: high gain gets the game's default, crunch a
# gentler one so a note's natural decay is not chopped.
GATE_KEY = "Pedal_NoiseGate"
_GATE_CRUNCH = -65.0
_GATE_HIGH_GAIN = -55.0


def _gate(threshold: float) -> dict[str, Any]:
    return {
        "key": GATE_KEY,
        "knobs": {"Pedal_NoiseGate_Thresh": threshold, "Pedal_NoiseGate_Rate": 81},
    }

# ---------------------------------------------------------------------------
# Lead presets
# ---------------------------------------------------------------------------

LEAD_CLEAN: dict[str, Any] = {
    "key": "RFLead_Clean",
    "name": "Lead – Clean",
    "volume": -21.0,
    "descriptors": [TONE_DESCRIPTORS["Clean"], TONE_DESCRIPTORS["Lead"]],
    "amp": {"key": "Amp_CS100", "knobs": {"Amp_CS100_Gain": 20}},
    "cabinet": {"key": "Cab_Marshall1960a_57_Cone"},
    "pre": [{"key": "Pedal_Chorus"}],
}

LEAD_CRUNCH: dict[str, Any] = {
    "key": "RFLead_Crunch",
    "name": "Lead – Crunch",
    "volume": -20.0,
    "descriptors": [TONE_DESCRIPTORS["Crunch"], TONE_DESCRIPTORS["Lead"]],
    "amp": {
        "key": "Amp_MarshallJCM800",
        "knobs": {
            "Amp_MarshallJCM800_Gain": 65,
            "Amp_MarshallJCM800_Bass": 60,
            "Amp_MarshallJCM800_Mid": 70,
            "Amp_MarshallJCM800_Treble": 72,
            "Amp_MarshallJCM800_Pres": 40,
        },
    },
    "cabinet": {"key": "Cab_Marshall1960a_57_Cone"},
    "pre": [_gate(_GATE_CRUNCH)],
}

LEAD_HIGH_GAIN: dict[str, Any] = {
    "key": "RFLead_HighGain",
    "name": "Lead – High Gain",
    "volume": -19.5,
    "descriptors": [TONE_DESCRIPTORS["High Gain"], TONE_DESCRIPTORS["Lead"]],
    "amp": {
        "key": "Amp_CA100",
        "knobs": {
            "Amp_CA100_Gain": 90,
            "Amp_CA100_Bass": 60,
            "Amp_CA100_Mid": 75,
            "Amp_CA100_Treble": 80,
            "Amp_CA100_Pres": 40,
        },
    },
    "cabinet": {"key": "Cab_GB412CMKIII_57_Cone"},
    "pre": [
        _gate(_GATE_HIGH_GAIN),
        {"key": "Pedal_GermaniumDrive", "knobs": {"Pedal_GermaniumDrive_Gain": 60}},
    ],
}

# ---------------------------------------------------------------------------
# Rhythm presets
# ---------------------------------------------------------------------------

RHYTHM_CLEAN: dict[str, Any] = {
    "key": "RFRhythm_Clean",
    "name": "Rhythm – Clean",
    "volume": -21.0,
    "descriptors": [TONE_DESCRIPTORS["Clean"]],
    "amp": {
        "key": "Amp_TW22",
        "knobs": {
            "Amp_TW22_Gain": 18,
            "Amp_TW22_Bass": 50,
            "Amp_TW22_Mid": 55,
            "Amp_TW22_Treble": 60,
        },
    },
    "cabinet": {"key": "Cab_TW112C_57_Cone"},
}

RHYTHM_CRUNCH: dict[str, Any] = {
    "key": "RFRhythm_Crunch",
    "name": "Rhythm – Crunch",
    "volume": -20.0,
    "descriptors": [TONE_DESCRIPTORS["Crunch"]],
    "amp": {
        "key": "Amp_MarshallJCM800",
        "knobs": {
            "Amp_MarshallJCM800_Gain": 50,
            "Amp_MarshallJCM800_Bass": 70,
            "Amp_MarshallJCM800_Mid": 65,
            "Amp_MarshallJCM800_Treble": 60,
            "Amp_MarshallJCM800_Pres": 35,
        },
    },
    "cabinet": {"key": "Cab_Marshall1960a_57_Cone"},
    "pre": [_gate(_GATE_CRUNCH)],
}

RHYTHM_HIGH_GAIN: dict[str, Any] = {
    "key": "RFRhythm_HighGain",
    "name": "Rhythm – High Gain",
    "volume": -19.5,
    "descriptors": [TONE_DESCRIPTORS["High Gain"], TONE_DESCRIPTORS["Distortion"]],
    "amp": {
        "key": "Amp_HG100",
        "knobs": {
            "Amp_HG100_Gain": 85,
            "Amp_HG100_Bass": 75,
            "Amp_HG100_Mid": 60,
            "Amp_HG100_Treble": 70,
        },
    },
    "cabinet": {"key": "Cab_GB412CMKII_57_Cone"},
    "pre": [_gate(_GATE_HIGH_GAIN)],
}

# ---------------------------------------------------------------------------
# Category → preset mapping
# ---------------------------------------------------------------------------

_LEAD_PRESETS = {
    "clean": LEAD_CLEAN,
    "crunch": LEAD_CRUNCH,
    "high_gain": LEAD_HIGH_GAIN,
}

_RHYTHM_PRESETS = {
    "clean": RHYTHM_CLEAN,
    "crunch": RHYTHM_CRUNCH,
    "high_gain": RHYTHM_HIGH_GAIN,
}


def suggest_tones(
    category: str,
) -> dict[str, Any]:
    """Return lead + rhythm tone dicts for a detected gain category.

    The returned dict has ``lead`` and ``rhythm`` keys, each a tone dict
    ready for ``tone_from_dict``.  ``category`` is one of
    ``"clean"`` / ``"crunch"`` / ``"high_gain"``.
    """
    lead_dict = _LEAD_PRESETS.get(category, LEAD_CRUNCH)
    rhythm_dict = _RHYTHM_PRESETS.get(category, RHYTHM_CRUNCH)

    lead = tone_from_dict(lead_dict)
    rhythm = tone_from_dict(rhythm_dict)

    if lead is None or rhythm is None:
        raise ValueError(f"failed to build preset tones for category '{category}'")

    return {
        "lead": _named(lead_dict),
        "rhythm": _named(rhythm_dict),
        "lead_tone": lead,
        "rhythm_tone": rhythm,
        "category": category,
    }


# ---------------------------------------------------------------------------
# Extended library — several candidates per role spanning the gain axis and
# its brightness/low-end variants, so ranking can offer "similar tones" to
# browse instead of one preset. Each entry is (tone_dict, fingerprint) where
# the fingerprint is (gain, bright, low) in 0-1 — the sound it targets.
# ---------------------------------------------------------------------------

LEAD_CLEAN_BRIGHT: dict[str, Any] = {
    "key": "RFLead_CleanBright",
    "name": "Lead – Clean brilhante",
    "volume": -21.0,
    "descriptors": [TONE_DESCRIPTORS["Clean"], TONE_DESCRIPTORS["Lead"]],
    "amp": {
        "key": "Amp_TW26",
        "knobs": {"Amp_TW26_Gain": 22, "Amp_TW26_Treble": 78, "Amp_TW26_Bass": 40},
    },
    "cabinet": {"key": "Cab_TW112C_57_Cone"},
    "pre": [{"key": "Pedal_VintageChorus"}],
}

LEAD_PLEXI: dict[str, Any] = {
    "key": "RFLead_Plexi",
    "name": "Lead – Plexi (rock clássico)",
    "volume": -20.0,
    "descriptors": [TONE_DESCRIPTORS["Crunch"], TONE_DESCRIPTORS["Lead"]],
    "amp": {
        "key": "Amp_MarshallPlexi",
        "knobs": {
            "Amp_MarshallPlexi_Loudness1": 72,
            "Amp_MarshallPlexi_Treble": 74,
            "Amp_MarshallPlexi_Pres": 55,
        },
    },
    "cabinet": {"key": "Cab_Marshall1960a_57_Cone"},
    "pre": [_gate(_GATE_CRUNCH)],
}

LEAD_OVERDRIVE: dict[str, Any] = {
    "key": "RFLead_Overdrive",
    "name": "Lead – Overdrive quente",
    "volume": -21.0,
    "descriptors": [TONE_DESCRIPTORS["Overdrive"], TONE_DESCRIPTORS["Lead"]],
    "amp": {
        "key": "Amp_Marshall1962Bluesbreaker",
        "knobs": {"Amp_Marshall1962Bluesbreaker_Gain": 60},
    },
    "cabinet": {"key": "Cab_Marshall1960a_57_Cone"},
    "pre": [
        _gate(_GATE_CRUNCH),
        {"key": "Pedal_SuperDrive", "knobs": {"Pedal_SuperDrive_Gain": 55}},
    ],
}

LEAD_METAL: dict[str, Any] = {
    "key": "RFLead_Metal",
    "name": "Lead – Metal (escuro/apertado)",
    "volume": -19.5,
    "descriptors": [TONE_DESCRIPTORS["High Gain"], TONE_DESCRIPTORS["Lead"]],
    "amp": {
        "key": "Amp_HG100",
        "knobs": {
            "Amp_HG100_Gain": 95,
            "Amp_HG100_Bass": 78,
            "Amp_HG100_Mid": 55,
            "Amp_HG100_Treble": 62,
        },
    },
    "cabinet": {"key": "Cab_GB412CMKIII_57_Cone"},
    "pre": [
        _gate(_GATE_HIGH_GAIN),
        {"key": "Pedal_MetalDistortion", "knobs": {"Pedal_MetalDistortion_Gain": 50}},
    ],
}

RHYTHM_PLEXI: dict[str, Any] = {
    "key": "RFRhythm_Plexi",
    "name": "Rhythm – Plexi (rock clássico)",
    "volume": -20.0,
    "descriptors": [TONE_DESCRIPTORS["Crunch"]],
    "amp": {
        "key": "Amp_MarshallPlexi",
        "knobs": {
            "Amp_MarshallPlexi_Loudness1": 58,
            "Amp_MarshallPlexi_Treble": 62,
            "Amp_MarshallPlexi_Bass": 66,
        },
    },
    "cabinet": {"key": "Cab_Marshall1960a_57_Cone"},
    "pre": [_gate(_GATE_CRUNCH)],
}

# The Rockerverb is a hot amp (its catalogue default gain is 88), so 68 was
# already high-gain territory with a crunch-level gate behind it: the one
# preset that set the user's September apart from Jet Lag, which shipped the
# same two presets but never switched to this one ("os detetados ainda ficam
# com ruído" on the first, "bastante bom" on the second). Gain 55 with the
# high-gain gate was still too much distortion and too quiet in game ("muito
# baixo, e mesmo assim está com ruído (distorção em demasia)"), so it is now a
# real crunch — gain 42, less bass where hum sits — played louder. The earlier
# chains are in PRESET_CHAINS_BEFORE so projects still carrying one are
# brought up.
_ORANGE_AMP_FIRST: dict[str, Any] = {
    "key": "Amp_OrangeRockerverb",
    "knobs": {
        "Amp_OrangeRockerverb_Gain": 68,
        "Amp_OrangeRockerverb_Bass": 74,
        "Amp_OrangeRockerverb_Treble": 55,
    },
}
_ORANGE_AMP_SECOND: dict[str, Any] = {
    "key": "Amp_OrangeRockerverb",
    "knobs": {
        "Amp_OrangeRockerverb_Gain": 55,
        "Amp_OrangeRockerverb_Bass": 66,
        "Amp_OrangeRockerverb_Treble": 55,
    },
}

RHYTHM_ORANGE: dict[str, Any] = {
    "key": "RFRhythm_Orange",
    "name": "Rhythm – Crunch encorpado",
    "volume": -23.5,
    "descriptors": [TONE_DESCRIPTORS["Crunch"], TONE_DESCRIPTORS["Distortion"]],
    "amp": {
        "key": "Amp_OrangeRockerverb",
        "knobs": {
            "Amp_OrangeRockerverb_Gain": 42,
            "Amp_OrangeRockerverb_Bass": 60,
            "Amp_OrangeRockerverb_Treble": 55,
        },
    },
    "cabinet": {"key": "Cab_OrangePPC412_57_Cone"},
    "pre": [_gate(_GATE_HIGH_GAIN)],
}

# Chains (amp + pre-pedals) a preset shipped with before, oldest first. A
# project's or the library's copy still exactly on one of them is moved to the
# current chain by ``upgrade_preset_chain`` — a chain the user touched is not.
PRESET_CHAINS_BEFORE: dict[str, list[dict[str, Any]]] = {
    "RFRhythm_Orange": [
        {"amp": _ORANGE_AMP_FIRST, "pre": []},
        {"amp": _ORANGE_AMP_FIRST, "pre": [_gate(_GATE_CRUNCH)]},
        {"amp": _ORANGE_AMP_SECOND, "pre": [_gate(_GATE_HIGH_GAIN)]},
    ],
}

RHYTHM_METAL: dict[str, Any] = {
    "key": "RFRhythm_Metal",
    "name": "Rhythm – Metal (djent/apertado)",
    "volume": -19.5,
    "descriptors": [TONE_DESCRIPTORS["High Gain"], TONE_DESCRIPTORS["Distortion"]],
    "amp": {
        "key": "Amp_CA100",
        "knobs": {
            "Amp_CA100_Gain": 98,
            "Amp_CA100_Bass": 80,
            "Amp_CA100_Mid": 45,
            "Amp_CA100_Treble": 70,
            "Amp_CA100_Pres": 55,
        },
    },
    "cabinet": {"key": "Cab_GB412CMKII_57_Cone"},
    "pre": [
        _gate(_GATE_HIGH_GAIN),
        {"key": "Pedal_MetalDistortion", "knobs": {"Pedal_MetalDistortion_Gain": 45}},
    ],
}

# (tone_dict, (gain, bright, low)) — fingerprints describe the target sound.
_LEAD_LIBRARY: list[tuple[dict[str, Any], tuple[float, float, float]]] = [
    (LEAD_CLEAN, (0.12, 0.50, 0.45)),
    (LEAD_CLEAN_BRIGHT, (0.12, 0.82, 0.25)),
    (LEAD_CRUNCH, (0.40, 0.60, 0.40)),
    (LEAD_PLEXI, (0.45, 0.72, 0.35)),
    (LEAD_OVERDRIVE, (0.55, 0.50, 0.50)),
    (LEAD_HIGH_GAIN, (0.80, 0.60, 0.50)),
    (LEAD_METAL, (0.90, 0.42, 0.72)),
]

_RHYTHM_LIBRARY: list[tuple[dict[str, Any], tuple[float, float, float]]] = [
    (RHYTHM_CLEAN, (0.10, 0.50, 0.45)),
    (RHYTHM_CRUNCH, (0.40, 0.55, 0.45)),
    (RHYTHM_PLEXI, (0.44, 0.66, 0.38)),
    (RHYTHM_ORANGE, (0.50, 0.44, 0.62)),
    (RHYTHM_HIGH_GAIN, (0.82, 0.55, 0.58)),
    (RHYTHM_METAL, (0.92, 0.50, 0.75)),
]

# Gain dominates the perceived match (a clean amp never sounds like a metal
# amp however you EQ it), brightness/low-end are the secondary refinements.
_W_GAIN, _W_BRIGHT, _W_LOW = 2.2, 1.0, 0.9
# Worst plausible distance (gain 0↔1 + bright 0↔1 + low 0↔1), for a 0-100%.
_MAX_DIST = (_W_GAIN + _W_BRIGHT + _W_LOW) ** 0.5


# The presets' names in English (the Portuguese is written in the presets
# above); applied when a preset is handed out, so a suggestion reads in the
# user's language — once applied it is the project's tone, named as it was.
_NAMES_EN = {
    "Lead – Clean brilhante": "Lead – Bright clean",
    "Lead – Plexi (rock clássico)": "Lead – Plexi (classic rock)",
    "Lead – Overdrive quente": "Lead – Warm overdrive",
    "Lead – Metal (escuro/apertado)": "Lead – Metal (dark/tight)",
    "Rhythm – Plexi (rock clássico)": "Rhythm – Plexi (classic rock)",
    "Rhythm – Crunch encorpado": "Rhythm – Full-bodied crunch",
    "Rhythm – Metal (djent/apertado)": "Rhythm – Metal (djent/tight)",
}


def _named(tone_dict: dict[str, Any]) -> dict[str, Any]:
    from rockforge.i18n import tr

    name = tone_dict.get("name", "")
    return {**tone_dict, "name": tr(name, _NAMES_EN.get(name, name))}


def _rank_library(
    library: list[tuple[dict[str, Any], tuple[float, float, float]]],
    gain: float,
    bright: float,
    low: float,
) -> list[dict[str, Any]]:
    """Rank a preset library by weighted distance to (gain, bright, low).

    Returns tone dicts (closest first) each annotated with a 0-100 ``match``.
    """
    scored: list[tuple[float, dict[str, Any]]] = []
    for tone_dict, (fg, fb, fl) in library:
        dist = (
            _W_GAIN * (gain - fg) ** 2
            + _W_BRIGHT * (bright - fb) ** 2
            + _W_LOW * (low - fl) ** 2
        ) ** 0.5
        match = round(100.0 * (1.0 - min(1.0, dist / _MAX_DIST)))
        scored.append((dist, {**_named(tone_dict), "match": match}))
    scored.sort(key=lambda s: s[0])
    return [tone for _, tone in scored]


def rank_tones(
    gain_level: float,
    brightness: float,
    low_end: float,
    category: str,
) -> dict[str, Any]:
    """Rank the whole lead/rhythm library against a detected profile.

    Unlike :func:`suggest_tones` (one preset per coarse category), this returns
    EVERY candidate ranked by how close its target sound is to the recording —
    so the user can browse several "similar tones" and pick the best match when
    the top guess is off. The closest lead/rhythm are also exposed as ``lead`` /
    ``rhythm`` for the one-click "apply suggested" path.
    """
    lead_candidates = _rank_library(_LEAD_LIBRARY, gain_level, brightness, low_end)
    rhythm_candidates = _rank_library(_RHYTHM_LIBRARY, gain_level, brightness, low_end)
    return {
        "category": category,
        "lead": lead_candidates[0],
        "rhythm": rhythm_candidates[0],
        "lead_candidates": lead_candidates,
        "rhythm_candidates": rhythm_candidates,
    }


def rank_role(
    role: str, gain_level: float, brightness: float, low_end: float
) -> list[dict[str, Any]]:
    """One role's library (``"lead"`` or ``"rhythm"``) ranked against a target
    sound, closest first — what the per-section suggestions pick from."""
    library = _LEAD_LIBRARY if role == "lead" else _RHYTHM_LIBRARY
    return _rank_library(library, gain_level, brightness, low_end)


def preset_fingerprint(key: str) -> tuple[float, float, float] | None:
    """The ``(gain, bright, low)`` a preset targets, or None for a key that is
    not one of the curated presets."""
    for tone, fp in (*_LEAD_LIBRARY, *_RHYTHM_LIBRARY):
        if tone["key"] == key:
            return fp
    return None


def preset_volume(key: str) -> float | None:
    """The volume a curated preset ships with now, or None for any other key."""
    preset = _preset(key)
    return None if preset is None else float(preset["volume"])


def _preset(key: str) -> dict[str, Any] | None:
    for tone, _fp in (*_LEAD_LIBRARY, *_RHYTHM_LIBRARY):
        if tone["key"] == key:
            return tone
    return None


def _pedal_keys(items: object) -> list[str]:
    if not isinstance(items, list):
        return []
    return [str(it.get("key")) for it in items if isinstance(it, dict) and it.get("key")]


def with_preset_gate(tone: dict[str, Any]) -> dict[str, Any] | None:
    """A project's copy of a curated preset with the noise gate the preset now
    opens with, or None when it needs nothing. Only a copy whose pre-pedals are
    still the ones the preset shipped with gets it: a chain the user rebuilt is
    theirs, and a full one (four pedals) has no slot to give."""
    preset = _preset(str(tone.get("key", "")))
    if preset is None:
        return None
    wanted = list(preset.get("pre") or [])
    if not wanted or wanted[0].get("key") != GATE_KEY:
        return None
    pre = list(tone.get("pre") or [])
    if GATE_KEY in _pedal_keys(pre) or _pedal_keys(pre) != _pedal_keys(wanted[1:]):
        return None
    pre = [dict(wanted[0], knobs=dict(wanted[0]["knobs"])), *pre]
    while len(pre) > 4 and pre[-1] is None:
        pre.pop()
    if len(pre) > 4:
        return None
    return {**tone, "pre": pre}


def _chain_piece(item: object) -> tuple[str, tuple[tuple[str, float], ...]] | None:
    """A gear piece as (key, every knob) — the catalogue default where the dict
    leaves a knob out, so a copy the tone editor filled in compares equal to the
    preset it came from."""
    if not isinstance(item, dict) or not item.get("key"):
        return None
    key = str(item["key"])
    knobs = knob_defaults(key)
    for k, v in (item.get("knobs") or {}).items():
        if k in knobs and isinstance(v, (int, float)):
            knobs[k] = float(v)
    return key, tuple(sorted(knobs.items()))


def _chain(tone: dict[str, Any]) -> tuple[object, ...]:
    pre = tone.get("pre") if isinstance(tone.get("pre"), list) else []
    return (
        _chain_piece(tone.get("amp")),
        tuple(p for p in map(_chain_piece, pre or []) if p is not None),
    )


def upgrade_preset_chain(tone: dict[str, Any]) -> dict[str, Any] | None:
    """A copy of a curated preset whose amp and pre-pedals are still exactly an
    earlier version of that preset (``PRESET_CHAINS_BEFORE``), moved to the
    current amp and pre-pedals; None when it is not one. Cabinet, post-pedals,
    racks, volume and name are left as they are."""
    key = str(tone.get("key", ""))
    preset = _preset(key)
    if preset is None or not isinstance(tone.get("amp"), dict):
        return None
    if _chain(tone) not in [_chain(old) for old in PRESET_CHAINS_BEFORE.get(key, [])]:
        return None
    amp = preset["amp"]
    return {
        **tone,
        "amp": {"key": amp["key"], "knobs": dict(amp.get("knobs") or {})},
        "pre": [dict(p, knobs=dict(p.get("knobs") or {})) for p in preset.get("pre") or []],
    }
