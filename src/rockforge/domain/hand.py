"""Fret-hand positions (FHPs, Rocksmith's "anchors"): where the hand sits.

An FHP is active from its time until the next one; the game highlights
``width`` frets from ``fret`` and the camera follows it. RockForge places them
automatically (``auto_windows``), and the user can place their own in the tab
viewer (``Arrangement.hand_positions``), which then decide every one of the
chart's FHPs — the automatic ones only ever fill a chart the user left alone.
"""

from __future__ import annotations

import bisect
import math
from collections.abc import Sequence
from dataclasses import dataclass

MAX_FRET = 24
MIN_WIDTH = 2
MAX_WIDTH = 12
# Max frets the automatic placement folds into one window before it moves the
# hand. 4 = the standard Rocksmith fret-hand window; a wider (5) merge let a
# stray low note (a lone fret 1) fold in with a fret 3-5 chord run, so the
# window sat a fret or two below the notes played. A single chord that spans
# more keeps its own full width — the cap only limits merging neighbours.
AUTO_WINDOW_SPAN = 4
# An FHP read back from the built XML is rounded to the millisecond while a
# note keeps the parser's float; an FHP placed on a note must still be AT it.
HAND_POSITION_MATCH_S = 0.005

# (first_time, last_time, frets) — one per note or chord, time-sorted; an open
# string has no frets.
Position = tuple[float, float, Sequence[int]]
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


def window_for(frets: Sequence[int]) -> tuple[int, int]:
    """(fret, width) that frames the given frets; open strings do not count."""
    used = [f for f in frets if f > 0]
    if not used:
        return 1, 4
    lo, hi = min(used), max(used)
    width = min(max(4, hi - lo + 1), MAX_FRET)
    return max(1, min(lo, MAX_FRET + 1 - width)), width


def auto_windows(positions: Sequence[Position]) -> list[Window]:
    """The automatic FHPs: consecutive fretted positions grouped greedily into
    one window spanning at most ``AUTO_WINDOW_SPAN`` frets, so the hand stays
    put instead of thrashing note to note. Open strings place no window."""
    fretted = [(t, lt, fr) for t, lt, fr in positions if any(f > 0 for f in fr)]
    out: list[Window] = []
    i = 0
    while i < len(fretted):
        used = [f for f in fretted[i][2] if f > 0]
        lo, hi, last = min(used), max(used), fretted[i][1]
        j = i + 1
        while j < len(fretted):
            nxt = [f for f in fretted[j][2] if f > 0]
            cand_lo, cand_hi = min(lo, *nxt), max(hi, *nxt)
            if cand_hi - cand_lo + 1 > AUTO_WINDOW_SPAN:
                break
            lo, hi, last = cand_lo, cand_hi, fretted[j][1]
            j += 1
        width = min(max(4, hi - lo + 1), MAX_FRET)
        out.append((fretted[i][0], last, max(1, min(lo, MAX_FRET + 1 - width)), width))
        i = j
    return out


def _owner(starts: Sequence[float], t: float) -> int:
    """Index of the FHP a note at ``t`` falls under: the last one at or before
    it (within ``HAND_POSITION_MATCH_S``), the first when it comes before all."""
    return max(0, bisect.bisect_right(starts, t + HAND_POSITION_MATCH_S) - 1)


def fixed_windows(
    hand_positions: Sequence[HandPosition], positions: Sequence[Position]
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
    for t, lt, _ in positions:
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
