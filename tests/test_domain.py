import pytest

from rockforge.domain.music import (
    Beat,
    BendPoint,
    TabNote,
    Technique,
    TempoMap,
    Tuning,
    alphatab_bend,
    apply_sustain_gap,
    expand_slide_ins,
    expand_trills,
    is_composite_bend,
    is_plain_rise,
)


def test_standard_tuning_offsets_are_zero() -> None:
    assert Tuning().offsets_from_standard() == (0, 0, 0, 0, 0, 0)


def test_drop_d_offsets() -> None:
    drop_d = Tuning(midi=(38, 45, 50, 55, 59, 64))
    assert drop_d.offsets_from_standard() == (-2, 0, 0, 0, 0, 0)


def test_tuning_rejects_an_impossible_pitch_at_construction() -> None:
    """Tuning was the one pitch-carrying domain type with no invariant, while
    TabNote/Beat/TempoMap all check theirs. An out-of-range value
    therefore travelled all the way to the SNG writer, where the semitone offset
    is packed as an int16, and died there as a cryptic struct.error with nothing
    pointing back at the tuning that caused it."""
    with pytest.raises(ValueError, match="out of range"):
        Tuning(midi=(999999, 1, 2, 3, 4, 5))
    with pytest.raises(ValueError, match="out of range"):
        Tuning(midi=(-1, 45, 50, 55, 59, 64))
    with pytest.raises(ValueError, match="6 strings"):
        Tuning(midi=(40, 45, 50, 55, 59))  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="finite"):
        Tuning(cent_offset=float("nan"))
    # Real low tunings must still construct — the guard is against nonsense, not
    # against the drop/down tunings the app exists to handle.
    drop = Tuning(midi=(37, 44, 49, 54, 58, 63))  # low string -3, the rest -1
    assert drop.offsets_from_standard() == (-3, -1, -1, -1, -1, -1)
    assert Tuning(midi=(34, 41, 46, 51, 55, 60)).midi[0] == 34  # Drop B territory


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
    assert out[0].slide_unpitch_to == 4
    # The curve is kept, at the same moments: a trimmed note must not bend earlier.
    kept = [(round(p.position * out[0].sustain, 6), p.step) for p in out[0].bend_points]
    assert kept == [(0.0, 0.0), (0.5, 1.0), (round(out[0].sustain, 6), 0.0)]


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


def test_is_composite_bend_for_varying_strength_or_a_pre_bend() -> None:
    # A single point is simple; a release / multi-step curve is composite, and so
    # is a flat pre-bend (bent from the attack, as alphaTab plays it).
    assert not is_composite_bend([BendPoint(1.0, 1.0)])  # single point
    assert not is_composite_bend([BendPoint(0.5, 1.0), BendPoint(1.0, 1.0)])  # bent later
    assert is_composite_bend([BendPoint(0.0, 1.0), BendPoint(1.0, 1.0)])  # flat pre-bend
    assert is_composite_bend([BendPoint(0.0, 0.0), BendPoint(1.0, 1.0)])  # a rise
    assert is_composite_bend(  # bend-and-release
        [BendPoint(0.0, 0.0), BendPoint(0.5, 1.0), BendPoint(1.0, 0.0)]
    )


def _curve(*pts: tuple[float, float]) -> tuple[BendPoint, ...]:
    return tuple(BendPoint(pos, step) for pos, step in pts)


@pytest.mark.parametrize(
    ("points", "played"),
    [
        # Up by the middle, then held: a rise across the whole note.
        (((0, 0), (0.5, 1), (1, 1)), ((0, 0), (1, 1))),
        # Pre-bend, held, released: a release across the whole note.
        (((0, 1), (0.5, 1), (1, 0)), ((0, 1), (1, 0))),
        # A middle below the destination, or a hold: dropped too.
        (((0, 0), (0.5, 0.5), (1, 1)), ((0, 0), (1, 1))),
        (((0, 1), (0.5, 1), (1, 1)), ((0, 1), (1, 1))),
        (((0, 0.5), (0.5, 1), (1, 0)), ((0, 0.5), (1, 0))),  # not higher than both ends
        # A peak in the middle is a bend-and-release: kept.
        (((0, 0), (0.5, 1), (1, 0)), ((0, 0), (0.5, 1), (1, 0))),
        (((0, 0), (0.5, 2), (1, 1)), ((0, 0), (0.5, 2), (1, 1))),
        # Other point counts are not touched.
        (((0, 0), (0.25, 1), (0.5, 1), (1, 1)), ((0, 0), (0.25, 1), (0.5, 1), (1, 1))),
        (((0, 0), (1, 1)), ((0, 0), (1, 1))),
    ],
)
def test_alphatab_bend_reads_three_points_as_alphatab(points, played) -> None:  # noqa: ANN001
    assert alphatab_bend(_curve(*points)) == _curve(*played)


def test_is_plain_rise() -> None:
    assert is_plain_rise(_curve((0, 0), (1, 1)))
    assert not is_plain_rise(_curve((0, 0), (0.75, 1)))  # peak before the end
    assert not is_plain_rise(_curve((0, 0.5), (1, 1)))  # pre-bent at the attack
    assert not is_plain_rise(_curve((0, 1), (1, 0)))  # a release
    assert not is_plain_rise(_curve((0, 0), (0.5, 1), (1, 1)))


def test_number_sections_counts_per_name_not_by_position() -> None:
    """Rocksmith shows a section as "<name> <number>", so the number is an
    ordinal WITHIN that name. Both callers used to pass the section's INDEX,
    which with COUNT/END and several names mixed in produced duplicates and
    gaps — a real build shipped two consecutive sections both numbered 2."""
    from rockforge.domain.arrangement import Section, number_sections

    src = [
        Section(name="COUNT", start_time=0.0),
        Section(name="riff", start_time=1.0),
        Section(name="riff", start_time=2.0),
        Section(name="noguitar", start_time=3.0),
        Section(name="riff", start_time=4.0),
    ]
    numbered, counts = number_sections(src)
    assert [(s.name, s.number) for s in numbered] == [
        ("COUNT", 1), ("riff", 1), ("riff", 2), ("noguitar", 1), ("riff", 3),
    ]
    assert counts["riff"] == 3

    # The tally carries forward, so a caller can continue the numbering across
    # arrangements — which is what a DLC Builder build does.
    more, counts = number_sections(
        [Section(name="riff", start_time=9.0), Section(name="noguitar", start_time=10.0)],
        counts,
    )
    assert [(s.name, s.number) for s in more] == [("riff", 4), ("noguitar", 2)]

    # Names are matched case-insensitively: one counter per section, not per
    # spelling.
    mixed, _ = number_sections(
        [Section(name="Verse", start_time=0.0), Section(name="verse", start_time=1.0)]
    )
    assert [s.number for s in mixed] == [1, 2]
    assert number_sections([]) == ([], {})
