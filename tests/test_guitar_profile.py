"""The player's guitar and bass (``infrastructure/guitar_profile.py``): stored
on its own, carried into the tone requests, and a small, said fit of the
driven presets."""

from __future__ import annotations

import importlib

import pytest

from rockforge import i18n


@pytest.fixture
def gp(tmp_path, monkeypatch):
    monkeypatch.setenv("ROCKFORGE_WORK_DIR", str(tmp_path))
    from rockforge import config

    importlib.reload(config)
    from rockforge.infrastructure import guitar_profile

    return guitar_profile


@pytest.fixture
def english():
    token = i18n.use("en")
    yield
    i18n.reset(token)


def _profile(pickups: str = "", output: str = "", name: str = "") -> dict:
    return {"guitar": {"pickups": pickups, "output": output, "name": name},
            "bass": {"pickups": "", "output": "", "name": ""}}


def test_only_known_values_are_kept_and_the_profile_comes_back(gp) -> None:
    assert gp.load() == _profile()
    stored = gp.save({"guitar": {"pickups": "single", "output": "loud",
                                 "name": "  Fender   Strat "},
                      "bass": {"pickups": "humbucker", "output": "high"}})
    assert stored["guitar"] == {"pickups": "single", "output": "", "name": "Fender Strat"}
    # a guitar's pickup type is not a bass's
    assert stored["bass"] == {"pickups": "", "output": "high", "name": ""}
    assert gp.load() == stored
    assert (gp._file()).name == "guitar_profile.json"


def test_the_request_says_what_the_player_plays(gp, english) -> None:
    assert gp.describe(_profile()) == ""
    text = gp.describe({**_profile("active", "high", "ESP LTD"),
                        "bass": {"pickups": "passive", "output": "", "name": "P-Bass"}},
                       guitar=True, bass=True)
    assert "My guitar: ESP LTD, active pickups, high output" in text
    assert "My bass: P-Bass, passive pickups" in text
    # only the instruments the request is for
    assert "bass" not in gp.describe({**_profile("single"), "bass": {
        "pickups": "passive", "output": "", "name": ""}}, guitar=True, bass=False).lower()


def test_hot_pickups_take_gain_off_and_close_the_gate(gp, english) -> None:
    from rockforge.infrastructure.packaging.gear import tone_presets

    preset = tone_presets._preset("RFLead_HighGain")
    fitted, changes = gp.fit_tone(preset, _profile("active"))
    assert fitted["amp"]["knobs"]["Amp_CA100_Gain"] == 75      # 85 - 10 % of 1..100
    assert fitted["pre"][0]["knobs"]["Pedal_NoiseGate_Thresh"] == -50
    assert len(changes) == 2 and "hot pickups" in changes[0]
    # the preset itself is untouched
    assert preset["amp"]["knobs"]["Amp_CA100_Gain"] == 85
    assert preset["pre"][0]["knobs"]["Pedal_NoiseGate_Thresh"] == -55


def test_single_coils_close_the_gate_and_a_weak_guitar_gets_more_gain(gp) -> None:
    from rockforge.infrastructure.packaging.gear import tone_presets

    preset = tone_presets._preset("RFRhythm_Crunch")
    fitted, changes = gp.fit_tone(preset, _profile("single"))
    assert fitted["amp"]["knobs"] == preset["amp"]["knobs"]
    assert fitted["pre"][0]["knobs"]["Pedal_NoiseGate_Thresh"] == -60   # -65 + 5
    assert len(changes) == 1
    weak, changes = gp.fit_tone(preset, _profile("humbucker", "low"))
    assert weak["amp"]["knobs"]["Amp_MarshallJCM800_Gain"] == 55       # 50 + 5 %
    assert len(changes) == 1
    # both: never past the gate's own maximum
    both, _ = gp.fit_tone(tone_presets._preset("RFLead_Metal"), _profile("single", "high"))
    assert both["pre"][0]["knobs"]["Pedal_NoiseGate_Thresh"] == -45


def test_only_driven_presets_are_fitted_and_a_silent_profile_changes_nothing(gp) -> None:
    from rockforge.infrastructure.packaging.gear import tone_presets

    clean = tone_presets._preset("RFLead_Clean")
    assert gp.fit_tone(clean, _profile("active", "high")) == (clean, [])
    driven = tone_presets._preset("RFLead_Crunch")
    assert gp.fit_tone(driven, _profile()) == (driven, [])
    own = {**driven, "key": "my_own_tone"}           # the user's tone, not a preset
    assert gp.fit_tone(own, _profile("active")) == (own, [])
    out = gp.fit_tones([driven, clean, "x"], _profile("active"))
    assert out[0]["fitted"] and "fitted" not in out[1] and out[2] == "x"
