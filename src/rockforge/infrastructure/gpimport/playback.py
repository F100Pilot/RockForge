# SPDX-License-Identifier: MPL-2.0
#
# This Source Code Form is subject to the terms of the Mozilla Public License,
# v. 2.0. If a copy of the MPL was not distributed with this file, You can
# obtain one at https://mozilla.org/MPL/2.0/.
#
# Ported from alphaTab (https://github.com/CoderLine/alphaTab), Copyright (c)
# Daniel Kuschny and Contributors, which is MPL-2.0. The MPL is file-level, so
# this file keeps it while the rest of RockForge is MIT (THIRD_PARTY_NOTICES.md).
"""The order a Guitar Pro score's bars are PLAYED in: repeats, voltas and jumps.

A score is written once but played with its repeats (``|: … :|`` with a count),
alternate endings (voltas: bar 1st/2nd time) and jumps (D.C., D.S., al Coda,
al Fine). Rocksmith has none of these: the chart must list the bars as heard,
or every repeated section is missing and everything after it plays early
against the recording.

This is a port of alphaTab's playback order — ``Score._addMasterBarToRepeatGroups``
(how repeat groups are formed, nested and multiple closings included) and
``MidiPlaybackController`` (repeats, voltas as a bitmask of passes, and the
direction jumps) — so a chart plays its bars in the same order alphaTab does.
Bars are 0-based here.

One departure, on the return after a D.C./D.S.: alphaTab takes no repeats there
but plays every volta, so a 1st-time bar sounds again before the 2nd-time one.
The usual convention (Gould, *Behind Bars*) is that on the return the repeats
are not taken and only the LAST ending is played, and that is what this does.
Neither Guitar Pro format records a "play repeats after the jump" choice (no
field for it in GP3-5 nor in GPIF's ``<Directions>``), so nothing in the file
can say otherwise; ``jump_skips_repeats`` tells the parsers when the convention
changed what is heard, so they can say which one was assumed.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from rockforge.i18n import tr

# alphaTab's Direction names (model/Direction.ts).
TARGET_FINE = "TargetFine"
TARGET_SEGNO = "TargetSegno"
TARGET_SEGNO_SEGNO = "TargetSegnoSegno"
TARGET_CODA = "TargetCoda"
TARGET_DOUBLE_CODA = "TargetDoubleCoda"

# Guitar Pro names (PyGuitarPro DirectionSign names / GPIF <Target>/<Jump>) →
# alphaTab Direction names.
GP5_DIRECTIONS = {
    "Coda": TARGET_CODA,
    "Double Coda": TARGET_DOUBLE_CODA,
    "Segno": TARGET_SEGNO,
    "Segno Segno": TARGET_SEGNO_SEGNO,
    "Fine": TARGET_FINE,
    "Da Capo": "JumpDaCapo",
    "Da Capo al Coda": "JumpDaCapoAlCoda",
    "Da Capo al Double Coda": "JumpDaCapoAlDoubleCoda",
    "Da Capo al Fine": "JumpDaCapoAlFine",
    "Da Segno": "JumpDalSegno",
    "Da Segno al Coda": "JumpDalSegnoAlCoda",
    "Da Segno al Double Coda": "JumpDalSegnoAlDoubleCoda",
    "Da Segno al Fine": "JumpDalSegnoAlFine",
    "Da Segno Segno": "JumpDalSegnoSegno",
    "Da Segno Segno al Coda": "JumpDalSegnoSegnoAlCoda",
    "Da Segno Segno al Double Coda": "JumpDalSegnoSegnoAlDoubleCoda",
    "Da Segno Segno al Fine": "JumpDalSegnoSegnoAlFine",
    "Da Coda": "JumpDaCoda",
    "Da Double Coda": "JumpDaDoubleCoda",
}
GPIF_TARGETS = {
    "Coda": TARGET_CODA,
    "DoubleCoda": TARGET_DOUBLE_CODA,
    "Segno": TARGET_SEGNO,
    "SegnoSegno": TARGET_SEGNO_SEGNO,
    "Fine": TARGET_FINE,
}
GPIF_JUMPS = {
    "DaCapo": "JumpDaCapo",
    "DaCapoAlCoda": "JumpDaCapoAlCoda",
    "DaCapoAlDoubleCoda": "JumpDaCapoAlDoubleCoda",
    "DaCapoAlFine": "JumpDaCapoAlFine",
    "DaSegno": "JumpDalSegno",
    "DaSegnoAlCoda": "JumpDalSegnoAlCoda",
    "DaSegnoAlDoubleCoda": "JumpDalSegnoAlDoubleCoda",
    "DaSegnoAlFine": "JumpDalSegnoAlFine",
    "DaSegnoSegno": "JumpDalSegnoSegno",
    "DaSegnoSegnoAlCoda": "JumpDalSegnoSegnoAlCoda",
    "DaSegnoSegnoAlDoubleCoda": "JumpDalSegnoSegnoAlDoubleCoda",
    "DaSegnoSegnoAlFine": "JumpDalSegnoSegnoAlFine",
    "DaCoda": "JumpDaCoda",
    "DaDoubleCoda": "JumpDaDoubleCoda",
}

def jump_convention_warning() -> str:
    """What the parsers say when ``jump_skips_repeats`` is true."""
    return tr(
        "Depois do D.C./D.S., as repetições não voltam a ser tocadas e só se toca a "
        "última casa (a convenção habitual; o ficheiro Guitar Pro não diz qual se "
        "pretende). Se a gravação repete a secção nesse regresso, os compassos "
        "daí em diante ficam desencontrados.",
        "After the D.C./D.S., repeats are not taken again and only the last ending "
        "is played (the usual convention; a Guitar Pro file does not say which is "
        "meant). If the recording repeats the section on that return, the bars "
        "from there on will not line up.",
    )


# A malformed score must not unroll forever (alphaTab bounds its loops too).
MAX_PLAYED_PER_BAR = 64

_NORMAL, _JUMPED, _AL_CODA, _AL_DOUBLE_CODA, _AL_FINE = range(5)
_DA_CAPO = {
    "JumpDaCapo": _JUMPED,
    "JumpDaCapoAlCoda": _AL_CODA,
    "JumpDaCapoAlDoubleCoda": _AL_DOUBLE_CODA,
    "JumpDaCapoAlFine": _AL_FINE,
}
_DAL_SEGNO = {
    "JumpDalSegno": (_JUMPED, TARGET_SEGNO),
    "JumpDalSegnoAlCoda": (_AL_CODA, TARGET_SEGNO),
    "JumpDalSegnoAlDoubleCoda": (_AL_DOUBLE_CODA, TARGET_SEGNO),
    "JumpDalSegnoAlFine": (_AL_FINE, TARGET_SEGNO),
    "JumpDalSegnoSegno": (_JUMPED, TARGET_SEGNO_SEGNO),
    "JumpDalSegnoSegnoAlCoda": (_AL_CODA, TARGET_SEGNO_SEGNO),
    "JumpDalSegnoSegnoAlDoubleCoda": (_AL_DOUBLE_CODA, TARGET_SEGNO_SEGNO),
    "JumpDalSegnoSegnoAlFine": (_AL_FINE, TARGET_SEGNO_SEGNO),
}


@dataclass(frozen=True)
class BarFlow:
    """What a bar says about playback order."""

    repeat_start: bool = False
    repeat_count: int = 0  # times the repeated section plays (alphaTab); 0 = no repeat end
    alternate_endings: int = 0  # bitmask of passes: bit 0 = 1st time, bit 1 = 2nd…
    directions: frozenset[str] = frozenset()  # alphaTab Direction names


@dataclass
class _Group:
    opening: int | None = None
    closings: list[int] = field(default_factory=list)
    closed: bool = False


@dataclass
class _Repeat:
    """A repeat being played: its group, the passes made at each closing, and
    the closing reached (alphaTab's ``Repeat``)."""

    group: _Group
    iterations: list[int]
    closing: int = 0


def _repeat_groups(bars: Sequence[BarFlow]) -> list[_Group]:
    """The repeat group of each bar (alphaTab ``Score._addMasterBarToRepeatGroups``)."""
    group_of: list[_Group] = []
    current: _Group | None = None
    opened: list[_Group] = []
    properly_opened = 0
    for index, bar in enumerate(bars):
        if bar.repeat_start:
            if current is not None and current.closed:
                opened.pop()
                properly_opened -= 1
            current = _Group()
            opened.append(current)
            properly_opened += 1
        elif current is None:
            current = _Group()
            opened.append(current)
        if current.opening is None:
            current.opening = index
        group_of.append(current)
        if bar.repeat_count > 0:
            current.closings.append(index)
            current.closed = True
            if properly_opened > 1:
                opened.pop()
                properly_opened -= 1
                current = opened[-1] if opened else None
    return group_of


def playback_order(bars: Sequence[BarFlow]) -> list[int]:
    """Indexes of ``bars`` in the order they are played (alphaTab's, but the
    last ending only on the return after a jump — see the module docstring)."""
    return _unroll(bars)[0]


def jump_skips_repeats(bars: Sequence[BarFlow]) -> bool:
    """Whether a D.C./D.S. returns through a repeat or a volta, i.e. whether the
    "no repeats after the jump, last ending only" convention changed the bars
    heard (the file cannot say which was meant)."""
    return _unroll(bars)[1]


def _unroll(bars: Sequence[BarFlow]) -> tuple[list[int], bool]:
    n = len(bars)
    group_of = _repeat_groups(bars)
    last_ending: dict[int, int] = {}  # the group's highest volta bit = its last pass
    for bar, group in zip(bars, group_of, strict=True):
        if bar.alternate_endings:
            last_ending[id(group)] = max(last_ending.get(id(group), 0),
                                         1 << (bar.alternate_endings.bit_length() - 1))
    convention = False
    jumped_endings = 0
    stack: list[_Repeat] = []
    on_stack: set[int] = set()
    previous_endings = 0
    state = _NORMAL
    index = 0
    played: list[int] = []
    limit = max(1, n) * MAX_PLAYED_PER_BAR

    def find(target: str, start: int, backwards_first: bool) -> int:
        backwards = [i for i in range(start, -1, -1) if target in bars[i].directions]
        forwards = [i for i in range(start, n) if target in bars[i].directions]
        first, second = (backwards, forwards) if backwards_first else (forwards, backwards)
        return (first or second or [-1])[0]

    while index < n and len(played) < limit:
        bar = bars[index]
        group = group_of[index]
        # processCurrent: should this bar play on this pass?
        should_play = True
        if state == _NORMAL:
            endings = bar.alternate_endings or previous_endings
            if group.opening == index and group.closed and id(group) not in on_stack:
                stack.append(_Repeat(group, [0] * len(group.closings)))
                on_stack.add(id(group))
                previous_endings = 0
                endings = bar.alternate_endings
            if stack and endings:
                repeat = stack[-1]
                iteration = repeat.iterations[repeat.closing]
                previous_endings = endings
                should_play = bool(endings & (1 << iteration))
        else:
            # The return after a jump: no repeats (moveNext below) and the last
            # ending only. A bar after a volta bar without one of its own is
            # still inside that ending, as in the normal pass.
            if group.opening == index:
                jumped_endings = 0
            endings = bar.alternate_endings or jumped_endings
            jumped_endings = endings
            last = last_ending.get(id(group), 0)
            if bar.repeat_count > 1 or (endings and last):
                convention = True
            if endings and last and not endings & last:
                should_play = False
        if should_play:
            played.append(index)

        # moveNext, directions first.
        directions = bar.directions
        if state == _NORMAL and not directions:
            pass  # normal repeats below
        elif not directions:
            index += 1
            continue
        elif state == _NORMAL:
            jump = next((d for d in _DA_CAPO if d in directions), None)
            if jump is not None:
                index, state = 0, _DA_CAPO[jump]
                stack.clear()
                on_stack.clear()
                previous_endings = jumped_endings = 0
                continue
            jumped = False
            for name, (new_state, segno_name) in _DAL_SEGNO.items():
                if name not in directions:
                    continue
                segno = find(segno_name, index, backwards_first=True)
                if segno != -1:  # no segno: this jump is ignored, as alphaTab does
                    index, state = segno, new_state
                    stack.clear()
                    on_stack.clear()
                    previous_endings = jumped_endings = 0
                    jumped = True
                    break
            if jumped:
                continue
        else:
            coda = {_AL_CODA: ("JumpDaCoda", TARGET_CODA),
                    _AL_DOUBLE_CODA: ("JumpDaDoubleCoda", TARGET_DOUBLE_CODA)}.get(state)
            if coda is not None and coda[0] in directions:
                landing = find(coda[1], index, backwards_first=False)
                if landing == -1:
                    index += 1
                else:
                    index, state = landing, _NORMAL
                continue
            if state == _AL_FINE and TARGET_FINE in directions:
                break
            index += 1
            continue

        # moveNext with normal repeats.
        count = bar.repeat_count - 1
        if stack and count > 0:
            repeat = stack[-1]
            iterations, closing = repeat.iterations, repeat.closing
            if iterations[closing] < count:
                index = repeat.group.opening or 0
                iterations[closing] += 1
                for i in range(closing):
                    iterations[i] = 0
                repeat.closing = 0
                previous_endings = 0
            elif closing < len(repeat.group.closings) - 1:
                repeat.closing += 1
                index += 1
            else:
                stack.pop()
                on_stack.discard(id(repeat.group))
                index += 1
        else:
            index += 1
    return played, convention
