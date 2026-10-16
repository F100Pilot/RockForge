"""A note shorter than a beat is charted with no sustain, as hand-made charts do.

Every Guitar Pro note has a length, and writing each eighth's length as a
sustain drew a tail on every note of a riff ("every single note looks extended
when they aren't")."""

from __future__ import annotations

import zipfile
from pathlib import Path

import guitarpro as gp

from rockforge.domain.music import BendPoint, TabNote, Technique, drop_short_sustains
from rockforge.infrastructure.gpimport.parser import parse_gp_track

BEATS = [i * 0.5 for i in range(20)]  # 120 BPM


def _note(time: float, sustain: float, **kw: object) -> TabNote:
    return TabNote(string=0, fret=5, time=time, sustain=sustain, **kw)  # type: ignore[arg-type]


def test_notes_shorter_than_a_beat_lose_their_sustain() -> None:
    notes = [_note(0.0, 0.125), _note(0.125, 0.25), _note(0.5, 0.375),  # 16th, 8th, dotted 8th
             _note(1.0, 0.5), _note(2.0, 2.0)]                         # quarter, whole
    assert [n.sustain for n in drop_short_sustains(notes, BEATS)] == [0.0, 0.0, 0.0, 0.5, 2.0]


def test_a_short_note_keeps_the_sustain_its_technique_is_drawn_on() -> None:
    kept = [
        _note(0.0, 0.25, slide_to_fret=7),
        _note(1.0, 0.25, slide_unpitch_to=0),
        _note(2.0, 0.25, link_next=True),
        _note(3.0, 0.25, trill_fret=7),
        _note(4.0, 0.25, bend_semitones=1.0, bend_points=(BendPoint(1.0, 1.0),)),
        _note(4.5, 0.25, techniques=frozenset({Technique.BEND})),
        _note(5.0, 0.25, techniques=frozenset({Technique.VIBRATO})),
        _note(6.0, 0.25, techniques=frozenset({Technique.LET_RING})),
        _note(7.0, 0.25, techniques=frozenset({Technique.TREMOLO})),
    ]
    assert [n.sustain for n in drop_short_sustains(kept, BEATS)] == [0.25] * len(kept)
    plain = _note(8.0, 0.25, techniques=frozenset({Technique.PALM_MUTE}))
    assert drop_short_sustains([plain], BEATS)[0].sustain == 0.0


def test_the_beat_is_the_grids_own_where_the_note_is() -> None:
    """At 60 BPM from 4 s an eighth lasts 0.5 s, still half a beat."""
    beats = [0.0, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 5.0]
    notes = [_note(0.0, 0.5), _note(4.0, 0.5), _note(5.5, 1.0)]  # after the last beat too
    assert [n.sustain for n in drop_short_sustains(notes, beats)] == [0.5, 0.0, 1.0]


def _gp5(tmp_path: Path) -> Path:
    """120 BPM, 4/4: four eighths, a bent eighth, a quarter, then a half note."""
    song = gp.Song()
    song.tempo = 120
    voice = song.tracks[0].measures[0].voices[0]
    voice.beats = []
    for value, fret, bend in [(8, 3, False), (8, 5, False), (8, 3, False), (8, 5, False),
                              (8, 7, True), (4, 5, False), (2, 3, False)]:
        beat = gp.Beat(voice)
        beat.status, beat.duration = gp.BeatStatus.normal, gp.Duration(value=value)
        note = gp.Note(beat)
        note.string, note.value = 6, fret
        if bend:
            note.effect.bend = gp.BendEffect(
                type=gp.BendType.bend, value=4,
                points=[gp.BendPoint(0, 0), gp.BendPoint(12, 4)])
        beat.notes.append(note)
        voice.beats.append(beat)
    song.newMeasure()
    path = tmp_path / "riff.gp5"
    gp.write(song, str(path))
    return path


def test_a_gp5_riff_of_eighths_has_no_tails_but_its_held_notes_do(tmp_path: Path) -> None:
    notes = parse_gp_track(_gp5(tmp_path), 0).notes
    held = [(round(n.time, 2), n.fret, n.sustain > 0) for n in notes]
    assert held == [(0.0, 3, False), (0.25, 5, False), (0.5, 3, False), (0.75, 5, False),
                    (1.0, 7, True), (1.25, 5, True), (1.75, 3, True)]


def test_a_gp7_riff_of_eighths_has_no_tails(tmp_path: Path) -> None:
    from test_gp_playback import _GPIF

    path = tmp_path / "riff.gp"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("VERSION", "7.0")
        z.writestr("Content/score.gpif", _GPIF.format(sync="").replace(
            "<NoteValue>Whole</NoteValue>", "<NoteValue>Eighth</NoteValue>"))
    notes = parse_gp_track(path, 0).notes
    assert notes and all(n.sustain == 0 for n in notes)
