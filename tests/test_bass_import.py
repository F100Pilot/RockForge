"""A Guitar Pro bass track becomes a 4-string bass chart (GP3-5 path).

Rocksmith's bass has four strings (DLC Builder refuses a bass note on string 4
or higher, I36); a 5-string bass is folded onto the four strings that lose the
fewest notes, and what falls off is counted, never silently dropped.
"""

from __future__ import annotations

from pathlib import Path

import guitarpro as gp
import pytest

from rockforge.domain.errors import IngestionError
from rockforge.infrastructure.gpimport.parser import parse_gp_track


def _bass_gp5(path: Path, pitches_low_to_high: list[int], notes: list[tuple[int, int]]) -> Path:
    """One bar of eighth notes on a bass track; ``notes`` are (string 0 = lowest, fret)."""
    song = gp.Song()
    song.tempo = 120
    n = len(pitches_low_to_high)
    track = song.tracks[0]
    track.name = "Bass"
    track.strings = [gp.GuitarString(i + 1, p) for i, p in enumerate(reversed(pitches_low_to_high))]
    voice = track.measures[0].voices[0]
    for string, fret in notes:
        beat = gp.Beat(voice)
        beat.status = gp.BeatStatus.normal
        beat.duration = gp.Duration(value=8)
        note = gp.Note(beat)
        note.string, note.value, note.type = n - string, fret, gp.NoteType.normal
        beat.notes.append(note)
        voice.beats.append(beat)
    gp.write(song, str(path))
    return path


def test_a_four_string_bass_keeps_its_strings_and_real_pitches(tmp_path: Path) -> None:
    path = _bass_gp5(tmp_path / "b.gp5", [28, 33, 38, 43], [(0, 3), (1, 5), (3, 2)])
    parsed = parse_gp_track(path, 0, bass=True)
    assert [(n.string, n.fret) for n in parsed.notes] == [(0, 3), (1, 5), (3, 2)]
    assert parsed.tuning.bass
    assert parsed.tuning.midi[:4] == (28, 33, 38, 43)
    assert parsed.tuning.offsets_from_standard() == (0, 0, 0, 0, 0, 0)
    assert not parsed.warnings


def test_a_drop_d_bass_carries_its_tuning_on_the_strings_it_does_not_have(tmp_path: Path) -> None:
    # DLC Builder copies string 3's offset into 4 and 5 (EOF writes them wrong).
    path = _bass_gp5(tmp_path / "b.gp5", [26, 31, 36, 41], [(0, 0)])
    assert parse_gp_track(path, 0, bass=True).tuning.offsets_from_standard() == (-2,) * 6


def test_a_five_string_bass_that_never_plays_the_high_string_is_b_e_a_d(tmp_path: Path) -> None:
    path = _bass_gp5(tmp_path / "b.gp5", [23, 28, 33, 38, 43], [(0, 2), (1, 0), (3, 4)])
    parsed = parse_gp_track(path, 0, bass=True)
    assert [(n.string, n.fret) for n in parsed.notes] == [(0, 2), (1, 0), (3, 4)]
    assert parsed.tuning.midi[:4] == (23, 28, 33, 38)
    assert any("B E A D" in w for w in parsed.warnings)
    assert not any("dropped" in w or "fora" in w for w in parsed.warnings[1:])


def test_a_five_string_bass_that_never_plays_the_low_b_is_e_a_d_g(tmp_path: Path) -> None:
    path = _bass_gp5(tmp_path / "b.gp5", [23, 28, 33, 38, 43], [(1, 0), (4, 5)])
    parsed = parse_gp_track(path, 0, bass=True)
    assert [(n.string, n.fret) for n in parsed.notes] == [(0, 0), (3, 5)]
    assert parsed.tuning.offsets_from_standard()[:4] == (0, 0, 0, 0)


def test_notes_a_five_string_part_loses_are_counted(tmp_path: Path) -> None:
    # Both outer strings played: the fewer notes are lost (one on the high G).
    notes = [(0, 1), (0, 3), (1, 0), (2, 2), (4, 7)]
    path = _bass_gp5(tmp_path / "b.gp5", [23, 28, 33, 38, 43], notes)
    parsed = parse_gp_track(path, 0, bass=True)
    assert len(parsed.notes) == 4
    assert len(parsed.warnings) == 2 and "1" in parsed.warnings[1]


def test_a_bass_is_not_a_guitar_chart_nor_a_guitar_a_bass(tmp_path: Path) -> None:
    bass = _bass_gp5(tmp_path / "b.gp5", [28, 33, 38, 43], [(0, 3)])
    with pytest.raises(IngestionError, match="Bass"):
        parse_gp_track(bass, 0)
    guitar = _bass_gp5(tmp_path / "g.gp5", [40, 45, 50, 55, 59, 64], [(0, 3)])
    with pytest.raises(IngestionError, match="Bass"):
        parse_gp_track(guitar, 0, bass=True)
