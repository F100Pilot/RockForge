import pytest

from rockforge.domain.errors import FretMappingError
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


def test_unplayable_pitch_raises_explicit_error() -> None:
    with pytest.raises(FretMappingError):
        map_to_fretboard([ev(20, 0.0)], STANDARD)  # below low E


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
