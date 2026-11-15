"""Bars and beats inserted into or removed from a chart's grid.

A tab that has a bar the recording does not (a repeat played once more on
paper), or lacks one it does, cannot be fixed by stretching time: the bar
before the gap would take the whole difference and its beats would no longer
be beats. Here the grid itself changes — a bar or a beat is added with the
spacing of its neighbour, or taken out — and everything after it moves by
exactly that length, so the bars on either side keep their tempo.

An edit is MUSICAL ("insert a bar after bar 12", "remove beat 3 of bar 20"),
resolved on the grid as it stands when the edit is applied — so it composes
with the sync corrections before and after it, and a later tempo change moves
it along with the bar it names. ``edit_grid`` turns one into the new grid plus
the ``GridStep``s that say how every other time moves.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from rockforge.domain.music import Beat

BAR_EDIT_OPS = ("insert_bar", "remove_bar", "insert_beat", "remove_beat")
MAX_BAR_EDIT_COUNT = 16

# A note within this of a bar line counts as on it (the XML rounds to the ms).
EDGE_S = 0.001


@dataclass(frozen=True)
class BarEdit:
    """``insert_bar``: ``count`` empty bars after bar ``bar`` (0 = before bar
    1), each as long as that bar (bar 1 for 0) and with its beats.
    ``remove_bar``: bar ``bar`` and the ``count - 1`` after it, with their notes.
    ``insert_beat``: ``count`` beats after beat ``beat`` of bar ``bar``, each as
    long as that beat. ``remove_beat``: beat ``beat`` of bar ``bar`` and the
    ``count - 1`` after it, with their notes."""

    op: str
    bar: int
    beat: int = 1
    count: int = 1

    def __post_init__(self) -> None:
        if self.op not in BAR_EDIT_OPS:
            raise ValueError(f"unknown bar edit {self.op!r}")
        if self.bar < (0 if self.op == "insert_bar" else 1):
            raise ValueError(f"no bar {self.bar} to edit")
        if self.beat < 1:
            raise ValueError("beats are counted from 1")
        if not 1 <= self.count <= MAX_BAR_EDIT_COUNT:
            raise ValueError(f"a bar edit repeats 1 to {MAX_BAR_EDIT_COUNT} times")

    def as_dict(self) -> dict[str, object]:
        return {"op": self.op, "bar": self.bar, "beat": self.beat, "count": self.count}

    def describe(self) -> str:
        times = f"{self.count} " if self.count > 1 else "a "
        plural = "s" if self.count > 1 else ""
        if self.op == "insert_bar":
            where = "before bar 1" if self.bar == 0 else f"after bar {self.bar}"
            return f"{times}bar{plural} inserted {where}"
        if self.op == "remove_bar":
            return f"{times}bar{plural} removed from bar {self.bar}"
        if self.op == "insert_beat":
            return f"{times}beat{plural} inserted after beat {self.beat} of bar {self.bar}"
        return f"{times}beat{plural} removed from beat {self.beat} of bar {self.bar}"


def bar_edit_from_stage(stage: object) -> BarEdit | None:
    """The bar edit a stored sync stage holds (``{"bar_edit": {...}}``), None
    for an ordinary round of anchors. ValueError for a broken one."""
    if not isinstance(stage, Mapping):
        return None
    raw = stage.get("bar_edit")
    if not isinstance(raw, Mapping):
        raise ValueError("a bar edit stage needs a bar_edit object")

    def whole(key: str, default: int | None = None) -> int:
        value = raw.get(key, default)
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"bar edit {key} must be a whole number")
        return value

    op = raw.get("op")
    if not isinstance(op, str):
        raise ValueError("bar edit op must be text")
    return BarEdit(op=op, bar=whole("bar"), beat=whole("beat", 1), count=whole("count", 1))


@dataclass(frozen=True)
class GridStep:
    """One length of time added at ``start`` (``insert``) or taken out from
    ``start`` to ``start + length``. ``at`` moves a moment something starts,
    ``end`` a moment something stops (a sustain's end), ``drops`` says whether
    something starting there goes with a removed stretch."""

    start: float
    length: float
    insert: bool

    @property
    def stop(self) -> float:
        return self.start + self.length

    def at(self, t: float) -> float:
        if self.insert:
            return t + self.length if t >= self.start - EDGE_S else t
        if t < self.start - EDGE_S:
            return t
        if t < self.stop - EDGE_S:
            return self.start
        return t - self.length

    def end(self, t: float) -> float:
        if self.insert:
            return t + self.length if t > self.start + EDGE_S else t
        if t <= self.start + EDGE_S:
            return t
        if t <= self.stop + EDGE_S:
            return self.start
        return t - self.length

    def drops(self, t: float) -> bool:
        return not self.insert and self.start - EDGE_S <= t < self.stop - EDGE_S


def _bar_span(beats: Sequence[Beat], number: int) -> tuple[int, int]:
    """Indices of bar ``number``'s downbeat and of the downbeat after it (the
    next bar's, or the closing bar line)."""
    downs = [i for i, b in enumerate(beats) if b.measure > 0]
    for k, i in enumerate(downs[:-1]):
        if beats[i].measure == number:
            return i, downs[k + 1]
    raise ValueError(f"the chart has no bar {number}")


def _renumber(beats: list[Beat], first: int) -> list[Beat]:
    out: list[Beat] = []
    n = first
    for b in beats:
        if b.measure > 0:
            out.append(Beat(time=b.time, measure=n))
            n += 1
        else:
            out.append(b)
    return out


def _moved(beats: Sequence[Beat], step: GridStep, keep_from: float) -> list[Beat]:
    """The beats before ``step.start`` as they are, those from ``keep_from`` on
    moved by the step (a removed stretch's own beats are left out)."""
    before = [b for b in beats if b.time < step.start - EDGE_S]
    after = [b for b in beats if b.time >= keep_from - EDGE_S]
    shift = step.length if step.insert else -step.length
    return before + [Beat(time=b.time + shift, measure=b.measure) for b in after]


def _one_step(beats: list[Beat], edit: BarEdit) -> tuple[list[Beat], GridStep]:
    downs = [b for b in beats if b.measure > 0]
    if len(downs) < 2:
        raise ValueError("the chart has no complete bar")
    first = downs[0].measure
    if edit.op == "insert_bar":
        number = edit.bar if edit.bar > 0 else first
        s, e = _bar_span(beats, number)
        length = beats[e].time - beats[s].time
        start = beats[e].time if edit.bar > 0 else beats[s].time
        step = GridStep(start=start, length=length, insert=True)
        new = [Beat(time=start + b.time - beats[s].time, measure=1 if k == 0 else -1)
               for k, b in enumerate(beats[s:e])]
        moved = _moved(beats, step, start)
        cut = sum(1 for b in moved if b.time < start - EDGE_S)
        return _renumber(moved[:cut] + new + moved[cut:], first), step
    if edit.op == "remove_bar":
        if len(downs) < 3:
            raise ValueError("the chart's only bar cannot be removed")
        s, e = _bar_span(beats, edit.bar)
        step = GridStep(start=beats[s].time, length=beats[e].time - beats[s].time, insert=False)
        return _renumber(_moved(beats, step, beats[e].time), first), step
    s, e = _bar_span(beats, edit.bar)
    inside = beats[s:e]
    if edit.beat > len(inside):
        raise ValueError(f"bar {edit.bar} has {len(inside)} beats, not {edit.beat}")
    k = edit.beat - 1
    this = inside[k].time
    nxt = inside[k + 1].time if k + 1 < len(inside) else beats[e].time
    if edit.op == "insert_beat":
        step = GridStep(start=nxt, length=nxt - this, insert=True)
        moved = _moved(beats, step, nxt)
        cut = sum(1 for b in moved if b.time < nxt - EDGE_S)
        return moved[:cut] + [Beat(time=nxt, measure=-1)] + moved[cut:], step
    if len(inside) < 2:
        raise ValueError(f"bar {edit.bar} has a single beat — remove the bar instead")
    step = GridStep(start=this, length=nxt - this, insert=False)
    moved = _moved(beats, step, nxt)
    if k == 0:  # the beat after the removed downbeat starts the bar now
        cut = sum(1 for b in moved if b.time < this - EDGE_S)
        moved[cut] = Beat(time=moved[cut].time, measure=edit.bar)
    return moved, step


def edit_grid(beats: Sequence[Beat], edit: BarEdit) -> tuple[list[Beat], list[GridStep]]:
    """The grid after ``edit`` and the steps that took it there, in order (an
    edit repeated ``count`` times is that many steps, each on the grid the one
    before left). ValueError when the bar or beat it names is not there."""
    grid = list(beats)
    steps: list[GridStep] = []
    for _ in range(edit.count):
        grid, step = _one_step(grid, edit)
        steps.append(step)
    return grid, steps


def source_bars(built_count: int, edits: Sequence[BarEdit]) -> list[int | None] | None:
    """For each bar of a chart built with ``edits``, the bar of the score it
    came from (None for an inserted one); None when the count does not add up
    (a stored edit the build could not apply)."""
    original = built_count
    for e in edits:
        if e.op == "insert_bar":
            original -= e.count
        elif e.op == "remove_bar":
            original += e.count
    if original < 1:
        return None
    bars: list[int | None] = list(range(1, original + 1))
    for e in edits:
        if e.op == "insert_bar":
            if e.bar > len(bars):
                return None
            bars[e.bar:e.bar] = [None] * e.count
        elif e.op == "remove_bar":
            if e.bar + e.count - 1 > len(bars):
                return None
            del bars[e.bar - 1:e.bar - 1 + e.count]
    return bars if len(bars) == built_count else None
