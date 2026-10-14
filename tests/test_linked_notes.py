"""Linked notes (Rocksmith's linkNext): read from a Guitar Pro legato slide,
kept only where DLC Builder's own checker would accept them.

The rules are Rocksmith2014.NET's: XmlToSngNote links a note to the NEXT note
on its string when that note starts within 2 ms of the linked note's end, and
InstrumentalChecker refuses a link into a chord, away from the end, onto
another fret than the note (or its slide's landing fret), with a bend that
does not carry on, or after an unpitched slide.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import guitarpro as gp

from rockforge.domain.music import BendPoint, TabNote, Technique, apply_sustain_gap, resolve_links
from rockforge.infrastructure.gpimport.parser import parse_gp_track
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
