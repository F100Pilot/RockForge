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
    tone_from_dict,
)

# A tone's Volume gets LOUDER as it gets more negative: DLC Builder's editor
# shows ``-Volume`` on a 0.1..36 slider with the loud icon at 36
# (Rocksmith2014.NET ``ToneDetails.fs``/``EditFunctions.SetVolume``), its own
# default tones sit at -18.6/-19.5 and a new tone at -18 (``ToneGear.fs``). The
# first presets used -13..-16, quieter than any of those, and in game they could
# hardly be heard. These are the values they shipped with, so a project still
# carrying one untouched can be brought up (``app._backfill_preset_tone_volumes``).
PRESET_VOLUMES_BEFORE: dict[str, float] = {
    "RFLead_Clean": -15.0, "RFLead_CleanBright": -15.0, "RFLead_Crunch": -14.0,
    "RFLead_Plexi": -14.0, "RFLead_Overdrive": -13.0, "RFLead_HighGain": -13.0,
    "RFLead_Metal": -13.0, "RFRhythm_Clean": -16.0, "RFRhythm_Crunch": -15.0,
    "RFRhythm_Plexi": -15.0, "RFRhythm_Orange": -14.0, "RFRhythm_HighGain": -14.0,
    "RFRhythm_Metal": -14.0,
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
    "pre": [{"key": "Pedal_GermaniumDrive", "knobs": {"Pedal_GermaniumDrive_Gain": 60}}],
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
        "lead": lead_dict,
        "rhythm": rhythm_dict,
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
}

LEAD_OVERDRIVE: dict[str, Any] = {
    "key": "RFLead_Overdrive",
    "name": "Lead – Overdrive quente",
    "volume": -19.5,
    "descriptors": [TONE_DESCRIPTORS["Overdrive"], TONE_DESCRIPTORS["Lead"]],
    "amp": {
        "key": "Amp_Marshall1962Bluesbreaker",
        "knobs": {"Amp_Marshall1962Bluesbreaker_Gain": 60},
    },
    "cabinet": {"key": "Cab_Marshall1960a_57_Cone"},
    "pre": [{"key": "Pedal_SuperDrive", "knobs": {"Pedal_SuperDrive_Gain": 55}}],
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
    "pre": [{"key": "Pedal_MetalDistortion", "knobs": {"Pedal_MetalDistortion_Gain": 50}}],
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
}

RHYTHM_ORANGE: dict[str, Any] = {
    "key": "RFRhythm_Orange",
    "name": "Rhythm – Crunch encorpado",
    "volume": -20.0,
    "descriptors": [TONE_DESCRIPTORS["Crunch"], TONE_DESCRIPTORS["Distortion"]],
    "amp": {
        "key": "Amp_OrangeRockerverb",
        "knobs": {
            "Amp_OrangeRockerverb_Gain": 68,
            "Amp_OrangeRockerverb_Bass": 74,
            "Amp_OrangeRockerverb_Treble": 55,
        },
    },
    "cabinet": {"key": "Cab_OrangePPC412_57_Cone"},
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
    "pre": [{"key": "Pedal_MetalDistortion", "knobs": {"Pedal_MetalDistortion_Gain": 45}}],
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
    (RHYTHM_ORANGE, (0.58, 0.44, 0.62)),
    (RHYTHM_HIGH_GAIN, (0.82, 0.55, 0.58)),
    (RHYTHM_METAL, (0.92, 0.50, 0.75)),
]

# Gain dominates the perceived match (a clean amp never sounds like a metal
# amp however you EQ it), brightness/low-end are the secondary refinements.
_W_GAIN, _W_BRIGHT, _W_LOW = 2.2, 1.0, 0.9
# Worst plausible distance (gain 0↔1 + bright 0↔1 + low 0↔1), for a 0-100%.
_MAX_DIST = (_W_GAIN + _W_BRIGHT + _W_LOW) ** 0.5


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
        scored.append((dist, {**tone_dict, "match": match}))
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
    for tone, _fp in (*_LEAD_LIBRARY, *_RHYTHM_LIBRARY):
        if tone["key"] == key:
            return float(tone["volume"])
    return None
