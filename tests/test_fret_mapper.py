import pytest

from rockforge.domain.music import NoteEvent, Technique, Tuning
from rockforge.infrastructure.fretboard.mapper import infer_legato, map_to_fretboard

STANDARD = Tuning()


def ev(pitch: int, start: float, dur: float = 0.2, bend: float = 0.0) -> NoteEvent:
    return NoteEvent(pitch=pitch, start=start, duration=dur, bend_semitones=bend)


def test_every_note_is_playable_and_pitch_preserved() -> None:
    notes = [ev(p, i * 0.5) for i, p in enumerate([40, 45, 52, 57, 64, 76, 88])]
    tab = map_to_fretboard(notes, STANDARD)
    assert len(tab) == len(notes)
    for n, t in zip(sorted(notes, key=lambda x: x.start), tab, strict=True):
        assert STANDARD.midi[t.string] + t.fret == n.pitch


def test_chord_gets_distinct_strings() -> None:
    # E major triad-ish cluster, simultaneous onsets
    chord = [ev(40, 1.0), ev(47, 1.0), ev(52, 1.001)]
    tab = map_to_fretboard(chord, STANDARD)
    assert len({t.string for t in tab}) == 3


def test_sequence_prefers_minimal_hand_movement() -> None:
    # A pentatonic-like run around frets 5-8 should not jump anchors wildly
    run = [ev(p, i * 0.25) for i, p in enumerate([45, 48, 50, 52, 55, 57])]
    tab = map_to_fretboard(run, STANDARD)
    fretted = [t.fret for t in tab if t.fret > 0]
    assert max(fretted) - min(fretted) <= 5


def test_unplayable_pitch_is_skipped_with_warning() -> None:
    w: list[str] = []
    tab = map_to_fretboard([ev(20, 0.0)], STANDARD, warnings=w)
    assert tab == []
    assert len(w) == 1
    assert "skipped unplayable note" in w[0]


def test_bend_technique_propagates() -> None:
    tab = map_to_fretboard([ev(67, 0.0, bend=1.0)], STANDARD)
    assert Technique.BEND in tab[0].techniques


def test_infer_legato_tags_hammer_on_and_pull_off() -> None:
    seq = [ev(45, 0.0, dur=0.1), ev(47, 0.105, dur=0.1), ev(45, 0.21, dur=0.1)]
    tab = infer_legato(map_to_fretboard(seq, STANDARD))
    techs = [t.techniques for t in tab]
    assert Technique.HAMMER_ON in techs[1]
    assert Technique.PULL_OFF in techs[2]


def test_empty_input() -> None:
    assert map_to_fretboard([], STANDARD) == []


def test_deterministic() -> None:
    notes = [ev(p, i * 0.3) for i, p in enumerate([50, 55, 59, 64, 59, 55, 50])]
    assert map_to_fretboard(notes, STANDARD) == map_to_fretboard(notes, STANDARD)


def test_unplayable_chord_drops_most_constrained_note() -> None:
    """A 4-note chord that can't fit should drop one note and produce 3."""
    # Same chord that failed in production: F2(41), C3(48), C4(60), A4(69)
    chord = [ev(41, 5.9), ev(48, 5.9), ev(60, 5.9), ev(69, 5.9)]
    w: list[str] = []
    tab = map_to_fretboard(chord, STANDARD, warnings=w)
    # Should produce 3 notes (dropped the most constrained one)
    assert len(tab) == 3
    assert len(w) == 1
    assert "dropped" in w[0]
    # All mapped notes should have valid pitch
    for t in tab:
        assert STANDARD.midi[t.string] + t.fret in {41, 48, 60, 69}


def test_unplayable_chord_skipped_if_drop_fails() -> None:
    """A 2-note group where both notes are unplayable should be skipped."""
    # Two notes below low E — no recovery possible
    chord = [ev(20, 0.0), ev(21, 0.0)]
    w: list[str] = []
    tab = map_to_fretboard(chord, STANDARD, warnings=w)
    assert tab == []
    assert len(w) == 1
    assert "skipped" in w[0]
