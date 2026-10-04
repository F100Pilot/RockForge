"""Earlier versions of the curated tone presets (``tone_presets``).

A project's or the tone library's copy of a preset that is still EXACTLY one
of these chains is moved to the preset's current chain at startup
(``tone_presets.upgrade_preset_chain``); a chain the user touched is left
alone. Data only — a version is added here, verbatim, whenever a preset's
chain changes, before the change.
"""

from __future__ import annotations

from typing import Any

# The chains the RFRhythm_Orange crunch shipped with before 2026-10-01's last
# retune: amp + pre-pedals (its cabinet never changed, post-pedals and racks
# were always empty).
ORANGE_EARLY: list[dict[str, Any]] = [
    {
        "amp": {
            "key": "Amp_OrangeRockerverb",
            "knobs": {
                "Amp_OrangeRockerverb_Gain": 68,
                "Amp_OrangeRockerverb_Bass": 74,
                "Amp_OrangeRockerverb_Treble": 55
            }
        },
        "pre": []
    },
    {
        "amp": {
            "key": "Amp_OrangeRockerverb",
            "knobs": {
                "Amp_OrangeRockerverb_Gain": 68,
                "Amp_OrangeRockerverb_Bass": 74,
                "Amp_OrangeRockerverb_Treble": 55
            }
        },
        "pre": [
            {
                "key": "Pedal_NoiseGate",
                "knobs": {
                    "Pedal_NoiseGate_Thresh": -65.0,
                    "Pedal_NoiseGate_Rate": 81
                }
            }
        ]
    },
    {
        "amp": {
            "key": "Amp_OrangeRockerverb",
            "knobs": {
                "Amp_OrangeRockerverb_Gain": 55,
                "Amp_OrangeRockerverb_Bass": 66,
                "Amp_OrangeRockerverb_Treble": 55
            }
        },
        "pre": [
            {
                "key": "Pedal_NoiseGate",
                "knobs": {
                    "Pedal_NoiseGate_Thresh": -55.0,
                    "Pedal_NoiseGate_Rate": 81
                }
            }
        ]
    }
]

# Every preset as it shipped until 2026-10-04 (no EQ, compressor or reverb; the
# high-gain ones stacked a drive pedal; the Plexis left Loudness2 at its hot
# catalogue default).
V1: dict[str, dict[str, Any]] = {
    "RFLead_Clean": {
        "amp": {
            "key": "Amp_CS100",
            "knobs": {
                "Amp_CS100_Gain": 20
            }
        },
        "cabinet": {
            "key": "Cab_Marshall1960a_57_Cone"
        },
        "pre": [
            {
                "key": "Pedal_Chorus"
            }
        ],
        "post": [],
        "racks": []
    },
    "RFLead_CleanBright": {
        "amp": {
            "key": "Amp_TW26",
            "knobs": {
                "Amp_TW26_Gain": 22,
                "Amp_TW26_Treble": 78,
                "Amp_TW26_Bass": 40
            }
        },
        "cabinet": {
            "key": "Cab_TW112C_57_Cone"
        },
        "pre": [
            {
                "key": "Pedal_VintageChorus"
            }
        ],
        "post": [],
        "racks": []
    },
    "RFLead_Crunch": {
        "amp": {
            "key": "Amp_MarshallJCM800",
            "knobs": {
                "Amp_MarshallJCM800_Gain": 65,
                "Amp_MarshallJCM800_Bass": 60,
                "Amp_MarshallJCM800_Mid": 70,
                "Amp_MarshallJCM800_Treble": 72,
                "Amp_MarshallJCM800_Pres": 40
            }
        },
        "cabinet": {
            "key": "Cab_Marshall1960a_57_Cone"
        },
        "pre": [
            {
                "key": "Pedal_NoiseGate",
                "knobs": {
                    "Pedal_NoiseGate_Thresh": -65.0,
                    "Pedal_NoiseGate_Rate": 81
                }
            }
        ],
        "post": [],
        "racks": []
    },
    "RFLead_Plexi": {
        "amp": {
            "key": "Amp_MarshallPlexi",
            "knobs": {
                "Amp_MarshallPlexi_Loudness1": 72,
                "Amp_MarshallPlexi_Treble": 74,
                "Amp_MarshallPlexi_Pres": 55
            }
        },
        "cabinet": {
            "key": "Cab_Marshall1960a_57_Cone"
        },
        "pre": [
            {
                "key": "Pedal_NoiseGate",
                "knobs": {
                    "Pedal_NoiseGate_Thresh": -65.0,
                    "Pedal_NoiseGate_Rate": 81
                }
            }
        ],
        "post": [],
        "racks": []
    },
    "RFLead_Overdrive": {
        "amp": {
            "key": "Amp_Marshall1962Bluesbreaker",
            "knobs": {
                "Amp_Marshall1962Bluesbreaker_Gain": 60
            }
        },
        "cabinet": {
            "key": "Cab_Marshall1960a_57_Cone"
        },
        "pre": [
            {
                "key": "Pedal_NoiseGate",
                "knobs": {
                    "Pedal_NoiseGate_Thresh": -65.0,
                    "Pedal_NoiseGate_Rate": 81
                }
            },
            {
                "key": "Pedal_SuperDrive",
                "knobs": {
                    "Pedal_SuperDrive_Gain": 55
                }
            }
        ],
        "post": [],
        "racks": []
    },
    "RFLead_HighGain": {
        "amp": {
            "key": "Amp_CA100",
            "knobs": {
                "Amp_CA100_Gain": 90,
                "Amp_CA100_Bass": 60,
                "Amp_CA100_Mid": 75,
                "Amp_CA100_Treble": 80,
                "Amp_CA100_Pres": 40
            }
        },
        "cabinet": {
            "key": "Cab_GB412CMKIII_57_Cone"
        },
        "pre": [
            {
                "key": "Pedal_NoiseGate",
                "knobs": {
                    "Pedal_NoiseGate_Thresh": -55.0,
                    "Pedal_NoiseGate_Rate": 81
                }
            },
            {
                "key": "Pedal_GermaniumDrive",
                "knobs": {
                    "Pedal_GermaniumDrive_Gain": 60
                }
            }
        ],
        "post": [],
        "racks": []
    },
    "RFLead_Metal": {
        "amp": {
            "key": "Amp_HG100",
            "knobs": {
                "Amp_HG100_Gain": 95,
                "Amp_HG100_Bass": 78,
                "Amp_HG100_Mid": 55,
                "Amp_HG100_Treble": 62
            }
        },
        "cabinet": {
            "key": "Cab_GB412CMKIII_57_Cone"
        },
        "pre": [
            {
                "key": "Pedal_NoiseGate",
                "knobs": {
                    "Pedal_NoiseGate_Thresh": -55.0,
                    "Pedal_NoiseGate_Rate": 81
                }
            },
            {
                "key": "Pedal_MetalDistortion",
                "knobs": {
                    "Pedal_MetalDistortion_Gain": 50
                }
            }
        ],
        "post": [],
        "racks": []
    },
    "RFRhythm_Clean": {
        "amp": {
            "key": "Amp_TW22",
            "knobs": {
                "Amp_TW22_Gain": 18,
                "Amp_TW22_Bass": 50,
                "Amp_TW22_Mid": 55,
                "Amp_TW22_Treble": 60
            }
        },
        "cabinet": {
            "key": "Cab_TW112C_57_Cone"
        },
        "pre": [],
        "post": [],
        "racks": []
    },
    "RFRhythm_Crunch": {
        "amp": {
            "key": "Amp_MarshallJCM800",
            "knobs": {
                "Amp_MarshallJCM800_Gain": 50,
                "Amp_MarshallJCM800_Bass": 70,
                "Amp_MarshallJCM800_Mid": 65,
                "Amp_MarshallJCM800_Treble": 60,
                "Amp_MarshallJCM800_Pres": 35
            }
        },
        "cabinet": {
            "key": "Cab_Marshall1960a_57_Cone"
        },
        "pre": [
            {
                "key": "Pedal_NoiseGate",
                "knobs": {
                    "Pedal_NoiseGate_Thresh": -65.0,
                    "Pedal_NoiseGate_Rate": 81
                }
            }
        ],
        "post": [],
        "racks": []
    },
    "RFRhythm_Plexi": {
        "amp": {
            "key": "Amp_MarshallPlexi",
            "knobs": {
                "Amp_MarshallPlexi_Loudness1": 58,
                "Amp_MarshallPlexi_Treble": 62,
                "Amp_MarshallPlexi_Bass": 66
            }
        },
        "cabinet": {
            "key": "Cab_Marshall1960a_57_Cone"
        },
        "pre": [
            {
                "key": "Pedal_NoiseGate",
                "knobs": {
                    "Pedal_NoiseGate_Thresh": -65.0,
                    "Pedal_NoiseGate_Rate": 81
                }
            }
        ],
        "post": [],
        "racks": []
    },
    "RFRhythm_Orange": {
        "amp": {
            "key": "Amp_OrangeRockerverb",
            "knobs": {
                "Amp_OrangeRockerverb_Gain": 42,
                "Amp_OrangeRockerverb_Bass": 60,
                "Amp_OrangeRockerverb_Treble": 55
            }
        },
        "cabinet": {
            "key": "Cab_OrangePPC412_57_Cone"
        },
        "pre": [
            {
                "key": "Pedal_NoiseGate",
                "knobs": {
                    "Pedal_NoiseGate_Thresh": -55.0,
                    "Pedal_NoiseGate_Rate": 81
                }
            }
        ],
        "post": [],
        "racks": []
    },
    "RFRhythm_HighGain": {
        "amp": {
            "key": "Amp_HG100",
            "knobs": {
                "Amp_HG100_Gain": 85,
                "Amp_HG100_Bass": 75,
                "Amp_HG100_Mid": 60,
                "Amp_HG100_Treble": 70
            }
        },
        "cabinet": {
            "key": "Cab_GB412CMKII_57_Cone"
        },
        "pre": [
            {
                "key": "Pedal_NoiseGate",
                "knobs": {
                    "Pedal_NoiseGate_Thresh": -55.0,
                    "Pedal_NoiseGate_Rate": 81
                }
            }
        ],
        "post": [],
        "racks": []
    },
    "RFRhythm_Metal": {
        "amp": {
            "key": "Amp_CA100",
            "knobs": {
                "Amp_CA100_Gain": 98,
                "Amp_CA100_Bass": 80,
                "Amp_CA100_Mid": 45,
                "Amp_CA100_Treble": 70,
                "Amp_CA100_Pres": 55
            }
        },
        "cabinet": {
            "key": "Cab_GB412CMKII_57_Cone"
        },
        "pre": [
            {
                "key": "Pedal_NoiseGate",
                "knobs": {
                    "Pedal_NoiseGate_Thresh": -55.0,
                    "Pedal_NoiseGate_Rate": 81
                }
            },
            {
                "key": "Pedal_MetalDistortion",
                "knobs": {
                    "Pedal_MetalDistortion_Gain": 45
                }
            }
        ],
        "post": [],
        "racks": []
    }
}
