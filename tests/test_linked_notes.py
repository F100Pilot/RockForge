"""Linked notes (Rocksmith's linkNext): read from a Guitar Pro legato slide,
kept only where DLC Builder's own checker would accept them.

The rules are Rocksmith2014.NET's: XmlToSngNote links a note to the NEXT note
on its string when that note starts within 2 ms of the linked note's end, and
InstrumentalChecker refuses a link into a chord, away from the end, onto
another fret than the note (or its slide's landing fret), with a bend that
does not carry on, or after an unpitched slide.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
import zipfile
from dataclasses import replace
from pathlib import Path

import guitarpro as gp

from rockforge.domain.arrangement import Arrangement, ArrangementKind, Section, SongMetadata
from rockforge.domain.music import (
    Beat,
    BendPoint,
    TabNote,
    Technique,
    TempoMap,
    Tuning,
    apply_sustain_gap,
    resolve_links,
)
from rockforge.infrastructure.gpimport.parser import parse_gp_track
from rockforge.infrastructure.packaging.psarc.sng import (
    NOTE_MASK_CHILD,
    NOTE_MASK_PARENT,
    from_arrangement,
)
from rockforge.infrastructure.packaging.psarc.sng_build import _good_phrase_time
from rockforge.infrastructure.packaging.psarc.verify import check_sng
from rockforge.infrastructure.rsxml.reader import read_arrangement_xml
from rockforge.infrastructure.rsxml.writer import render_arrangement
from test_gpif_import import GPIF


def _pair(**parent: object) -> list[TabNote]:
    base: dict[str, object] = {"string": 1, "fret": 5, "time": 1.0, "sustain": 0.5,
                               "link_next": True}
    base.update(parent)
    return [TabNote(**base), TabNote(string=1, fret=5, time=1.5, sustain=0.5)]  # type: ignore[arg-type]


def test_a_link_into_the_next_note_is_kept_and_ends_on_it() -> None:
    notes = _pair(sustain=0.4987)  # a sync correction left it a hair short
    out = resolve_links(notes)
    assert out[0].link_next
    assert out[0].time + out[0].sustain == out[1].time


def test_a_slide_links_into_the_note_it_lands_on() -> None:
    out = resolve_links([
        TabNote(string=2, fret=5, time=0.0, sustain=0.5, link_next=True,
                techniques=frozenset({Technique.SLIDE}), slide_to_fret=7),
        TabNote(string=2, fret=7, time=0.5, sustain=1.0),
    ])
    assert out[0].link_next


def test_links_the_checker_would_refuse_are_cleared() -> None:
    cases = {
        "next note on another fret": [
            TabNote(string=1, fret=5, time=1.0, sustain=0.5, link_next=True),
            TabNote(string=1, fret=8, time=1.5, sustain=0.5),
        ],
        "slide lands elsewhere": [
            TabNote(string=1, fret=5, time=1.0, sustain=0.5, link_next=True,
                    techniques=frozenset({Technique.SLIDE}), slide_to_fret=9),
            TabNote(string=1, fret=7, time=1.5, sustain=0.5),
        ],
        "next note starts later": _pair(sustain=0.3),
        "next note is in a chord": [
            *_pair(),
            TabNote(string=3, fret=7, time=1.5, sustain=0.5),
        ],
        "unpitched slide": _pair(slide_unpitch_to=1),
        "bend not carried on": _pair(
            bend_semitones=2.0, bend_points=(BendPoint(0.0, 0.0), BendPoint(1.0, 2.0)),
            techniques=frozenset({Technique.BEND}),
        ),
        "nothing after it": [TabNote(string=1, fret=5, time=1.0, sustain=0.5, link_next=True)],
    }
    for why, notes in cases.items():
        assert not resolve_links(notes)[0].link_next, why


def test_a_bend_held_into_the_next_note_keeps_the_link() -> None:
    held = BendPoint(0.0, 2.0)
    out = resolve_links([
        TabNote(string=1, fret=7, time=0.0, sustain=0.5, link_next=True,
                techniques=frozenset({Technique.BEND}), bend_semitones=2.0,
                bend_points=(BendPoint(0.0, 0.0), BendPoint(1.0, 2.0))),
        TabNote(string=1, fret=7, time=0.5, sustain=0.5,
                techniques=frozenset({Technique.BEND}), bend_semitones=2.0,
                bend_points=(held, BendPoint(1.0, 2.0))),
    ])
    assert out[0].link_next


def test_the_sustain_gap_leaves_a_linked_note_reaching_the_next() -> None:
    out = apply_sustain_gap(_pair())
    assert out[0].sustain == 0.5


def _gp5_slide(tmp_path: Path, slide: gp.SlideType) -> Path:
    song = gp.Song()
    song.tempo = 120
    voice = song.tracks[0].measures[0].voices[0]
    for fret, slides in ((5, [slide]), (7, []), (0, [])):
        beat = gp.Beat(voice)
        beat.status = gp.BeatStatus.normal
        beat.duration = gp.Duration(value=4)
        note = gp.Note(beat)
        note.string, note.value, note.type = 5, fret, gp.NoteType.normal
        note.effect.slides = slides
        beat.notes.append(note)
        voice.beats.append(beat)
    path = tmp_path / f"slide{int(slide.value)}.gp5"
    gp.write(song, str(path))
    return path


def test_a_gp5_legato_slide_links_its_landing_note(tmp_path: Path) -> None:
    notes = sorted(parse_gp_track(_gp5_slide(tmp_path, gp.SlideType.legatoSlideTo), 0).notes,
                   key=lambda n: n.time)
    first, landing = notes[0], notes[1]
    assert first.link_next and first.slide_to_fret == 7
    assert first.time + first.sustain == landing.time
    assert resolve_links(notes)[0].link_next


def test_a_gp5_shift_slide_is_picked_again(tmp_path: Path) -> None:
    notes = sorted(parse_gp_track(_gp5_slide(tmp_path, gp.SlideType.shiftSlideTo), 0).notes,
                   key=lambda n: n.time)
    assert not notes[0].link_next and notes[0].slide_to_fret == 7


def test_a_gp7_legato_slide_links_its_landing_note(tmp_path: Path) -> None:
    path = tmp_path / "legato.gp"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("VERSION", "7.0")
        z.writestr("Content/score.gpif",
                   GPIF.replace('<Property name="Slide"><Flags>1</Flags></Property>',
                                '<Property name="Slide"><Flags>2</Flags></Property>'))
    notes = parse_gp_track(path, 0).notes
    slide = next(n for n in notes if Technique.SLIDE in n.techniques)
    assert slide.link_next and slide.slide_to_fret == 9
    assert resolve_links(notes)[notes.index(slide)].link_next


# --- the built chart -----------------------------------------------------------

def _linked_chart() -> Arrangement:
    """A slide held into its landing note, a plain held note, and a chord whose
    G string is held on into a single note — over enough bars for DD levels."""
    beats = tuple(Beat(time=round(1.0 + 0.5 * i, 3), measure=(i // 4 + 1) if i % 4 == 0 else -1)
                  for i in range(60))
    notes = [TabNote(3, 2 + k % 5, 2.0 + 0.4 * k, 0.1) for k in range(20)]
    notes += [
        TabNote(2, 5, 12.0, 0.5, frozenset({Technique.SLIDE}), slide_to_fret=7, link_next=True),
        TabNote(2, 7, 12.5, 0.4),
        TabNote(1, 3, 14.0, 0.25, link_next=True),
        TabNote(1, 3, 14.25, 0.3),
        TabNote(0, 3, 16.0, 0.5), TabNote(1, 5, 16.0, 0.5),
        TabNote(2, 5, 16.0, 0.5, link_next=True),
        TabNote(2, 5, 16.5, 0.5),
    ]
    return Arrangement(
        kind=ArrangementKind.LEAD, metadata=SongMetadata(title="L", artist="A", song_length=31.0),
        tuning=Tuning(), notes=resolve_links(notes),
        sections=[Section("verse", 1.0, 1)],
        tempo_map=TempoMap(beats=beats, average_bpm=120.0),
    )


def test_the_xml_carries_link_next_and_the_reader_brings_it_back(tmp_path: Path) -> None:
    arr = _linked_chart()
    song = render_arrangement(arr)
    linked = {(n.get("time"), n.get("string")) for n in song.iter("note")
              if n.get("linkNext") == "1"}
    assert linked == {("12.000", "2"), ("14.000", "1")}
    chord = next(c for c in song.iter("chord") if c.get("time") == "16.000")
    assert chord.get("linkNext") == "1"
    assert [cn.get("linkNext", "0") for cn in chord.iter("chordNote")] == ["0", "0", "1"]
    # The sustain is written to end exactly where the next note starts, in the
    # file's own millisecond rounding (DLC Builder links within 2 ms of the end).
    slide = next(n for n in song.iter("note") if n.get("time") == "12.000")
    assert float(slide.get("time")) + float(slide.get("sustain")) == 12.5
    odd = render_arrangement(replace(arr, notes=[
        TabNote(1, 5, 1.2346, 0.2655, link_next=True), TabNote(1, 5, 1.5001, 0.2)]))
    first = next(odd.iter("note"))
    assert abs(float(first.get("time")) + float(first.get("sustain")) - 1.5) < 1e-9

    path = tmp_path / "a.xml"
    ET.ElementTree(song).write(path)
    back = read_arrangement_xml(path)
    assert sorted((n.time, n.string) for n in back.notes if n.link_next) == [
        (12.0, 2), (14.0, 1), (16.0, 2)]


def test_the_sng_marks_parent_and_child_at_every_level() -> None:
    model = from_arrangement(_linked_chart())
    assert len(model.arrangements) > 1
    for lv in model.arrangements:
        notes = lv.notes
        children = [(i, n) for i, n in enumerate(notes) if n.mask & NOTE_MASK_CHILD]
        # A linked pair is shown together or not at all.
        times = {round(n.time, 3) for n in notes}
        assert (12.0 in times) == (12.5 in times) and (14.0 in times) == (14.25 in times)
        for i, n in children:
            parent = notes[n.parent_prev_note]
            assert n.parent_prev_note < i and parent.mask & NOTE_MASK_PARENT
        assert {round(n.time, 3) for _, n in children} == times & {12.5, 14.25, 16.5}
        for n in notes:
            if not n.mask & NOTE_MASK_CHILD:
                assert n.parent_prev_note == -1
        chord = next((n for n in notes if n.chord_id >= 0 and round(n.time, 3) == 16.0), None)
        if chord is not None:
            assert chord.mask & NOTE_MASK_PARENT
            masks = model.chord_notes[chord.chord_notes_id].note_mask
            assert [bool(m & NOTE_MASK_PARENT) for m in masks[:3]] == [False, False, True]
        assert check_sng(model) == []


def test_a_phrase_is_not_started_on_a_note_a_link_runs_into() -> None:
    """findGoodPhraseTime's linkNext rule: on the note a linked note runs into,
    the phrase goes back to where the link starts, or past that note."""
    singles = [TabNote(1, 5, 1.0, 0.5, link_next=True), TabNote(1, 5, 1.5, 0.3)]
    assert _good_phrase_time(singles, 1.5) == (1.0, 1.8)
    chord = [TabNote(0, 3, 3.0, 0.5), TabNote(1, 5, 3.0, 0.5, link_next=True)]
    held = [TabNote(1, 5, 3.5, 0.0)]
    earlier, later = _good_phrase_time(held, 3.5, chords=[chord])
    assert earlier == 3.0 and abs(later - 3.6) < 1e-9


def test_without_resolve_links_a_refused_link_never_reaches_the_sng() -> None:
    arr = _linked_chart()
    broken = [replace(n, link_next=True) if n.time == 2.0 else n for n in arr.notes]
    model = from_arrangement(replace(arr, notes=resolve_links(broken)))
    assert check_sng(model) == []
