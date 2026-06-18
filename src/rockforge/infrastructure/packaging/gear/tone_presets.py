"""Curated tone presets mapped to the Rocksmith gear catalogue.

Each preset is a tone dict in the shape ``tone_from_dict`` expects, using
real catalogue gear keys (from ``tone_gear_data.json``). Knobs omitted here
are filled from catalogue defaults by ``tone_from_dict``.

Presets are organized by gain category (clean / crunch / high_gain) and
role (lead / rhythm). The analyzer picks the best match based on spectral
features; the user reviews and adjusts in the tone editor.
"""

from __future__ import annotations

from typing import Any

from rockforge.infrastructure.packaging.gear.gear_catalogue import (
    TONE_DESCRIPTORS,
    tone_from_dict,
)

# ---------------------------------------------------------------------------
# Lead presets
# ---------------------------------------------------------------------------

LEAD_CLEAN: dict[str, Any] = {
    "key": "RFLead_Clean",
    "name": "Lead – Clean",
    "volume": -15.0,
    "descriptors": [TONE_DESCRIPTORS["Clean"], TONE_DESCRIPTORS["Lead"]],
    "amp": {"key": "Amp_CS100", "knobs": {"Amp_CS100_Gain": 20}},
    "cabinet": {"key": "Cab_Marshall1960a_57_Cone"},
    "pre": [{"key": "Pedal_Chorus"}],
}

LEAD_CRUNCH: dict[str, Any] = {
    "key": "RFLead_Crunch",
    "name": "Lead – Crunch",
    "volume": -14.0,
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
    "volume": -13.0,
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
    "volume": -16.0,
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
    "volume": -15.0,
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
    "volume": -14.0,
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
