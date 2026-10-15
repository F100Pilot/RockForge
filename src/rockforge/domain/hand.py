"""Fret-hand positions (FHPs, Rocksmith's "anchors"): where the hand sits.

An FHP is active from its time until the next one; the game highlights
``width`` frets from ``fret`` and the camera follows it. RockForge places them
automatically (``auto_windows``, measured against hand-made charts), and the
user can place their own in the tab viewer (``Arrangement.hand_positions``),
which then decide every one of the chart's FHPs — the automatic ones only ever
fill a chart the user left alone.
"""

from __future__ import annotations

import bisect
import math
from collections.abc import Sequence
from dataclasses import dataclass

MAX_FRET = 24
MIN_WIDTH = 2
MAX_WIDTH = 12
# An FHP read back from the built XML is rounded to the millisecond while a
# note keeps the parser's float; an FHP placed on a note must still be AT it.
HAND_POSITION_MATCH_S = 0.005

# (first_time, last_time, frets) — one per note or chord, time-sorted; an open
# string has no frets.
Position = tuple[float, float, Sequence[int]]
# ... plus the index finger's fret when it is known (``position_pin``), -1 if not.
PinnedPosition = tuple[float, float, Sequence[int], int]
# (start, last_note, fret, width)
Window = tuple[float, float, int, int]


@dataclass(frozen=True, order=True)
class HandPosition:
    time: float
    fret: int
    width: int = 4

    def __post_init__(self) -> None:
        if not math.isfinite(self.time) or self.time < 0:
            raise ValueError(f"hand position time must be a finite time >= 0, got {self.time}")
        if not MIN_WIDTH <= self.width <= MAX_WIDTH:
            raise ValueError(
                f"hand position width must be {MIN_WIDTH}-{MAX_WIDTH} frets, got {self.width}"
            )
        if not 1 <= self.fret <= MAX_FRET - self.width + 1:
            raise ValueError(
                f"hand position fret {self.fret} with width {self.width} leaves the neck "
                f"(1-{MAX_FRET})"
            )

    def covers(self, fret: int) -> bool:
        return fret <= 0 or self.fret <= fret < self.fret + self.width


def position_pin(frets: Sequence[int], fingers: Sequence[int]) -> int:
    """The fret the index finger frets, for a note or chord whose fingering
    says so (one fret and one finger per string; 1 = index), else -1 (the
    hand is free: a pair fretted with fingers 2 and 3, an open string with
    one fretted note). The hand-made charts put a chord's FHP exactly there,
    and leave the others to the notes around them."""
    played = [f for f in frets if f >= 0]
    if len(played) > 1 and sum(f > 0 for f in played) < 2:
        return -1  # open strings and one fretted note: any finger frets it
    index = [f for f, k in zip(frets, fingers, strict=False) if f > 0 and k == 1]
    return min(index) if index else -1


def auto_windows(positions: Sequence[Position | PinnedPosition]) -> list[Window]:
    """The automatic FHPs, placed the way the hand-made charts place them.

    Measured on the two community CDLC the user sent (seven charts, 3292
    fretted notes, two Lead, three Rhythm, two Bass): every FHP is 4 frets
    wide and frames every note under it; a chord whose fingering puts the
    index finger on a fret has its FHP exactly there; any other note leaves
    the hand where it is while a finger can still reach it, and the hand moves
    at the first note it cannot. So each note allows a range of index frets
    (a ``pin`` exactly; a single note, a pair fretted with fingers 2-3 or an
    open string with one fretted note, the four frets from which a finger
    reaches it), a run of notes stays in one position while those ranges
    overlap — the fewest moves, each as late as possible — and the index
    sits on the run's lowest note it can. Against those charts: the same
    FHP fret on 98.0% of the notes (80.1% with the old greedy windows, which
    also merged chords into windows below their index finger) and 344 moves
    where the authors made 343. Open strings place nothing; a shape wider
    than four frets keeps its own width.
    """
    groups: list[tuple[float, float, int, int, int]] = []  # (t, last, lo, hi, pin)
    for pos in positions:
        used = [f for f in pos[2] if f > 0]
        if used:
            pin = pos[3] if len(pos) > 3 else -1
            groups.append((pos[0], pos[1], min(used), max(used), pin))
    if not groups:
        return []
    top = MAX_FRET - 3

    def allowed(lo: int, hi: int, pin: int) -> tuple[int, int]:
        if pin >= 1:
            p = min(pin, lo, top)
            return p, p
        if hi - lo + 1 > 4:
            return lo, lo
        return max(1, hi - 3), min(lo, top)

    # Fewest moves, each as late as possible: a run goes on while the ranges
    # of index frets that cover its notes still overlap (greedy is optimal for
    # this interval-intersection partition, and it moves at the first note
    # the old position cannot reach — where the hand-made charts move).
    runs: list[tuple[int, int, int, int]] = []  # (first, last, lo_p, hi_p)
    for i, (_t, _l, lo, hi, pin) in enumerate(groups):
        a_, b_ = allowed(lo, hi, pin)
        if runs and max(runs[-1][2], a_) <= min(runs[-1][3], b_):
            f0, _, ra, rb = runs[-1]
            runs[-1] = (f0, i, max(ra, a_), min(rb, b_))
        else:
            runs.append((i, i, a_, b_))
    out: list[Window] = []
    for first, last, _ra, rb in runs:
        p = rb  # the index on the lowest note the run allows
        hi = max(g[3] for g in groups[first:last + 1])
        width = min(max(4, hi - p + 1), MAX_FRET)
        if out and out[-1][2] == p:
            out[-1] = (out[-1][0], groups[last][1], p, max(out[-1][3], width))
        else:
            out.append((groups[first][0], groups[last][1], p, width))
    return out


def _owner(starts: Sequence[float], t: float) -> int:
    """Index of the FHP a note at ``t`` falls under: the last one at or before
    it (within ``HAND_POSITION_MATCH_S``), the first when it comes before all."""
    return max(0, bisect.bisect_right(starts, t + HAND_POSITION_MATCH_S) - 1)


def fixed_windows(
    hand_positions: Sequence[HandPosition], positions: Sequence[Position | PinnedPosition]
) -> list[Window]:
    """The user's FHPs as windows over ``positions`` (one difficulty level's
    notes). Every note, open strings included, belongs to the FHP before it; an
    FHP left with no note at this level is dropped (the one before it carries
    on — there is nothing in between to frame), so a thinned level never ships
    a window over notes it does not have."""
    hps = sorted(hand_positions)
    if not hps or not positions:
        return []
    starts = [h.time for h in hps]
    owned: dict[int, tuple[float, float]] = {}
    for pos in positions:
        t, lt = pos[0], pos[1]
        k = _owner(starts, t)
        first, last = owned.get(k, (t, lt))
        owned[k] = (min(first, t), max(last, lt))
    return [
        (min(hps[k].time, first), last, hps[k].fret, hps[k].width)
        for k, (first, last) in sorted(owned.items())
    ]


def notes_outside(
    hand_positions: Sequence[HandPosition], notes: Sequence[tuple[float, int]]
) -> list[float]:
    """Times of the fretted notes ``(time, fret)`` their FHP does not frame —
    playable (the window is a highlight, not a limit), but worth a look."""
    hps = sorted(hand_positions)
    if not hps:
        return []
    starts = [h.time for h in hps]
    return [t for t, fret in notes if not hps[_owner(starts, t)].covers(fret)]
