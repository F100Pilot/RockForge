"""Smoothing a video's per-bar marks (GitHub issue #26).

Songsterr marked bar 7 of a video 0.27 s early against bars 6 and 8, which
agree with the tab's tempo, and RockForge put every bar exactly on its mark.
``smooth_bar_times`` moves such a mark back where the score puts it, and only
when the user asks for it; a bar that is really held longer is left alone.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from rockforge.infrastructure.example_song import write_example_gp5
from rockforge.infrastructure.gpimport.parser import parse_gp_track
from rockforge.infrastructure.gpimport.sync_map import (
    smooth_bar_times,
    smoothed_bar_times_warning,
)

SCORE = [2.0 * i for i in range(12)]  # twelve bars of two seconds


def test_one_mark_off_between_neighbours_that_agree_is_moved_back() -> None:
    marks = [10.0 + t for t in SCORE]
    marks[6] -= 0.27  # bar 7 marked early, as in the issue
    out, moved = smooth_bar_times(marks, SCORE)
    assert moved == [7]
    assert out[6] == pytest.approx(10.0 + SCORE[6])
    assert [out[i] for i in range(12) if i != 6] == [marks[i] for i in range(12) if i != 6]


def test_a_mark_a_little_off_is_left_where_it_was() -> None:
    marks = [10.0 + t for t in SCORE]
    marks[6] -= 0.05  # under SMOOTH_MIN_OFF_S: a hand's ordinary error
    assert smooth_bar_times(marks, SCORE) == (marks, [])


def test_a_bar_that_is_really_held_longer_is_never_smoothed() -> None:
    # Bar 6 held a second longer (a fermata): every mark after it moves on.
    marks = [10.0 + t + (1.0 if i > 5 else 0.0) for i, t in enumerate(SCORE)]
    assert smooth_bar_times(marks, SCORE) == (marks, [])


def test_the_tempo_of_the_recording_is_not_what_is_compared() -> None:
    # A recording 10 % slower than the tab, with bar 7 marked early: the
    # neighbours are compared with the local tempo, not the tab's own.
    marks = [10.0 + 1.1 * t for t in SCORE]
    marks[6] -= 0.27
    out, moved = smooth_bar_times(marks, SCORE)
    assert moved == [7]
    assert out[6] == pytest.approx(10.0 + 1.1 * SCORE[6])


def test_marks_off_in_a_row_are_placed_between_the_nearest_good_ones() -> None:
    marks = [10.0 + t for t in SCORE]
    for i, d in ((4, 0.15), (5, -0.15), (6, 0.15)):
        marks[i] += d
    out, moved = smooth_bar_times(marks, SCORE)
    assert moved == [5, 6, 7]
    assert out[4:7] == pytest.approx([10.0 + SCORE[i] for i in (4, 5, 6)])


def test_the_first_and_last_marks_and_odd_input_are_left_alone() -> None:
    marks = [10.0 + t for t in SCORE]
    marks[0] -= 0.3
    marks[-1] += 0.3
    assert smooth_bar_times(marks, SCORE)[1] == []
    assert smooth_bar_times([1.0, 2.0], [0.0, 1.0]) == ([1.0, 2.0], [])
    odd = [1.0, math.nan, 3.0, 4.0]
    assert smooth_bar_times(odd, [0.0, 1.0, 2.0, 3.0])[1] == []


def test_the_warning_names_the_bars_moved() -> None:
    assert "bars 3-5, 9" in smoothed_bar_times_warning([3, 4, 5, 9])
    assert "4 mark(s)" in smoothed_bar_times_warning([3, 4, 5, 9])
    assert "already sat" in smoothed_bar_times_warning([])


def _downbeat(parsed, measure: int) -> float:  # type: ignore[no-untyped-def]
    return next(b.time for b in parsed.tempo_map.beats if b.measure == measure)


def test_a_gp5_is_timed_on_the_smoothed_marks_only_when_asked(tmp_path: Path) -> None:
    gp = write_example_gp5(tmp_path / "riff.gp5", "Riff", "Test")
    plain = parse_gp_track(gp, 0)
    bar = _downbeat(plain, 2) - _downbeat(plain, 1)  # the tab's own bar length
    marks = [1.0 + i * bar for i in range(16)]
    marks[6] -= 0.27
    as_marked = parse_gp_track(gp, 0, bar_times=marks)
    smoothed = parse_gp_track(gp, 0, bar_times=marks, smooth=True)
    assert _downbeat(as_marked, 7) == pytest.approx(6 * bar - 0.27, abs=1e-6)
    assert _downbeat(smoothed, 7) == pytest.approx(6 * bar, abs=1e-6)
    assert _downbeat(smoothed, 8) == pytest.approx(_downbeat(as_marked, 8), abs=1e-6)
    assert not any("smoothed" in w for w in as_marked.warnings)
    assert any("smoothed" in w and "bars 7" in w for w in smoothed.warnings)
