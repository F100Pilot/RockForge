"""Tests for the tone detection feature (spectral analysis + preset mapping)."""

from rockforge.infrastructure.packaging.gear.tone_presets import suggest_tones
from rockforge.infrastructure.tone_analysis.analyzer import ToneProfile


def test_tone_profile_classifies_clean() -> None:
    profile = ToneProfile(gain_level=0.1, brightness=0.4, low_end=0.5, dynamic_range=0.8)
    assert profile.category == "clean"


def test_tone_profile_classifies_crunch() -> None:
    profile = ToneProfile(gain_level=0.4, brightness=0.5, low_end=0.4, dynamic_range=0.5)
    assert profile.category == "crunch"


def test_tone_profile_classifies_high_gain() -> None:
    profile = ToneProfile(gain_level=0.7, brightness=0.6, low_end=0.6, dynamic_range=0.2)
    assert profile.category == "high_gain"


def _profile(gain: float, **kw: float) -> ToneProfile:
    base = {"brightness": 0.5, "low_end": 0.5, "dynamic_range": 0.3}
    base.update(kw)
    return ToneProfile(gain_level=gain, **base)


def test_high_gain_boundary_is_half() -> None:
    # A distorted song should not be under-read as crunch: the crunch/high-gain
    # boundary is 0.5, so a solidly-distorted tone reads high_gain.
    assert _profile(0.49).category == "crunch"
    assert _profile(0.5).category == "high_gain"


def test_tone_profile_carries_distortion_cues() -> None:
    # flatness / compression are the brightness-independent distortion cues; they
    # default to 0 so older callers/serialized profiles stay valid.
    p = _profile(0.6, flatness=0.7, compression=0.65)
    assert p.flatness == 0.7 and p.compression == 0.65
    assert _profile(0.1).flatness == 0.0


def test_suggest_tones_returns_lead_and_rhythm_for_each_category() -> None:
    for cat in ("clean", "crunch", "high_gain"):
        result = suggest_tones(cat)
        assert result["category"] == cat
        assert result["lead"]["key"].startswith("RFLead_")
        assert result["rhythm"]["key"].startswith("RFRhythm_")
        assert result["lead_tone"] is not None
        assert result["rhythm_tone"] is not None


def test_suggest_tones_builds_valid_domain_tones() -> None:
    result = suggest_tones("high_gain")
    lead = result["lead_tone"]
    rhythm = result["rhythm_tone"]
    assert lead.gear.amp.key == "Amp_CA100"
    assert rhythm.gear.amp.key == "Amp_HG100"
    assert lead.gear.cabinet is not None
    assert rhythm.gear.cabinet is not None


def test_suggest_tones_unknown_category_falls_back_to_crunch() -> None:
    result = suggest_tones("unknown_category")
    assert result["category"] == "unknown_category"
    assert result["lead"]["key"] == "RFLead_Crunch"
    assert result["rhythm"]["key"] == "RFRhythm_Crunch"


def test_preset_tone_dicts_have_required_fields() -> None:
    from rockforge.infrastructure.packaging.gear.gear_catalogue import tone_from_dict

    for cat in ("clean", "crunch", "high_gain"):
        result = suggest_tones(cat)
        for role in ("lead", "rhythm"):
            tone_dict = result[role]
            assert "key" in tone_dict
            assert "name" in tone_dict
            assert "amp" in tone_dict
            assert "cabinet" in tone_dict
            tone = tone_from_dict(tone_dict)
            assert tone is not None, f"tone_from_dict failed for {cat}/{role}"
            assert len(tone.gear.amp.knob_values) > 0
