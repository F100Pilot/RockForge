"""Chord-naming heuristic (domain/chords.py) — derived from sounding pitches."""

from rockforge.domain.chords import (
    chord_display,
    chord_fingering,
    group_fingering,
    hand_shape_spans,
    name_chord,
)
from rockforge.domain.music import TabNote

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


# --- Fingers and hand shapes: what Rocksmith draws the chord's fingers from ---

X = -1


def test_chord_fingering_follows_the_hand_made_charts() -> None:
    """Shapes taken from the two community CDLC (Daughtry) the user sent, each
    with the fingers their authors gave it — a barre where one is needed, an
    open-chord part as in that chord, a root-less power chord 2-3."""
    cases = {
        (X, 2, 4, 4, 3, 2): (X, 1, 3, 4, 2, 1),   # Bm barre
        (1, 3, 3, 2, 1, 1): (1, 3, 4, 2, 1, 1),   # F barre
        (3, 5, 5, 3, 3, 3): (1, 3, 4, 1, 1, 1),   # G minor barre
        (3, 5, 5, 4, 0, X): (1, 3, 4, 2, X, X),   # no barre over an open string
        (X, 3, 5, 5, X, X): (X, 1, 3, 4, X, X),   # power chord with octave
        (4, 4, 4, X, X, X): (1, 2, 3, X, X, X),
        (X, X, 0, 2, 3, 2): (X, X, X, 1, 3, 2),   # D
        (X, 3, 2, 0, 1, 0): (X, 3, 2, X, 1, X),   # C
        (0, 2, 2, X, X, X): (X, 2, 3, X, X, X),   # part of an E
        (X, 0, 2, 2, 0, X): (X, X, 2, 3, X, X),   # part of an Am
        (X, 3, 2, X, X, X): (X, 3, 2, X, X, X),   # part of a C
        (X, 7, 7, X, X, X): (X, 2, 3, X, X, X),   # power chord without its root
        (X, X, X, X, 8, 5): (X, X, X, X, 4, 1),
    }
    for frets, fingers in cases.items():
        assert chord_fingering(frets) == fingers, frets


def test_a_shape_beyond_four_fingers_or_with_none_fretted_is_left_unfingered() -> None:
    assert chord_fingering((X, 6, 8, 8, 8, 6)) == (X,) * 6  # wants a fifth finger
    assert chord_fingering((0, X, X, 0, X, X)) == (X,) * 6


def test_the_guitar_pro_fingering_wins_when_it_fingers_every_note() -> None:
    frets = (X, 3, 5, 5, X, X)
    assert group_fingering(frets, (X, 1, 2, 3, X, X)) == (X, 1, 2, 3, X, X)
    # One fretted note without a finger: the file does not say, so ours.
    assert group_fingering(frets, (X, 1, X, 3, X, X)) == (X, 1, 3, 4, X, X)


def test_chord_display_names_the_chord_and_reads_the_files_fingers() -> None:
    notes = [TabNote(string=0, fret=3, time=0.0, sustain=0.0, left_hand=1),
             TabNote(string=1, fret=5, time=0.0, sustain=0.0, left_hand=3)]
    fingers, name = chord_display((3, 5, X, X, X, X), notes, (40, 45, 50, 55, 59, 64))
    assert fingers == (1, 3, X, X, X, X) and name == "G5"


def test_hand_shapes_cover_each_run_of_one_chord() -> None:
    # A A A (single) A | B B, then A after a long rest.
    groups = [
        (0.0, 0.0, 0), (0.5, 0.0, 0), (1.0, 0.2, 0),
        (1.5, 0.0, -1),
        (2.0, 0.0, 0),
        (2.5, 0.0, 1), (3.0, 0.4, 1),
        (6.0, 0.0, 0),
    ]
    spans = hand_shape_spans(groups)
    assert [(c, a, b) for c, a, b, _ in spans] == [(0, 0, 2), (0, 4, 4), (1, 5, 6), (0, 7, 7)]
    ends = [round(e, 3) for *_, e in spans]
    assert ends[0] == 1.201  # 1 ms past the sustain: the references' shape
    assert ends[2] == 3.401
    # Never past the next note: a sustain into the next note stops at it.
    clipped = hand_shape_spans([(0.0, 2.0, 0), (1.0, 0.0, -1)])
    assert clipped[0][3] == 1.0


def test_a_rest_longer_than_a_second_starts_a_new_hand_shape() -> None:
    spans = hand_shape_spans([(0.0, 0.0, 3), (0.9, 0.0, 3), (2.5, 0.0, 3)])
    assert [(a, b) for _, a, b, _ in spans] == [(0, 1), (2, 2)]


def test_a_dead_string_is_left_out_of_the_chords_name() -> None:
    """GitHub issue #30: an octave 6 X 8 whose X carries fret 8 (where the hand
    mutes it) was named A#5 — after the F of a string nobody plays. A dead
    string sounds no pitch: the octave alone is no chord the namer knows, so it
    gets no name rather than a wrong one."""
    from rockforge.domain.music import TabNote, Technique

    dead = frozenset({Technique.FRET_MUTE})
    notes = [
        TabNote(string=0, fret=6, time=0.0, sustain=0.0),
        TabNote(string=1, fret=8, time=0.0, sustain=0.0, techniques=dead),
        TabNote(string=2, fret=8, time=0.0, sustain=0.0),
    ]
    frets = (6, 8, 8, X, X, X)
    fingers, name = chord_display(frets, notes, (40, 45, 50, 55, 59, 64))
    assert name == ""
    assert fingers[1] != -1  # a finger still sits on the muted string
    # The same frets with the A string played are the power chord.
    played = [TabNote(string=n.string, fret=n.fret, time=0.0, sustain=0.0) for n in notes]
    assert chord_display(frets, played, (40, 45, 50, 55, 59, 64))[1] == "A#5"


def test_a_muted_string_in_a_chord_sits_on_the_chords_lowest_fret() -> None:
    """GitHub issue #30: the tab's octave 10 X 12 carried fret 5 on the muted A
    string, and the game draws an X at the fret the note carries, so it showed
    up outside the chord. It goes where the index finger mutes it; a slide
    moves with it; a lone X, or one in a chord of open strings, keeps its fret."""
    from rockforge.domain.chords import place_dead_strings_in_chords
    from rockforge.domain.music import Technique

    dead = frozenset({Technique.FRET_MUTE})
    octave = [
        TabNote(string=0, fret=10, time=0.0, sustain=0.0),
        TabNote(string=1, fret=5, time=0.0, sustain=0.0, techniques=dead),
        TabNote(string=2, fret=12, time=0.0, sustain=0.0),
    ]
    sliding = [
        TabNote(string=0, fret=10, time=1.0, sustain=0.5, slide_to_fret=12),
        TabNote(string=1, fret=5, time=1.0, sustain=0.5, slide_to_fret=7,
                techniques=dead | {Technique.SLIDE}),
    ]
    alone = [TabNote(string=1, fret=5, time=2.0, sustain=0.0, techniques=dead)]
    open_chord = [
        TabNote(string=0, fret=0, time=3.0, sustain=0.0),
        TabNote(string=1, fret=5, time=3.0, sustain=0.0, techniques=dead),
    ]
    off_neck = [
        TabNote(string=0, fret=20, time=4.0, sustain=0.0),
        TabNote(string=1, fret=2, time=4.0, sustain=0.3, slide_to_fret=22,
                techniques=dead),
    ]
    out = place_dead_strings_in_chords(octave + sliding + alone + open_chord + off_neck)
    assert [n.fret for n in out[:3]] == [10, 10, 12]
    assert out[1].techniques == dead
    assert (out[4].fret, out[4].slide_to_fret) == (10, 12)
    assert out[5].fret == 5          # alone
    assert out[7].fret == 5          # only an open string beside it
    assert (out[9].fret, out[9].slide_to_fret) == (2, 22)  # 20 + 20 is off the neck
