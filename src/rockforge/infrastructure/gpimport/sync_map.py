"""Re-timing a score onto a recording from per-position time points.

Two sources feed it, both a list of ``(score tick, seconds in the recording)``:
Guitar Pro 8's own audio-track sync points (``gpif_parser._sync_points``) and
externally supplied per-bar times — Songsterr's human-marked measure timestamps
(:func:`bar_time_points`). Shared by both GP parsers so the two formats can
never disagree about what a point means.
"""

from __future__ import annotations

import bisect
import math
import statistics
from collections.abc import Callable, Sequence


def audio_clock(
    to_seconds: Callable[[int], float], points: list[tuple[int, float]]
) -> Callable[[int], float] | None:
    """tick → seconds in the synced audio's clock, or None with no sync points.

    Each pair of neighbouring points maps the score's own time span linearly
    onto the audio span between them, so tempo changes authored inside a span
    keep their proportions. Before the first point and after the last, the
    nearest span's stretch continues; a lone point is a pure shift. alphaTab
    holds a constant BPM after each point instead — the two agree exactly
    whenever a span carries no tempo change of its own.
    """
    if not points:
        return None
    score: list[float] = []
    audio: list[float] = []
    for tick, at in points:
        s = float(to_seconds(tick))
        # Two points on one instant of the score (a bar of no length) would
        # divide its span by zero: the first one says where that instant is.
        if score and s <= score[-1]:
            continue
        score.append(s)
        audio.append(at)
    if len(score) == 1:
        return lambda tick: audio[0] + float(to_seconds(tick)) - score[0]

    def convert(tick: int) -> float:
        s = float(to_seconds(tick))
        i = min(max(bisect.bisect_right(score, s) - 1, 0), len(score) - 2)
        ratio = (audio[i + 1] - audio[i]) / (score[i + 1] - score[i])
        return audio[i] + (s - score[i]) * ratio

    return convert


def relative_to_bar_one(
    to_seconds: Callable[[int], float], points: list[tuple[int, float]]
) -> Callable[[int], float]:
    """The score re-timed onto the synced audio, RELATIVE to bar 1.

    Relative so ``offset_s`` keeps the one meaning it has for every file —
    where bar 1 sits in the recording. The absolute value GP8 stored is what
    ``gpif_parser.sync_start_s`` reports, so the wizard can pre-fill it.
    """
    clock = audio_clock(to_seconds, points)
    if clock is None:
        return to_seconds
    origin = clock(0)
    return lambda tick: clock(tick) - origin


def bar_time_points(
    bar_start_ticks: Sequence[int], bar_times: Sequence[float]
) -> tuple[list[tuple[int, float]], int]:
    """Pair each bar's start tick with an externally supplied time for it.

    ``bar_times[i]`` is where bar ``i + 1`` starts in the recording — the shape
    of Songsterr's per-measure video timestamps. Pairs are taken in order up to
    the shorter list (a GP that is not the tab the times were marked on shows
    up as a length mismatch, which the caller reports). A time that is not
    finite or does not move forward is skipped and counted: it would fold the
    timeline back on itself. A negative time (a count-in marked before the
    video starts) is an ordinary point.
    """
    points: list[tuple[int, float]] = []
    skipped = 0
    for tick, when in zip(bar_start_ticks, bar_times, strict=False):
        when = float(when)
        # A time before the recording's first second (Songsterr count-in marks
        # can start at t<0) is kept: the timeline is relative to bar 1, and
        # offset_s takes bar 1's own (negative) time, as for a GP8 file whose
        # bar 1 comes before its audio. Skipping it made bar 1 an extrapolation
        # of the later marks while offset_s stayed the real mark, shifting the
        # whole song by their difference.
        if not math.isfinite(when) or (points and when <= points[-1][1]):
            skipped += 1
            continue
        points.append((int(tick), when))
    return points, skipped


# Smoothing externally supplied bar times (``smooth_bar_times``). A mark is
# re-placed when it sits more than SMOOTH_MIN_OFF_S off where the score's own
# proportions put it between its neighbours, while those two neighbours span
# what the score says at the local tempo (within SMOOTH_PAIR_TOL) — one mark
# off, not a real change of tempo. The local tempo is the median of the marked
# bars' tempo ratios over SMOOTH_WINDOW bars either side.
SMOOTH_MIN_OFF_S = 0.08
SMOOTH_PAIR_TOL = 0.04
SMOOTH_WINDOW = 4


def smooth_bar_times(
    bar_times: Sequence[float], score_starts: Sequence[float]
) -> tuple[list[float], list[int]]:
    """Bar times with the marks that sit off between their neighbours moved
    back where the score puts them, and the (1-based) bars moved.

    ``score_starts[i]`` is where bar ``i + 1`` starts in the score's own clock
    (its tempo map). GitHub issue #26: Songsterr marked bar 7 of a video 0.27 s
    early against bars 6 and 8, which agree with the tab's tempo, and every bar
    was placed exactly on its mark. A run of marks off in a row is re-placed
    between the nearest marks that are not, by the score's proportions. A bar
    that is really held longer (a fermata) leaves its two neighbours spanning
    more than the score says, so it is never touched; neither is the first or
    the last mark, nor a time that is not finite. Off by default — the marks
    are the recording's word unless the user asks."""
    n = min(len(bar_times), len(score_starts))
    v = [float(x) for x in bar_times[:n]]
    s = [float(x) for x in score_starts[:n]]
    if n < 3 or not all(math.isfinite(x) for x in v + s):
        return list(bar_times), []
    flagged: set[int] = set()
    for i in range(1, n - 1):
        e1, e2 = s[i] - s[i - 1], s[i + 1] - s[i]
        span = v[i + 1] - v[i - 1]
        if e1 <= 0 or e2 <= 0 or span <= 0:
            continue
        lo, hi = max(1, i - SMOOTH_WINDOW), min(n - 1, i + SMOOTH_WINDOW + 1)
        ratios = [
            (v[j] - v[j - 1]) / (s[j] - s[j - 1])
            for j in range(lo, hi) if s[j] > s[j - 1]
        ]
        local = statistics.median(ratios)
        if local <= 0 or abs(span / (e1 + e2) / local - 1) > SMOOTH_PAIR_TOL:
            continue
        where = v[i - 1] + span * e1 / (e1 + e2)
        if abs(v[i] - where) > SMOOTH_MIN_OFF_S:
            flagged.add(i)
    out = [float(x) for x in bar_times]
    i = 1
    while i < n - 1:
        if i not in flagged:
            i += 1
            continue
        j = i
        while j + 1 in flagged:
            j += 1
        a, b = i - 1, j + 1
        for k in range(i, j + 1):
            out[k] = v[a] + (v[b] - v[a]) * (s[k] - s[a]) / (s[b] - s[a])
        i = j + 1
    return out, sorted(k + 1 for k in flagged)


def _bar_runs(bars: Sequence[int]) -> str:
    """1, 2, 3, 7, 9, 10 → "1-3, 7, 9-10"."""
    runs: list[str] = []
    last = -2
    for bar in bars:
        if runs and bar == last + 1:
            first = runs[-1].split("-")[0]
            runs[-1] = f"{first}-{bar}"
        else:
            runs.append(str(bar))
        last = bar
    return ", ".join(runs)


def smoothed_bar_times_warning(bars: Sequence[int]) -> str:
    """What smoothing the bar times changed."""
    if not bars:
        return "bar times smoothed: every mark already sat where its neighbours put it"
    return (
        f"bar times smoothed: {len(bars)} mark(s) that sat off between their neighbours "
        f"were moved where the tab's tempo puts them (bars {_bar_runs(bars)})"
    )


def bar_times_warnings(n_bars: int, n_times: int, skipped: int) -> list[str]:
    """What to tell the user about externally supplied bar times."""
    notes = [
        f"bar times from an external source (e.g. Songsterr) re-time the chart: "
        f"{n_times} times for {n_bars} bars"
    ]
    if n_times != n_bars:
        notes.append(
            f"the bar times do not match the file's bar count ({n_times} vs {n_bars}) — "
            "they were probably marked on a different version of the tab; check the "
            "sync from the first bar where they diverge"
        )
    if skipped:
        notes.append(f"{skipped} bar time(s) ignored: not finite, or not after the previous one")
    return notes
