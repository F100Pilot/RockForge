import pytest

from rockforge.domain.music import (
    Beat,
    BendPoint,
    NoteEvent,
    TabNote,
    Technique,
    TempoMap,
    Tuning,
    apply_sustain_gap,
    is_composite_bend,
)


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


def test_sustain_gap_trims_before_next_note_on_same_string() -> None:
    # A sustain that runs into the next attack on the same string is trimmed to
    # leave a small gap; the last note (no successor) keeps its full length.
    notes = [
        TabNote(string=0, fret=5, time=0.0, sustain=1.0),  # runs into the next
        TabNote(string=0, fret=7, time=1.0, sustain=1.0),  # last on string 0
    ]
    out = apply_sustain_gap(notes)
    assert out[0].sustain < 1.0 and out[0].time + out[0].sustain < 1.0
    assert out[1].sustain == 1.0


def test_sustain_gap_ignores_other_strings_and_slides() -> None:
    notes = [
        TabNote(string=0, fret=5, time=0.0, sustain=1.0),  # next note is string 1
        TabNote(string=1, fret=7, time=0.5, sustain=0.2),
        TabNote(string=2, fret=3, time=0.0, sustain=1.0,   # slides to its landing
                techniques=frozenset({Technique.SLIDE}), slide_to_fret=5),
        TabNote(string=2, fret=5, time=1.0, sustain=0.2),
    ]
    out = apply_sustain_gap(notes)
    assert out[0].sustain == 1.0  # different string ahead — untouched
    assert out[2].sustain == 1.0  # slide keeps its reach to the landing note


def test_sustain_gap_keeps_short_staccato_notes() -> None:
    notes = [
        TabNote(string=0, fret=5, time=0.0, sustain=0.1),  # already short
        TabNote(string=0, fret=7, time=1.0, sustain=0.1),
    ]
    out = apply_sustain_gap(notes)
    assert out[0].sustain == 0.1  # nowhere near the next note — unchanged


def test_sustain_gap_preserves_slide_unpitch_and_bend_points() -> None:
    pts = (BendPoint(0.0, 0.0), BendPoint(0.5, 1.0), BendPoint(1.0, 0.0))
    notes = [
        TabNote(string=0, fret=9, time=0.0, sustain=1.0,
                slide_unpitch_to=4, bend_points=pts),
        TabNote(string=0, fret=7, time=1.0, sustain=0.5),
    ]
    out = apply_sustain_gap(notes)
    assert out[0].sustain < 1.0  # trimmed
    assert out[0].slide_unpitch_to == 4 and out[0].bend_points == pts  # kept


def test_sustain_gap_skips_let_ring_notes() -> None:
    notes = [
        TabNote(string=0, fret=5, time=0.0, sustain=1.0,
                techniques=frozenset({Technique.LET_RING})),
        TabNote(string=0, fret=7, time=1.0, sustain=0.5),
    ]
    out = apply_sustain_gap(notes)
    assert out[0].sustain == 1.0  # let-ring keeps its full sustain into the next note


def test_is_composite_bend_only_for_varying_strength() -> None:
    # A flat hold (even a pre-bend held at one value) is simple; only a real
    # release / multi-step curve is composite.
    assert not is_composite_bend([BendPoint(1.0, 1.0)])  # single point
    assert not is_composite_bend([BendPoint(0.0, 1.0), BendPoint(1.0, 1.0)])  # flat hold
    assert is_composite_bend([BendPoint(0.0, 0.0), BendPoint(1.0, 1.0)])  # a rise
    assert is_composite_bend(  # bend-and-release
        [BendPoint(0.0, 0.0), BendPoint(0.5, 1.0), BendPoint(1.0, 0.0)]
    )
