import pytest

from rockforge.domain.music import Beat, NoteEvent, TabNote, TempoMap, Tuning


def test_standard_tuning_offsets_are_zero() -> None:
    assert Tuning().offsets_from_standard() == (0, 0, 0, 0, 0, 0)


def test_drop_d_offsets() -> None:
    drop_d = Tuning(midi=(38, 45, 50, 55, 59, 64))
    assert drop_d.offsets_from_standard() == (-2, 0, 0, 0, 0, 0)


def test_candidate_positions_open_e() -> None:
    # E2 (40) is playable only as open string 0 in standard tuning
    assert Tuning().candidate_positions(40) == [(0, 0)]


def test_candidate_positions_middle_pitch_has_multiple_strings() -> None:
    positions = Tuning().candidate_positions(64)  # E4
    assert (5, 0) in positions and (4, 5) in positions and (3, 9) in positions


def test_note_event_rejects_bad_pitch() -> None:
    with pytest.raises(ValueError):
        NoteEvent(pitch=200, start=0.0, duration=1.0)


def test_tab_note_rejects_bad_fret() -> None:
    with pytest.raises(ValueError):
        TabNote(string=0, fret=30, time=0.0, sustain=0.1)


def test_tempo_map_requires_sorted_beats() -> None:
    with pytest.raises(ValueError):
        TempoMap(beats=(Beat(1.0, 1), Beat(0.5, -1)), average_bpm=120)
