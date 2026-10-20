"""Songsterr markers that start before the video's first second (t < 0).

A community-marked song can carry its first bars at negative times — a count-in
marked before the video starts (GitHub PR #5). They are ordinary points: the
timeline is relative to bar 1 and ``offset_s`` takes bar 1's own negative time,
as for a Guitar Pro 8 file whose bar 1 comes before its audio. Skipping them
made bar 1 an extrapolation of the later marks while ``offset_s`` stayed the
real mark, so every bar landed off by their difference.
"""

from __future__ import annotations

import sys
from pathlib import Path

import guitarpro as gp

from rockforge.application.gp_pipeline import MIN_LEAD_S
from rockforge.infrastructure.gpimport.sync_map import bar_time_points
from rockforge.infrastructure.rsxml.reader import read_arrangement_xml

sys.path.insert(0, str(Path(__file__).parent))
from test_merge_tracks import _beat, _run  # noqa: E402


def test_negative_markers_are_kept_as_points() -> None:
    ticks = [0, 1920, 3840, 5760, 7680]
    times = [-15.12, -0.12, 1.76, 3.60, 5.41]
    points, skipped = bar_time_points(ticks, times)
    assert skipped == 0
    assert points == list(zip(ticks, times, strict=True))


def test_a_marker_that_does_not_move_forward_is_still_skipped() -> None:
    points, skipped = bar_time_points([0, 1920, 3840], [-3.0, -3.5, 1.0])
    assert skipped == 1
    assert points == [(0, -3.0), (3840, 1.0)]


def test_every_bar_lands_on_its_mark_when_the_count_in_is_marked_before_the_video(
    tmp_path: Path,
) -> None:
    """Eight bars at 120 BPM, the count-in marked a little slower than the
    rest and before the video starts; the start is bar 1's mark, as the wizard
    pre-fills it. Every bar's note must sit on its own mark."""
    song = gp.Song()
    song.title, song.artist, song.tempo = "Count-in", "Band", 120
    while len(song.measureHeaders) < 8:
        header = gp.MeasureHeader()
        header.number = len(song.measureHeaders) + 1
        song.addMeasureHeader(header)
    for i, header in enumerate(song.measureHeaders):
        header.start = 960 + i * 3840
    track = song.tracks[0]
    while len(track.measures) < 8:
        track.measures.append(gp.Measure(track, song.measureHeaders[len(track.measures)]))
    for measure in track.measures:
        _beat(measure.voices[0], 1, [(3, 5)])  # one whole note on each downbeat
    path = tmp_path / "count_in.gp5"
    gp.write(song, str(path))
    times = [-4.6, -2.2] + [0.05 + 2 * i for i in range(6)]

    result = _run(path, tmp_path, combo_track=0, bar_times=times, offset_s=times[0])
    xml = next(Path(result.packaging.bundle_dir).glob("arrangement_*.xml"))
    pad = max(0.0, MIN_LEAD_S - times[0])
    landed = [n.time - pad for n in read_arrangement_xml(xml).notes]
    assert [round(t, 3) for t in landed] == [round(t, 3) for t in times]
