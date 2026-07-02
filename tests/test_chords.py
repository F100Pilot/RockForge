"""Chord-naming heuristic (domain/chords.py) — derived from sounding pitches."""

from rockforge.domain.chords import name_chord

# MIDI reference: C4=60, E4=64, G4=67, A3=57, C3=48, etc.


def test_major_triad() -> None:
    assert name_chord([60, 64, 67]) == "C"  # C E G


def test_minor_triad() -> None:
    assert name_chord([57, 60, 64]) == "Am"  # A C E


def test_power_chord() -> None:
    assert name_chord([40, 47]) == "E5"  # E B (root + fifth)


def test_dominant_seventh() -> None:
    assert name_chord([55, 59, 62, 65]) == "G7"  # G B D F


def test_major_seventh() -> None:
    assert name_chord([60, 64, 67, 71]) == "Cmaj7"  # C E G B


def test_sus4() -> None:
    assert name_chord([62, 67, 69]) == "Dsus4"  # D G A


def test_inversion_uses_slash_over_bass() -> None:
    # C major with E in the bass → C/E
    assert name_chord([52, 60, 67]) == "C/E"  # E C G


def test_octave_doubling_is_ignored() -> None:
    # C E G with the root doubled an octave up is still a plain C
    assert name_chord([60, 64, 67, 72]) == "C"


def test_single_pitch_class_is_not_a_chord() -> None:
    assert name_chord([60]) is None
    assert name_chord([60, 72]) is None  # two Cs, one pitch class


def test_unknown_voicing_returns_none() -> None:
    # A cluster that matches no template must not be given an invented name.
    assert name_chord([60, 61, 62]) is None
