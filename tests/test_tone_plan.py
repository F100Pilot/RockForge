"""Tones pasted as text (a chatbot's answer) → the project's tones and each
chart's tone changes (``infrastructure/tone_plan.py``). Invented songs only."""

from __future__ import annotations

import json

import pytest

from rockforge import i18n
from rockforge.infrastructure.packaging.gear.gear_catalogue import TONE_DESCRIPTORS
from rockforge.infrastructure.tone_plan import (
    ChartContext,
    PlanContext,
    TonePlanError,
    build_prompt,
    cabinet_for_amp,
    extract_plan,
    match_gear,
    read_plan,
)

BARS = [2.0 + 2 * i for i in range(60)]          # bar N at 2N s, in the build's clock
SECTIONS = [("Intro", 2.0), ("Verse", 10.0), ("Chorus", 26.0), ("Verse", 42.0),
            ("Chorus", 58.0), ("Solo", 74.0)]


@pytest.fixture(autouse=True)
def _english():
    token = i18n.use("en")
    yield
    i18n.reset(token)


def _ctx(bass: bool = False, pad: float = 2.0) -> PlanContext:
    charts = [ChartContext("Lead", "LEAD", BARS, SECTIONS, 122.0, 2.0),
              ChartContext("Rhythm", "RHYTHM", BARS, SECTIONS, 122.0, 2.0)]
    if bass:
        charts.append(ChartContext("Bass", "BASS", BARS, SECTIONS, 122.0, 2.0))
    return PlanContext("Deriva", "Banda Inventada", pad, charts)


def _plan(tones, changes=(), **extra) -> str:
    return json.dumps({"tones": list(tones), "changes": list(changes), **extra})


CLEAN = {"name": "Clean", "amp": {"key": "Amp_TW22"}, "cabinet": "Cab_TW112C_57_Cone"}
DIRT = {"name": "Dirt", "amp": {"key": "Amp_MarshallJCM800"},
        "cabinet": "Cab_Marshall1960a_57_Cone"}


def _track(res, kind):
    return next(t for t in res.tracks if t.kind == kind)


# --- reading the text ---------------------------------------------------------

def test_the_json_is_found_inside_a_chatbot_answer_and_its_slips_forgiven() -> None:
    text = """Here are the tones I would use!
```json
{
  “tones”: [
    {"name": "Clean", "amp": "Amp_TW22",},   // the intro
    /* a block comment */
  ],
  "changes": [{"track": "all", "at": "start", "tone": "Clean"},],
}
```
Let me know if you want more."""
    data = extract_plan(text)
    assert data["tones"] == [{"name": "Clean", "amp": "Amp_TW22"}]
    assert extract_plan('Sure: {"tons": []} — done')["tons"] == []
    # A URL in a string is not a comment.
    assert extract_plan('{"tones": [], "sources": ["https://example.org/rig"]}')["sources"] == [
        "https://example.org/rig"]


def test_a_text_that_is_not_a_tone_plan_is_refused_never_guessed() -> None:
    for text in ("The intro is clean, then a Marshall at bar 33.", '{"other": 1}', "{broken"):
        with pytest.raises(TonePlanError, match="Copy the request"):
            extract_plan(text)
    with pytest.raises(TonePlanError, match="too long"):
        extract_plan("{" + " " * 200_001 + "}")
    with pytest.raises(TonePlanError, match="no tone"):
        read_plan('{"tones": []}', _ctx())
    with pytest.raises(TonePlanError, match="none of the block"):
        read_plan(_plan([{"name": "X", "amp": "Amp_DoesNotExist999"}]), _ctx())


# --- gear and knobs -----------------------------------------------------------

def test_gear_is_found_by_key_by_game_name_or_by_the_real_gear_its_key_names() -> None:
    assert match_gear("Amp_MarshallJCM800", "Amps")[0]["Key"] == "Amp_MarshallJCM800"
    assert match_gear("amp_marshalljcm800", "Amps") == (match_gear("Amp_MarshallJCM800",
                                                                    "Amps")[0], True)
    name = match_gear("Amp_CA100", "Amps")[0]["Name"]
    assert match_gear(name, "Amps") == (match_gear("Amp_CA100", "Amps")[0], True)
    assert match_gear("Marshall JCM800", "Amps")[1] is True       # the key without its prefix
    approx, exact = match_gear("Marshall JCM800 2203 (1981)", "Amps")
    assert approx["Key"] == "Amp_MarshallJCM800" and exact is False
    assert match_gear("Mesa Dual Rectifier", "Amps")[0] is None


def test_each_adaptation_of_a_tone_is_said() -> None:
    tone = {
        "name": "Crunch", "amp": {"key": "Marshall JCM800 2203",
                                  "knobs": {"Gain": "80%", "Treble": 140, "Presense": 40,
                                            "Sparkle": 9}},
        "pre_pedals": ["Pedal_NoiseGate", "Rack_StudioCompressor"] + ["Pedal_NoiseGate"] * 4,
        "volume": 50, "descriptors": "Crunch, Rocking",
    }
    res = read_plan(_plan([tone]), _ctx())
    t = res.tones[0]
    knobs = t["amp"]["knobs"]
    assert knobs["Amp_MarshallJCM800_Gain"] == 80               # 1 + 0.8·99, on its step
    assert knobs["Amp_MarshallJCM800_Treble"] == 100            # clamped
    assert knobs["Amp_MarshallJCM800_Pres"] == 40               # a close spelling
    assert knobs["Amp_MarshallJCM800_Bass"] == 75               # untouched: its default
    assert [p["key"] for p in t["racks"]] == ["Rack_StudioCompressor"]
    assert len(t["pre"]) == 4
    assert t["cabinet"]["key"].startswith("Cab_Marshall") and t["cabinet"]["key"].endswith(
        "_57_Cone")
    assert t["volume"] == -36
    assert t["descriptors"] == [TONE_DESCRIPTORS["Crunch"]]
    said = "\n".join(res.warnings)
    for fragment in ("read as", "outside 1–100", "“Presense” read as “Presence”",
                     "no knob “Sparkle”", "is a rack", "only 4 pedals before the amp",
                     "cabinet chosen for the amp", "volume 50 outside", "“Rocking”"):
        assert fragment in said, fragment


def test_knob_values_read_as_numbers_fractions_percentages_and_labels() -> None:
    tone = {"name": "B", "amp": {"key": "Bass_Amp_BT975B",
                                 "knobs": {"Low-Shift": "Off", "Gain": "7/10"}}}
    res = read_plan(_plan([tone]), _ctx(bass=True))
    knobs = res.tones[0]["amp"]["knobs"]
    assert knobs["Bass_Amp_BT975B_LoShift"] == 0                # an enum by its label
    assert res.tones[0]["cabinet"]["key"].startswith("Bass_Cab_")  # a bass amp, a bass cab


def test_an_amp_with_no_cabinet_gets_the_presets_one_or_one_of_its_family() -> None:
    assert cabinet_for_amp("Amp_MarshallJCM800")["Key"] == "Cab_Marshall1960a_57_Cone"  # presets
    assert cabinet_for_amp("Amp_CA38")["Key"] == "Cab_CA412C_57_Cone"   # family, a 4x12 first
    assert cabinet_for_amp("Amp_OrangeRockerverb")["Key"].startswith("Cab_Orange")
    assert cabinet_for_amp("Amp_EpiphoneZephyr")["Key"] == "Cab_Marshall1960a_57_Cone"
    res = read_plan(_plan([{"name": "Ribbon", "amp": "Amp_MarshallPlexi",
                            "cabinet": {"name": "Marshall 1960a", "mic": "ribbon cone"}}]), _ctx())
    assert res.tones[0]["cabinet"]["key"] == "Cab_Marshall1960a_Ribbon_Cone"


def test_volume_is_the_dlc_builder_scale_louder_when_higher() -> None:
    tones = [{**CLEAN, "name": "a", "volume": 20}, {**CLEAN, "name": "b", "volume": -19.5},
             {**CLEAN, "name": "c"}]
    assert [t["volume"] for t in read_plan(_plan(tones), _ctx()).tones] == [-20, -19.5, -18]


# --- when, and on which chart ------------------------------------------------

def test_bars_sections_and_recording_times_become_the_builds_times() -> None:
    changes = [
        {"track": "all", "at": "start", "tone": "Clean"},
        {"track": "LEAD", "at": "bar 13", "tone": "Dirt"},           # 26 s
        {"track": "LEAD", "at": "c. 21", "tone": "Clean"},           # 42 s
        {"track": "LEAD", "at": "Chorus #2", "tone": "Dirt"},        # 58 s
        {"track": "RHYTHM", "at": "1:10.0", "tone": "Dirt"},         # 70 s + the 2 s pad
        {"track": "RHYTHM", "section": "Solo", "tone": "Clean"},     # 74 s
    ]
    res = read_plan(_plan([CLEAN, DIRT], changes), _ctx())
    lead, rhythm = _track(res, "Lead"), _track(res, "Rhythm")
    clean, dirt = (t["key"] for t in res.tones)
    assert lead.tone_base == clean and lead.tone_names == [clean, dirt]
    assert lead.tone_changes == [(26.0, dirt), (42.0, clean), (58.0, dirt)]
    assert rhythm.tone_changes == [(72.0, dirt), (74.0, clean)]
    assert not res.warnings


def test_moments_that_cannot_be_placed_are_said_and_left_out() -> None:
    changes = [
        {"track": "all", "at": "start", "tone": "Clean"},
        {"track": "LEAD", "at": "Verse", "tone": "Dirt"},            # twice: the first
        {"track": "LEAD", "at": "Bridge", "tone": "Clean"},
        {"track": "LEAD", "at": "bar 99", "tone": "Clean"},
        {"track": "LEAD", "at": "9:00", "tone": "Clean"},
        {"track": "LEAD", "at": "bar 30", "tone": "Fuzz"},
        {"track": "LEAD", "tone": "Clean"},
        {"track": "Keys", "at": "bar 3", "tone": "Clean"},
    ]
    res = read_plan(_plan([CLEAN, DIRT], changes), _ctx())
    assert _track(res, "Lead").tone_changes == [(10.0, res.tones[1]["key"])]
    said = "\n".join(res.warnings)
    for fragment in ("“Verse” occurs 2 times", "no section “Bridge” (there are: Intro, "
                     "Verse #1, Chorus #1, Verse #2, Chorus #2, Solo)", "bar 99 does not exist",
                     "9:00.0 is outside the song", "“Fuzz”, a tone not in “tones”",
                     "with no moment", "no chart “Keys”"):
        assert fragment in said, fragment


def test_all_means_every_guitar_and_the_bass_only_when_named() -> None:
    res = read_plan(_plan([CLEAN, DIRT], [{"track": "all", "at": "start", "tone": "Clean"},
                                          {"track": "baixo", "at": "start", "tone": "Dirt"}]),
                    _ctx(bass=True))
    clean, dirt = (t["key"] for t in res.tones)
    assert {t.kind: t.tone_base for t in res.tracks} == {"Lead": clean, "Rhythm": clean,
                                                          "Bass": dirt}
    res = read_plan(_plan([CLEAN], [{"track": "all", "at": "start", "tone": "Clean"}]),
                    _ctx(bass=True))
    assert [t.kind for t in res.tracks] == ["Lead", "Rhythm"]
    assert "BASS is not mentioned — it keeps the tones it has" in res.warnings


def test_a_chart_with_no_tone_for_its_start_plays_its_first_one_from_the_start() -> None:
    res = read_plan(_plan([CLEAN, DIRT], [{"track": "LEAD", "at": "bar 13", "tone": "Dirt"},
                                          {"track": "LEAD", "at": "bar 21", "tone": "Clean"}]),
                    _ctx())
    lead = _track(res, "Lead")
    assert lead.tone_base == res.tones[1]["key"]
    assert lead.tone_changes == [(42.0, res.tones[0]["key"])]
    assert "LEAD: no tone for the start — it plays" in "\n".join(res.warnings)


def test_a_chart_that_enters_late_takes_the_tone_given_where_it_enters_as_its_base() -> None:
    late = ChartContext("Rhythm", "RHYTHM", BARS, SECTIONS, 122.0, 10.0)
    ctx = PlanContext("S", "A", 2.0, [late])
    res = read_plan(_plan([CLEAN, DIRT], [{"track": "all", "at": "start", "tone": "Clean"},
                                          {"track": "all", "at": "Verse #1", "tone": "Dirt"}]),
                    ctx)
    assert res.tracks[0].tone_base == res.tones[1]["key"] and res.tracks[0].tone_changes == []


def test_a_chart_keeps_at_most_four_tones_the_ones_that_sound_longest() -> None:
    tones = [{**CLEAN, "name": n} for n in ("A", "B", "C", "D", "E")]
    changes = [{"track": "LEAD", "at": "start", "tone": "A"},
               {"track": "LEAD", "at": "bar 5", "tone": "B"},     # 10–12 s: the shortest
               {"track": "LEAD", "at": "bar 6", "tone": "C"},
               {"track": "LEAD", "at": "bar 20", "tone": "D"},
               {"track": "LEAD", "at": "bar 30", "tone": "E"},
               {"track": "LEAD", "at": "bar 40", "tone": "A"},
               {"track": "LEAD", "at": "bar 41", "tone": "A"}]    # already playing: no switch
    res = read_plan(_plan(tones, changes), _ctx())
    lead = _track(res, "Lead")
    key = {t["name"]: t["key"] for t in res.tones}
    assert lead.tone_names == [key["A"], key["C"], key["D"], key["E"]]
    assert lead.tone_changes == [(12.0, key["C"]), (40.0, key["D"]), (60.0, key["E"]),
                                 (80.0, key["A"])]
    assert "switches between 4 tones per chart — left out (the tone before carries on): " \
           + key["B"] in "\n".join(res.warnings)


def test_two_changes_at_one_moment_keep_the_last_and_say_so() -> None:
    res = read_plan(_plan([CLEAN, DIRT], [{"track": "LEAD", "at": "start", "tone": "Clean"},
                                          {"track": "LEAD", "at": "bar 10", "tone": "Dirt"},
                                          {"track": "LEAD", "at": "0:18", "tone": "Clean"},
                                          {"track": "LEAD", "at": "bar 10", "tone": "Dirt"}]),
                    _ctx())
    assert _track(res, "Lead").tone_changes == [(20.0, res.tones[1]["key"])]
    assert "LEAD: two changes at 0:20.0 — the last is kept" in res.warnings


def test_descriptions_sources_and_unused_tones_come_back() -> None:
    res = read_plan(_plan([{**CLEAN, "description": "from a 1996 interview"}, DIRT],
                          [{"at": "start", "tone": "Clean"}], sources=["Guitar World, 1996"]),
                    _ctx())
    assert res.notes == {res.tones[0]["key"]: "from a 1996 interview"}
    assert res.sources == ["Guitar World, 1996"]
    assert "“Dirt” is used by no chart — it is only added to the project's tones" in res.warnings
    assert [t.tone_base for t in res.tracks] == [res.tones[0]["key"]] * 2


# --- the request ---------------------------------------------------------------

def test_the_request_names_the_song_its_sections_and_the_games_gear() -> None:
    prompt = build_prompt(_ctx())
    assert "“Deriva” by Banda Inventada" in prompt
    assert "- Verse #2 — bar 21 — 0:40.0" in prompt                # recording clock
    assert "- LEAD (bars 1–60)" in prompt and "- RHYTHM (bars 1–60)" in prompt
    assert "- Amp_MarshallJCM800 (" in prompt and "Gain [1–100;" in prompt
    assert "Cab_Marshall1960a (" in prompt and "Rack_StudioCompressor" in prompt
    assert "Bass_Amp_" not in prompt                               # no bass chart, no bass gear
    assert "Bass_Amp_" in build_prompt(_ctx(bass=True))
    extracted = extract_plan(prompt)                               # its own example reads back
    assert extracted["tones"][0]["name"] == "Verse crunch"
    token = i18n.use("pt")
    try:
        assert "«Deriva» de Banda Inventada" in build_prompt(_ctx())
    finally:
        i18n.reset(token)
