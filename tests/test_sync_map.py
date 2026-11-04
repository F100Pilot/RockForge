"""The shared re-timing of a score onto a recording (``gpimport/sync_map.py``)."""

from __future__ import annotations

import pytest

from rockforge.infrastructure.gpimport.sync_map import audio_clock


def test_two_points_on_one_instant_of_the_score_do_not_divide_by_zero() -> None:
    """A bar of no length puts two points on the same score time; the span
    between them divided by zero. The first one says where that instant is."""
    def to_seconds(tick: int) -> float:
        return tick / 960 * 0.5  # 120 BPM

    clock = audio_clock(to_seconds, [(0, 1.0), (0, 1.2), (3840, 3.0)])
    assert clock is not None
    assert clock(0) == pytest.approx(1.0)
    assert clock(3840) == pytest.approx(3.0)
    assert clock(1920) == pytest.approx(2.0)
    only = audio_clock(to_seconds, [(960, 4.0), (960, 9.0)])
    assert only is not None and only(960) == pytest.approx(4.0)
