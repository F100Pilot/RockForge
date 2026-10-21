"""A Songsterr tab written as a Guitar Pro 5 file, then read by our importer.

The parts are shaped like the JSON Songsterr's player draws each track from
(field meanings read off teaqu/guitar-pro-youtube-sync's converter). What is
pinned is the round trip: what the GP5 writer produces is what
``inspect_gp``/``parse_gp_track`` — the same path an uploaded file takes —
read back.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from rockforge.domain.errors import IngestionError
from rockforge.domain.music import Technique
from rockforge.infrastructure.gpimport.parser import inspect_gp, parse_gp_track
from rockforge.infrastructure.gpimport.songsterr_gp import write_songsterr_gp5

STANDARD = [64, 59, 55, 50, 45, 40]  # Songsterr lists the HIGHEST string first


def _lead() -> dict:
    return {
        "name": "Lead", "instrument": "Distortion Guitar", "strings": 6, "tuning": STANDARD,
        "automations": {"tempo": [{"measure": 0, "position": 0, "bpm": 120},
                                  {"measure": 2, "position": 0, "bpm": 60}]},
        "measures": [
            {"signature": [4, 4], "marker": {"text": "Intro"}, "voices": [{"beats": [
                {"type": 4, "notes": [{"string": 5, "fret": 3}]},
                {"type": 4, "notes": [{"string": 5, "fret": 5, "hp": True}]},
                {"type": 4, "notes": [{"string": 0, "fret": 7, "bend": {"points": [
                    {"position": 0, "tone": 0}, {"position": 30, "tone": 100}]}}]},
                {"type": 4, "rest": True},
            ]}]},
            {"voices": [{"beats": [
                {"type": 8, "tuplet": 3, "notes": [{"string": 1, "fret": 1}]},
                {"type": 8, "tuplet": 3, "notes": [{"string": 1, "fret": 1, "tie": True}]},
                {"type": 8, "tuplet": 3, "notes": [{"string": 2, "fret": 2, "dead": True}]},
                {"type": 16, "graceNote": "beforeBeat", "notes": [{"string": 3, "fret": 1}]},
                {"type": 2, "dots": 1, "notes": [
                    {"string": 3, "fret": 2, "vibrato": True, "palmMute": True}]},
            ]}]},
            {"marker": {"text": "Verso"}, "voices": [{"beats": [
                {"type": 1, "notes": [{"string": 4, "fret": 0, "slide": "shift"}]}]}]},
        ],
    }


def _write(tmp_path: Path, parts: list[dict]) -> tuple[Path, object]:
    dst = tmp_path / "tab.gp5"
    report = write_songsterr_gp5(parts, dst, title="Song", artist="Band")
    return dst, report


def test_the_tab_reads_back_note_for_note(tmp_path: Path) -> None:
    dst, report = _write(tmp_path, [_lead()])
    notes = parse_gp_track(dst, 0).notes
    # (time, string low=0, fret) — 120 BPM for two bars, 60 BPM from bar 3.
    assert [(round(n.time, 3), n.string, n.fret) for n in notes] == [
        (0.0, 0, 3), (0.5, 0, 5), (1.0, 5, 7),
        (2.0, 4, 1),            # the tied triplet is ONE note held over two
        (2.333, 3, 2),
        (2.375, 2, 1),          # the grace note: a sixteenth before the note it leads into
        (2.5, 2, 2),
        (4.0, 1, 0),            # bar 3 at 60 BPM starts after 2 bars at 120
    ]
    # Held over two triplet eighths: still 2/3 of a beat, so charted with no tail.
    assert notes[3].sustain == 0.0
    assert round(notes[-1].sustain, 3) == 4.0  # a whole note at 60 BPM
    assert report.notes == 8 and report.graces == 1 and report.grace_dropped == 0


def test_techniques_survive_the_trip(tmp_path: Path) -> None:
    dst, _ = _write(tmp_path, [_lead()])
    notes = parse_gp_track(dst, 0).notes
    techs = [n.techniques for n in notes]
    assert Technique.HAMMER_ON in techs[1]            # hp marks the TARGET note
    assert Technique.BEND in techs[2] and notes[2].bend_semitones == 2.0  # a full tone
    assert Technique.FRET_MUTE in techs[4]            # dead note
    assert {Technique.PALM_MUTE, Technique.VIBRATO} <= techs[6]  # techs[5]: the grace note
    assert Technique.SLIDE in techs[7]


def test_tuning_sections_tempo_and_metadata(tmp_path: Path) -> None:
    dst, _ = _write(tmp_path, [_lead()])
    info = inspect_gp(dst)
    assert (info.title, info.artist, info.tempo) == ("Song", "Band", 120)
    [track] = info.tracks
    assert track.name == "Lead" and track.string_count == 6
    assert track.tuning_midi == (40, 45, 50, 55, 59, 64)   # our order: low → high
    sections = parse_gp_track(dst, 0).sections
    assert [(s.name, round(s.start_time, 3)) for s in sections] == [("Intro", 0.0), ("Verso", 4.0)]


def test_drums_are_left_out_and_said_so(tmp_path: Path) -> None:
    drums = {"name": "Drums", "instrument": "Drums", "tuning": None, "measures": [{}]}
    bass = {**_lead(), "name": "Bass", "strings": 4, "tuning": [43, 38, 33, 28]}
    dst, report = _write(tmp_path, [drums, _lead(), bass])
    assert [t.name for t in inspect_gp(dst).tracks] == ["Lead", "Bass"]
    assert report.skipped_tracks == ["Drums (percussão)"]
    assert any("Drums" in w for w in report.warnings)


def test_a_tab_without_any_stringed_track_is_refused(tmp_path: Path) -> None:
    drums = {"name": "Drums", "instrument": "Drums", "tuning": None, "measures": [{}]}
    with pytest.raises(IngestionError):
        _write(tmp_path, [drums])


def test_odd_meters_keep_every_bar_where_it_belongs(tmp_path: Path) -> None:
    def bar(kind: int, fret: int) -> dict:
        return {"voices": [{"beats": [{"type": kind, "notes": [{"string": 0, "fret": fret}]}]}]}

    part = {"name": "G", "tuning": STANDARD, "measures": [
        {"signature": [7, 8], **bar(8, 1)},
        bar(8, 2),
        {"signature": [3, 4], "voices": []},  # an empty bar still takes its time
        bar(4, 3),
    ]}
    dst, _ = _write(tmp_path, [part])
    # 7/8 at 120 BPM = 1.75 s per bar; an under-filled bar does not pull the next in.
    assert [round(n.time, 3) for n in parse_gp_track(dst, 0).notes] == [0.0, 1.75, 5.0]


def _q(fret: int, string: int = 5) -> dict:
    return {"type": 4, "notes": [{"string": string, "fret": fret}]}


def _guitar_and_vocals(**vocal_extra: object) -> list[dict]:
    """A guitar strumming quarters and a vocal line with its own rhythm — the
    lyrics belong to the vocal line, whose notes do not match the guitar's."""
    guitar = {
        "name": "Guitar", "instrument": "Overdriven Guitar", "strings": 6, "tuning": STANDARD,
        "automations": {"tempo": [{"measure": 0, "position": 0, "bpm": 120}]},
        "measures": [
            {"signature": [4, 4], "voices": [{"beats": [_q(0), _q(2), _q(3), _q(5)]}]},
            {"voices": [{"beats": [_q(0), _q(2), _q(3), _q(5)]}]},
            {"voices": [{"beats": [{"type": 1, "notes": [{"string": 5, "fret": 0}]}]}]},
        ],
        "newLyrics": [],
    }
    eighth = {"type": 8, "notes": [{"string": 0, "fret": 7}]}
    vocals = {
        "name": "Vocals", "instrument": "Voice Oohs", "strings": 1, "tuning": [64],
        "measures": [
            {"voices": [{"beats": [{"type": 1, "rest": True}]}]},
            {"voices": [{"beats": [eighth] * 8}]},
            {"voices": [{"beats": [
                {"type": 2, "notes": [{"string": 0, "fret": 5}]},
                {"type": 4, "rest": True},
                {"type": 4, "notes": [{"string": 0, "fret": 3}]},
            ]}]},
        ],
        "newLyrics": [
            {"text": "Hel-lo  world is here now", "offset": 1},
            {"text": "la la", "offset": 2},
        ],
        **vocal_extra,
    }
    return [guitar, vocals]


def test_songsterr_lyrics_are_written_on_the_part_that_sings_them(tmp_path: Path) -> None:
    dst, report = _write(tmp_path, _guitar_and_vocals())
    assert inspect_gp(dst).has_lyrics
    assert report.lyric_lines == 2
    parsed = parse_gp_track(dst, 0)  # the GUITAR is the chart
    # Each line starts on its (0-based) Songsterr offset's bar: bars 2 and 3.
    assert [(line.time, line.text) for line in parsed.lyrics] == [
        (2.0, "Hel-lo  world is here now"), (4.0, "la la"),
    ]
    # The syllables go to the VOCAL line's notes (rests skipped), not the guitar's.
    assert parsed.lyric_notes is not None
    assert tuple(n.time for n in parsed.lyric_notes) == (
        2.0, 2.25, 2.5, 2.75, 3.0, 3.25, 3.5, 3.75, 4.0, 5.5,
    )


def test_lyrics_on_a_part_that_could_not_be_written_fall_back_and_say_so(
    tmp_path: Path,
) -> None:
    dst, report = _write(tmp_path, _guitar_and_vocals(tuning=[]))  # no strings
    parsed = parse_gp_track(dst, 0)
    assert parsed.lyrics and parsed.lyric_notes is not None
    assert tuple(n.time for n in parsed.lyric_notes) == (
        0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0,
    )
    assert any("primeira pista" in w for w in report.warnings)


def test_text_gp5_cannot_store_does_not_abort_the_import(tmp_path: Path) -> None:
    parts = _guitar_and_vocals()
    parts[1]["newLyrics"] = [{"text": "Кино ok", "offset": 1}]
    dst = tmp_path / "tab.gp5"
    write_songsterr_gp5(parts, dst, title="Группа крови", artist="Кино")
    assert parse_gp_track(dst, 0).lyrics[0].text == "???? ok"


def test_the_tabs_tempo_map_gives_each_bar_its_exact_start() -> None:
    """Decimals, a mid-bar change and a change of metre, as the player plays them."""
    from rockforge.infrastructure.gpimport.songsterr_gp import tab_bar_times

    # 4/4 at 120 = 2 s a bar; at 117.85 a bar lasts 4 * 60 / 117.85 s.
    assert tab_bar_times([4.0, 4.0, 4.0], [], 120.0) == [0.0, 2.0, 4.0]
    bar = 240 / 117.85
    times = tab_bar_times([4.0, 4.0, 4.0], [(1, 0.0, 117.85)], 120.0)
    assert times[:2] == [0.0, 2.0] and times[2] == pytest.approx(2.0 + bar)
    # Halfway through bar 2 the tempo halves: 1 s + 2 s, so bar 3 starts at 5 s.
    assert tab_bar_times([4.0, 4.0, 4.0], [(1, 0.5, 60.0)], 120.0) == [0.0, 2.0, 5.0]
    # 3/4 is three quarters: 1.5 s at 120.
    assert tab_bar_times([3.0, 4.0], [], 120.0) == [0.0, 1.5]


def test_a_tab_that_follows_a_recording_keeps_its_tempo_to_the_decimal(tmp_path: Path) -> None:
    """GP5 holds a whole BPM at a bar's start, so the tab's own map travels as
    bar times; the GP5's tempo is rounded (int() made 117.85 BPM 117, a drift
    that grew bar by bar) and a mid-bar change is counted."""
    part = _lead()
    part["automations"] = {"tempo": [
        {"measure": 0, "position": 0, "bpm": 117.85},
        {"measure": 1, "position": 0.5, "bpm": 90.4},
    ]}
    dst, report = _write(tmp_path, [part])
    assert inspect_gp(dst).tempo == 118
    assert report.tempo_count == 2 and report.tempo_decimal and report.tempo_moved == 1
    q = 240 / 117.85
    assert report.bar_times == pytest.approx([0.0, q, q + q / 2 + 120 / 90.4])
    assert any("meio do compasso" in w or "mid-bar" in w for w in report.warnings)

    # Those times re-time the chart: bar 3's note lands where the player plays it.
    exact = parse_gp_track(dst, 0, bar_times=report.bar_times).notes
    assert exact[-1].time == pytest.approx(report.bar_times[2], abs=1e-6)
    # Without them the GP5's whole BPMs put it elsewhere.
    plain = parse_gp_track(dst, 0).notes
    assert abs(plain[-1].time - report.bar_times[2]) > 0.05


def test_a_tab_at_one_whole_tempo_says_so(tmp_path: Path) -> None:
    part = _lead()
    part["automations"] = {"tempo": [{"measure": 0, "position": 0, "bpm": 100}]}
    _dst, report = _write(tmp_path, [part])
    assert (report.tempo_count, report.tempo_decimal) == (1, False)
    assert report.bar_times == pytest.approx([0.0, 2.4, 4.8])


def test_a_tempo_change_at_a_position_that_cannot_be_read_is_said(tmp_path: Path) -> None:
    """A ``position`` of 1 or more is no fraction of the bar (a unit never seen):
    it is read as the bar's start, but counted and said, never silently."""
    part = _lead()
    part["automations"] = {"tempo": [
        {"measure": 0, "position": 0, "bpm": 120},
        {"measure": 1, "position": 480, "bpm": 60},
    ]}
    _dst, report = _write(tmp_path, [part])
    assert report.tempo_position_unknown == 1 and report.tempo_moved == 0
    assert report.bar_times == pytest.approx([0.0, 2.0, 6.0])  # bar 2 at 60 from its start
    assert any("não sei ler" in w or "cannot read" in w for w in report.warnings)


def test_a_grace_note_in_the_vocal_line_takes_its_own_syllable(tmp_path: Path) -> None:
    """Songsterr (and Guitar Pro) hand a syllable to every beat of the lyrics'
    track that is not a rest — a grace note too. Dropped, every syllable after
    it landed one note late ("a letra fica sempre atrasada")."""
    from rockforge.infrastructure.rsxml.vocals import distribute_syllables

    vocals = {"name": "Voz", "tuning": [64], "measures": [{"signature": [4, 4], "voices": [{"beats": [
        {"type": 4, "notes": [{"string": 0, "fret": 2}]},
        {"type": 16, "graceNote": "beforeBeat", "notes": [{"string": 0, "fret": 4}]},
        {"type": 4, "notes": [{"string": 0, "fret": 5}]},
        {"type": 4, "notes": [{"string": 0, "fret": 4}]},
        {"type": 4, "notes": [{"string": 0, "fret": 2}]},
    ]}]}], "newLyrics": [{"text": "one two three four five", "offset": 0}]}
    dst, report = _write(tmp_path, [_lead(), vocals])
    parsed = parse_gp_track(dst, 0)
    assert report.graces == 2  # the lead's and the vocal line's
    onsets = [round(n.time, 3) for n in parsed.lyric_notes]
    assert onsets == [0.0, 0.375, 0.5, 1.0, 1.5]  # 120 BPM: the grace a sixteenth before beat 2
    events = distribute_syllables(
        [(line.time, line.text) for line in parsed.lyrics],
        [n.time for n in parsed.lyric_notes], ends=[n.end for n in parsed.lyric_notes])
    assert [(round(e.time, 3), e.lyric.rstrip("+")) for e in events] == [
        (0.0, "one"), (0.375, "two"), (0.5, "three"), (1.0, "four"), (1.5, "five")]
