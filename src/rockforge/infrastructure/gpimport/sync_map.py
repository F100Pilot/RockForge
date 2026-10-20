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
    score = [float(to_seconds(tick)) for tick, _ in points]
    audio = [a for _, a in points]
    if len(points) == 1:
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
