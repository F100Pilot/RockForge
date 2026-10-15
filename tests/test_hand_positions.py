"""The FHP editor: fret-hand positions placed by the user (a Reddit report:
"There's no way to add or edit FHPs. Automatic ones are total shit.").

A chart with FHPs of the user's ships exactly those — in the XML for DLC
Builder and in every difficulty level of the native SNG, where each level only
keeps the FHPs that still frame a note of its own and every note points at its
level's anchor (the rules ``check_sng`` holds).
"""

from __future__ import annotations

import pytest

from rockforge.domain.arrangement import Arrangement, ArrangementKind, Section, SongMetadata
from rockforge.domain.hand import (
    HandPosition,
    auto_windows,
    fixed_windows,
    notes_outside,
    position_pin,
)
from rockforge.domain.music import Beat, TabNote, Technique, TempoMap, Tuning
from rockforge.infrastructure.packaging.psarc.sng import from_arrangement
from rockforge.infrastructure.packaging.psarc.verify import check_sng
from rockforge.infrastructure.rsxml.writer import render_arrangement


def _chart(notes: list[TabNote], hps: list[HandPosition] | None = None) -> Arrangement:
    beats = tuple(Beat(time=round(1.0 + 0.5 * i, 3), measure=(i // 4 + 1) if i % 4 == 0 else -1)
                  for i in range(90))
    return Arrangement(
        kind=ArrangementKind.LEAD, metadata=SongMetadata(title="A", artist="B", song_length=46.0),
        tuning=Tuning(), notes=sorted(notes, key=lambda n: (n.time, n.string)),
        sections=[Section("verse", 1.0, 1), Section("chorus", 21.0, 1)],
        tempo_map=TempoMap(beats=beats, average_bpm=120.0),
        hand_positions=sorted(hps or []),
    )


def _climb() -> list[TabNote]:
    """Forty notes walking up and down the neck, through two sections."""
    frets = [3, 5, 7, 5, 8, 10, 12, 10, 7, 5] * 4
    return [TabNote(string=k % 3, fret=f, time=2.0 + 0.95 * k, sustain=0.2)
            for k, f in enumerate(frets)]


MINE = [HandPosition(1.5, 3, 5), HandPosition(5.8, 7, 6), HandPosition(12.0, 2, 4),
        HandPosition(30.0, 9, 4)]


def test_a_hand_position_must_sit_on_the_neck() -> None:
    assert HandPosition(1.0, 21, 4).covers(24) and HandPosition(1.0, 5, 4).covers(0)
    assert not HandPosition(1.0, 5, 4).covers(9)
    for bad in ((1.0, 0, 4), (1.0, 22, 4), (1.0, 5, 1), (1.0, 5, 13), (-1.0, 5, 4),
                (float("nan"), 5, 4)):
        with pytest.raises(ValueError):
            HandPosition(*bad)  # type: ignore[arg-type]


def test_each_note_belongs_to_the_hand_position_before_it() -> None:
    hps = [HandPosition(10.0, 5), HandPosition(20.0, 9)]
    positions = [(3.0, 3.0, [2]), (9.997, 9.997, [5]), (12.0, 12.0, [0]), (15.0, 15.0, [8])]
    # Before the first: the first. A note 3 ms before an FHP read back from the
    # XML (millisecond times) is AT it. An FHP with no note here is dropped.
    assert fixed_windows(hps, positions) == [(3.0, 15.0, 5, 4)]
    assert fixed_windows(hps, [(21.0, 21.0, [9])]) == [(20.0, 21.0, 9, 4)]
    assert notes_outside(hps, [(9.997, 2), (12.0, 0), (15.0, 9), (25.0, 12)]) == [9.997, 15.0]


def test_the_users_hand_positions_are_the_xml_anchors() -> None:
    root = render_arrangement(_chart(_climb(), MINE))
    anchors = [(float(a.get("time", "0")), int(a.get("fret", "0")), float(a.get("width", "0")))
               for a in root.iter("anchor")]
    assert anchors == [(h.time, h.fret, float(h.width)) for h in MINE]
    # Without them the XML carries the native SNG's automatic windows.
    auto = render_arrangement(_chart(_climb()))
    groups = [(n.time, n.time, [n.fret]) for n in _climb()]
    assert [(float(a.get("time", "0")), int(a.get("fret", "0"))) for a in auto.iter("anchor")] == [
        (round(t, 3), fret) for t, _, fret, _ in auto_windows(groups)
    ]


@pytest.mark.parametrize("dd", [True, False])
def test_every_level_of_the_sng_uses_only_the_users_hand_positions(dd: bool) -> None:
    model = from_arrangement(_chart(_climb(), MINE), dynamic_difficulty=dd)
    assert check_sng(model) == []
    assert len(model.arrangements) > (1 if dd else 0)
    mine = [(h.fret, h.width) for h in MINE]
    for level in model.arrangements:
        kept = []
        for a in level.anchors:  # pieces of one FHP split at a phrase start
            if not kept or kept[-1] != (a.fret, a.width):
                kept.append((a.fret, a.width))
        it = iter(mine)
        assert all(any(k == m for m in it) for k in kept), (level.difficulty, kept)
        for n in level.notes:
            owner = max((h for h in MINE if h.time <= n.time + 0.005), default=MINE[0])
            assert (n.anchor_fret, n.anchor_width) == (owner.fret, owner.width)
    full = model.arrangements[-1]
    assert {(a.fret, a.width) for a in full.anchors} == set(mine)
    # And they really are not the automatic ones.
    auto = from_arrangement(_chart(_climb()), dynamic_difficulty=dd).arrangements[-1]
    assert {(a.fret, a.width) for a in auto.anchors} != set(mine)


def test_a_level_without_the_notes_of_a_hand_position_does_not_carry_it() -> None:
    notes = [TabNote(string=0, fret=3, time=2.0 + k, sustain=0.2) for k in range(18)]
    notes.append(TabNote(string=5, fret=15, time=30.0, sustain=0.2))
    hps = [HandPosition(1.0, 3, 4), HandPosition(29.5, 14, 4)]
    model = from_arrangement(_chart(notes, hps))
    assert check_sng(model) == []
    with_it = [lv for lv in model.arrangements if any(n.time == 30.0 for n in lv.notes)]
    without = [lv for lv in model.arrangements if not any(n.time == 30.0 for n in lv.notes)]
    assert with_it and all(any(a.fret == 14 for a in lv.anchors) for lv in with_it)
    assert all(not any(a.fret == 14 for a in lv.anchors) for lv in without)


def test_a_hand_position_inside_an_arpeggio_is_the_users_call() -> None:
    arp = [TabNote(string=s, fret=f, time=20.0 + 0.25 * i, sustain=0.2,
                   techniques=frozenset({Technique.LET_RING}))
           for i, (s, f) in enumerate([(1, 3), (2, 2), (3, 0), (4, 1)])]
    notes = [TabNote(string=5, fret=5, time=18.0, sustain=0.2), *arp]
    hps = [HandPosition(17.0, 5, 4), HandPosition(20.0, 1, 4), HandPosition(20.5, 2, 4)]
    model = from_arrangement(_chart(notes, hps))
    assert check_sng(model) == []
    assert [(a.fret) for a in model.arrangements[-1].anchors if a.start_time >= 20.0][:2] == [1, 2]


# --- The automatic placement, measured against hand-made charts -------------

def _auto(groups: list[tuple[list[int], list[int]]]) -> list[tuple[int, int]]:
    """(time index, FHP fret) of the automatic windows over chords/notes given
    as (frets per string, fingers per string); a single note is one string."""
    positions = [
        (float(i), float(i), [f for f in frets if f > 0], position_pin(frets, fingers))
        for i, (frets, fingers) in enumerate(groups)
    ]
    return [(int(t), fret) for t, _, fret, _ in auto_windows(positions)]


def _note(fret: int) -> tuple[list[int], list[int]]:
    return [fret], [-1]


def test_a_chord_puts_the_hand_on_its_index_finger() -> None:
    # A note on fret 4 then a power chord 5-7-7 fingered 1-3-4: the hand moves
    # to 5, where the index is — not left at 4, whose window still reaches 7.
    power = ([-1, 5, 7, 7, -1, -1], [-1, 1, 3, 4, -1, -1])
    assert _auto([_note(4), power, _note(6)]) == [(0, 4), (1, 5)]
    assert _auto([_note(4), ([-1, 5, 7, 7, -1, -1], [-1] * 6)]) == [(0, 4)]  # fingering unknown


def test_a_shape_without_the_index_leaves_the_hand_where_it_is() -> None:
    pair = ([-1, 6, 6, -1, -1, -1], [-1, 2, 3, -1, -1, -1])  # fingers 2 and 3
    open_and_one = ([-1, -1, 0, 7, -1, -1], [-1, -1, -1, 1, -1, -1])
    assert position_pin(*pair) == -1 and position_pin(*open_and_one) == -1
    assert _auto([_note(4), pair, open_and_one, _note(5)]) == [(0, 4)]


def test_the_hand_moves_at_the_first_note_it_cannot_reach() -> None:
    # 2..5 is one position; the 7 cannot be reached from it, so the move is
    # at the 7 — not earlier, at the first 5, where the new position would fit
    # — and the index goes on the lowest note of the new run.
    assert _auto([_note(2), _note(3), _note(5), _note(5), _note(7), _note(5)]) == [(0, 2), (4, 5)]


def test_the_xml_and_the_sng_place_the_same_automatic_hand_positions() -> None:
    power = [TabNote(string=s, fret=f, time=0.0, sustain=0.2) for s, f in ((1, 5), (2, 7), (3, 7))]
    notes = []
    for k in range(10):
        t0 = 2.0 + 2.0 * k
        notes += [TabNote(string=0, fret=4, time=t0, sustain=0.2)]
        notes += [TabNote(string=n.string, fret=n.fret, time=t0 + 0.5, sustain=0.2) for n in power]
        notes += [TabNote(string=2, fret=6, time=t0 + 1.0, sustain=0.2, left_hand=2)]
    chart = _chart(notes)
    xml = [(int(a.get("fret", "0")), int(float(a.get("width", "0"))))
           for a in render_arrangement(chart).iter("anchor")]
    top = from_arrangement(chart, dynamic_difficulty=False).arrangements[0]
    sng = []
    for a in top.anchors:
        if not sng or sng[-1] != (a.fret, a.width):
            sng.append((a.fret, a.width))
    assert xml == sng == [(4, 4), (5, 4)] * 10
