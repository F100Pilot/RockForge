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
    clean_transcription,
    expand_slide_ins,
    expand_trills,
    is_composite_bend,
    suggest_tuning,
    tuning_name,
)


def test_suggest_tuning_standard_when_lowest_is_low_e() -> None:
    pitches = [40] * 10 + [47, 52, 55, 59]  # nothing below low E
    assert suggest_tuning(pitches) == ("E Standard", (40, 45, 50, 55, 59, 64))


def test_suggest_tuning_infers_drop_from_low_notes() -> None:
    # A cluster of C#2 (MIDI 37) → Drop C# (the common tuning whose low string fits).
    pitches = [37] * 12 + [44, 49, 54, 58]
    name, midi = suggest_tuning(pitches)
    assert name == "Drop C#"
    assert midi[0] == 37


def test_suggest_tuning_ignores_lone_sub_harmonic_ghost() -> None:
    # One stray ghost at MIDI 30 among a standard-tuning song must NOT drag the
    # guess down — it recurs only once, below the frequency threshold.
    pitches = [40] * 30 + [45, 50, 55, 59, 64] * 5 + [30]
    assert suggest_tuning(pitches)[0] == "E Standard"


def test_suggest_tuning_drop_d_wins_tie_over_d_standard() -> None:
    # Low string D2 (38) fits both Drop D and D Standard; the more common Drop D
    # wins the tie (list order).
    assert suggest_tuning([38] * 8 + [45, 50, 55])[0] == "Drop D"


def test_suggest_tuning_empty_is_standard() -> None:
    assert suggest_tuning([]) == ("E Standard", (40, 45, 50, 55, 59, 64))


def test_tuning_name_maps_known_and_custom() -> None:
    assert tuning_name((38, 45, 50, 55, 59, 64)) == "Drop D"
    assert tuning_name((41, 46, 51, 56, 60, 65)) == "custom"


def test_standard_tuning_offsets_are_zero() -> None:
    assert Tuning().offsets_from_standard() == (0, 0, 0, 0, 0, 0)


def test_clean_transcription_drops_out_of_range_notes() -> None:
    """Basic Pitch on a distorted mix emits sub-harmonic ghosts below low E and
    octave ghosts far above the neck; both are unplayable and pruned before
    mapping (standard tuning: playable MIDI 40..88)."""
    notes = [
        NoteEvent(pitch=39, start=1.0, duration=0.5),   # below low E — ghost
        NoteEvent(pitch=37, start=2.0, duration=0.5),   # below low E — ghost
        NoteEvent(pitch=92, start=3.0, duration=0.5),   # above the 24th fret — ghost
        NoteEvent(pitch=52, start=4.0, duration=0.5),   # playable — kept
        NoteEvent(pitch=40, start=5.0, duration=0.5),   # low E open — kept (boundary)
        NoteEvent(pitch=88, start=6.0, duration=0.5),   # high E 24th — kept (boundary)
    ]
    r = clean_transcription(notes, Tuning())
    assert r.dropped_out_of_range == 3
    assert sorted(n.pitch for n in r.notes) == [40, 52, 88]


def test_clean_transcription_drops_short_fragments() -> None:
    notes = [
        NoteEvent(pitch=52, start=0.0, duration=0.01),  # 10 ms — noise
        NoteEvent(pitch=52, start=1.0, duration=0.30),  # real
    ]
    r = clean_transcription(notes, Tuning())
    assert r.dropped_too_short == 1
    assert [n.duration for n in r.notes] == [0.30]


def test_clean_transcription_merges_same_pitch_fragments() -> None:
    """A held note split into adjacent same-pitch segments is rejoined into one."""
    notes = [
        NoteEvent(pitch=52, start=0.0, duration=0.20),
        NoteEvent(pitch=52, start=0.21, duration=0.20),  # 10 ms gap → same note
        NoteEvent(pitch=52, start=0.42, duration=0.20),  # another 10 ms gap
    ]
    r = clean_transcription(notes, Tuning())
    assert r.merged_fragments == 2
    assert len(r.notes) == 1
    assert r.notes[0].start == 0.0
    assert r.notes[0].start + r.notes[0].duration == pytest.approx(0.62)


def test_clean_transcription_keeps_distinct_and_distant_same_pitch() -> None:
    # Same pitch but a big gap → two separate notes (not merged).
    notes = [
        NoteEvent(pitch=52, start=0.0, duration=0.20),
        NoteEvent(pitch=52, start=2.0, duration=0.20),
    ]
    r = clean_transcription(notes, Tuning())
    assert r.merged_fragments == 0
    assert len(r.notes) == 2


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


def test_slide_in_adds_lead_in_note_when_there_is_room() -> None:
    notes = [
        TabNote(string=0, fret=5, time=0.0, sustain=0.2),   # ends 0.2, far before
        TabNote(string=0, fret=12, time=1.0, sustain=0.3, slide_in_from=9),
    ]
    out = expand_slide_ins(notes)
    assert len(out) == 3  # a lead-in note was inserted
    lead = next(n for n in out if n.fret == 9)
    assert lead.slide_to_fret == 12 and Technique.SLIDE in lead.techniques
    assert lead.time < 1.0 and lead.time + lead.sustain <= 1.0 + 1e-9
    assert next(n for n in out if n.fret == 12).slide_in_from is None  # marker cleared


def test_slide_in_makes_previous_note_slide_when_crowded() -> None:
    notes = [
        TabNote(string=0, fret=10, time=0.9, sustain=0.1),  # adjacent, near in pitch
        TabNote(string=0, fret=12, time=1.0, sustain=0.3, slide_in_from=9),
    ]
    out = expand_slide_ins(notes)
    assert len(out) == 2  # no extra note — the previous note carries the slide
    prev = next(n for n in out if n.fret == 10)
    assert prev.slide_to_fret == 12 and Technique.SLIDE in prev.techniques


def test_slide_in_left_plain_on_a_big_jump_with_no_room() -> None:
    notes = [
        TabNote(string=0, fret=2, time=0.9, sustain=0.1),   # adjacent but far in pitch
        TabNote(string=0, fret=17, time=1.0, sustain=0.3, slide_in_from=14),
    ]
    out = expand_slide_ins(notes)
    assert len(out) == 2
    assert next(n for n in out if n.fret == 2).slide_to_fret is None  # not forced


def test_trill_expands_to_alternating_hammer_pull_run() -> None:
    n = TabNote(string=0, fret=5, time=0.0, sustain=0.5, trill_fret=7)
    out = expand_trills([n], period=0.1)  # 0.5 / 0.1 = 5 steps
    assert [x.fret for x in out] == [5, 7, 5, 7, 5]
    assert all(x.trill_fret is None for x in out)
    # first step is the picked attack; later steps hammer on (up) / pull off (down)
    assert not ({Technique.HAMMER_ON, Technique.PULL_OFF} & out[0].techniques)
    assert Technique.HAMMER_ON in out[1].techniques   # 5 -> 7
    assert Technique.PULL_OFF in out[2].techniques    # 7 -> 5
    assert abs((out[-1].time + out[-1].sustain) - 0.5) < 1e-9  # spans the sustain


def test_note_without_trill_is_unchanged() -> None:
    n = TabNote(string=0, fret=5, time=0.0, sustain=0.5)
    assert expand_trills([n]) == [n]


def test_is_composite_bend_only_for_varying_strength() -> None:
    # A flat hold (even a pre-bend held at one value) is simple; only a real
    # release / multi-step curve is composite.
    assert not is_composite_bend([BendPoint(1.0, 1.0)])  # single point
    assert not is_composite_bend([BendPoint(0.0, 1.0), BendPoint(1.0, 1.0)])  # flat hold
    assert is_composite_bend([BendPoint(0.0, 0.0), BendPoint(1.0, 1.0)])  # a rise
    assert is_composite_bend(  # bend-and-release
        [BendPoint(0.0, 0.0), BendPoint(0.5, 1.0), BendPoint(1.0, 0.0)]
    )
