"""Songsterr markers that start before the video's first second (t < 0).

A community-marked song can carry its first bars at negative times — a count-in
marked before the video starts. Those anchors are unusable (the downloaded
audio begins at the video's own t=0), so ``bar_time_points`` skips them — but
it must still consume their bars: dropping them instead would shift every
later bar onto the wrong time.
"""

from rockforge.infrastructure.gpimport.sync_map import bar_time_points


def test_negative_markers_are_skipped_without_shifting_alignment() -> None:
    # 4 bars, ticks at 1920/bar; markers: two negative, then 1.76, 3.60, ...
    ticks = [0, 1920, 3840, 5760, 7680]
    times = [-15.12, -0.12, 1.76, 3.60, 5.41]
    points, skipped = bar_time_points(ticks, times)
    assert skipped == 2
    # bars 3..5 keep THEIR OWN times — not the dropped pair's
    assert points == [(3840, 1.76), (5760, 3.60), (7680, 5.41)]


def test_all_negative_markers_yield_no_points() -> None:
    points, skipped = bar_time_points([0, 1920], [-3.0, -1.0])
    assert points == []
    assert skipped == 2
