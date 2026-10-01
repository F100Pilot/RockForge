"""Tests for the tone detection feature (spectral analysis + preset mapping)."""

from rockforge.infrastructure.packaging.gear.gear_catalogue import tone_from_dict
from rockforge.infrastructure.packaging.gear.tone_presets import rank_tones, suggest_tones
from rockforge.infrastructure.tone_analysis.analyzer import ToneProfile, profile_from_features


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


def test_rank_tones_returns_ranked_candidate_libraries() -> None:
    # A distorted profile ranks a high-gain lead first and a clean lead last.
    result = rank_tones(gain_level=0.85, brightness=0.55, low_end=0.6, category="high_gain")
    lead = result["lead_candidates"]
    rhythm = result["rhythm_candidates"]
    assert len(lead) >= 5 and len(rhythm) >= 5
    # Ranked closest-first: the match score is monotonically non-increasing.
    lead_matches = [c["match"] for c in lead]
    assert lead_matches == sorted(lead_matches, reverse=True)
    # The top lead for a heavy profile is a high-gain/metal preset, not clean.
    assert "HighGain" in lead[0]["key"] or "Metal" in lead[0]["key"]
    assert lead[-1]["key"] == "RFLead_Clean" or "Clean" in lead[-1]["key"]
    # The primary lead/rhythm are the top candidates.
    assert result["lead"]["key"] == lead[0]["key"]
    assert result["rhythm"]["key"] == rhythm[0]["key"]
    # Every candidate is a buildable domain tone.
    for c in lead + rhythm:
        assert 0 <= c["match"] <= 100
        assert tone_from_dict(c) is not None


def test_rank_tones_clean_profile_ranks_clean_first() -> None:
    result = rank_tones(gain_level=0.08, brightness=0.5, low_end=0.4, category="clean")
    assert "Clean" in result["lead_candidates"][0]["key"]
    assert "Clean" in result["rhythm_candidates"][0]["key"]


def test_preset_tone_dicts_have_required_fields() -> None:
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


# ---- The gain heuristic itself -------------------------------------------
# The weights, thresholds and category boundaries used to sit inline inside
# analyze_guitar_tone(), which imports librosa, so CI (no ML stack) covered none
# of the calibration. profile_from_features() is the pure half; these pin its
# behaviour the way test_loudness.py pins the ffmpeg-free loudness maths.

_CLEAN = dict(zcr=0.04, centroid=1800.0, contrast=27.0, rolloff=5000.0,
              flatness=0.002, crest=5.0, rms_std_ratio=0.6)
_HIGH_GAIN = dict(zcr=0.14, centroid=2600.0, contrast=13.0, rolloff=7000.0,
                  flatness=0.03, crest=1.8, rms_std_ratio=0.2)


def test_gain_estimate_separates_clean_from_high_gain() -> None:
    assert profile_from_features(**_CLEAN).category == "clean"
    assert profile_from_features(**_HIGH_GAIN).category == "high_gain"


def test_a_dark_low_tuned_high_gain_tone_is_not_read_as_clean() -> None:
    """The exact bias the heuristic was redesigned to fix ("usually too clean").

    Zero-crossing rate and spectral centroid both measure BRIGHTNESS, so a dark,
    down-tuned or palm-muted high-gain tone read low on both and was classified
    clean. The brightness-independent cues — spectral flatness and the crest
    factor — have to carry it: this tone is dim (low centroid/rolloff) yet
    saturated and compressed, and must still come out high gain."""
    dark = profile_from_features(zcr=0.05, centroid=1400.0, contrast=12.0, rolloff=3500.0,
                                 flatness=0.025, crest=1.7, rms_std_ratio=0.15)
    assert dark.brightness < 0.2, "precondition: this tone really is dark"
    assert dark.category == "high_gain"


def test_the_crest_factor_dominates_the_gain_estimate() -> None:
    """Compression carries the most weight by design (it is the most reliable
    cue in practice), so squashing the dynamics alone must move the estimate."""
    picked = profile_from_features(**{**_CLEAN, "crest": 5.0})
    squashed = profile_from_features(**{**_CLEAN, "crest": 1.5})
    assert squashed.gain_level > picked.gain_level + 0.3
    assert squashed.compression == 1.0 and picked.compression == 0.0


def test_features_are_clamped_and_never_escape_zero_to_one() -> None:
    """Every field is a 0-1 normalized cue; absurd inputs must clamp, not leak a
    negative or >1 value into the preset ranking's weighted distance."""
    for extreme in (
        dict(zcr=99.0, centroid=99999.0, contrast=-99.0, rolloff=-99.0,
             flatness=1.0, crest=0.0, rms_std_ratio=99.0),
        dict(zcr=-99.0, centroid=-99999.0, contrast=999.0, rolloff=99999.0,
             flatness=1e-12, crest=999.0, rms_std_ratio=-99.0),
    ):
        p = profile_from_features(**extreme)
        for field in (p.gain_level, p.brightness, p.low_end, p.dynamic_range,
                      p.flatness, p.compression):
            assert 0.0 <= field <= 1.0, f"{field} out of range for {extreme}"


def test_presets_are_as_loud_as_the_games_own_tones() -> None:
    """A tone's Volume gets LOUDER as it gets more negative (DLC Builder shows
    -Volume, loudest at 36); its default tones sit at -18.6/-19.5. The first
    presets used -13..-16 and could hardly be heard in game."""
    from rockforge.infrastructure.packaging.gear import tone_presets as tp

    for tone, _fp in (*tp._LEAD_LIBRARY, *tp._RHYTHM_LIBRARY):
        assert -22.0 <= tone["volume"] <= -18.0, tone["key"]
        assert tp.preset_volume(tone["key"]) == tone["volume"]
        assert tone["key"] in tp.PRESET_VOLUMES_BEFORE
    assert tp.preset_volume("not-a-preset") is None


def test_every_preset_knob_is_a_real_knob_of_its_gear() -> None:
    """tone_from_dict drops a knob its gear does not have without a word — the
    Plexi's "Gain" (it has Loudness1/2) was silently ignored."""
    from rockforge.infrastructure.packaging.gear import tone_presets as tp
    from rockforge.infrastructure.packaging.gear.gear_catalogue import knob_defaults

    for tone, _fp in (*tp._LEAD_LIBRARY, *tp._RHYTHM_LIBRARY):
        for slot in ("amp", "cabinet", "pre", "post", "racks"):
            items = tone.get(slot) or []
            for item in [items] if isinstance(items, dict) else items:
                assert set(item.get("knobs") or {}) <= set(knob_defaults(item["key"])), (
                    tone["key"], item["key"],
                )


def test_every_preset_with_drive_opens_with_a_noise_gate() -> None:
    """Gain amplifies what the guitar feeds in between notes, so the driven
    presets left a hiss at the end of each note; the clean ones need no gate."""
    from rockforge.infrastructure.packaging.gear import tone_presets as tp
    from rockforge.infrastructure.packaging.gear.gear_catalogue import tone_from_dict

    for tone, (gain, _b, _l) in (*tp._LEAD_LIBRARY, *tp._RHYTHM_LIBRARY):
        built = tone_from_dict(tone)
        assert built is not None
        first = built.gear.pre_pedals[0]
        if gain >= 0.35:
            assert first is not None and first.key == tp.GATE_KEY, tone["key"]
            thresh = first.knob_values["Pedal_NoiseGate_Thresh"]
            assert -90 <= thresh <= -40
            if gain >= 0.8:  # high gain gates harder than crunch
                assert thresh == tp._GATE_HIGH_GAIN
            else:
                assert thresh == tp._GATE_CRUNCH
        else:
            assert all(p is None or p.key != tp.GATE_KEY for p in built.gear.pre_pedals)


def test_a_projects_untouched_preset_gets_the_gate_but_a_rebuilt_chain_does_not() -> None:
    from rockforge.infrastructure.packaging.gear import tone_presets as tp

    old = {"key": "RFLead_Metal", "pre": [
        {"key": "Pedal_MetalDistortion", "knobs": {"Pedal_MetalDistortion_Gain": 50}},
        None, None, None,
    ]}
    gated = tp.with_preset_gate(old)
    assert gated is not None
    assert [p and p["key"] for p in gated["pre"]] == [
        tp.GATE_KEY, "Pedal_MetalDistortion", None, None,
    ]
    assert tp.with_preset_gate(gated) is None  # already there
    assert tp.with_preset_gate({"key": "RFLead_Crunch"})["pre"][0]["key"] == tp.GATE_KEY
    # the user's own chain, a clean preset, a tone that is not a preset
    assert tp.with_preset_gate({"key": "RFLead_Metal", "pre": [{"key": "Pedal_Chorus"}]}) is None
    assert tp.with_preset_gate({"key": "RFLead_Clean", "pre": [{"key": "Pedal_Chorus"}]}) is None
    assert tp.with_preset_gate({"key": "mine"}) is None
