"""Diagnosis of HOW a chart is out of sync — progressive drift vs a sudden jump
vs a structural mismatch. Pure: no audio, no ml extra."""

from __future__ import annotations

import pytest

from rockforge.application.sync_analysis import (
    SyncPoint,
    build_correspondence,
    diagnose,
)


def _bars(n: int, spacing: float = 2.0) -> list[float]:
    return [i * spacing for i in range(n)]


def _beats(n: int, spacing: float = 0.5) -> list[float]:
    return [i * spacing for i in range(n)]


def _series(f, times: list[float], matched: bool = True) -> list[SyncPoint]:
    """Chart onsets at `times`, each sounding at chart + f(chart) in the audio."""
    return [SyncPoint(chart_time=t, audio_time=t + f(t), matched=matched) for t in times]


def test_progressive_drift_is_diagnosed_and_a_slower_bpm_recommended() -> None:
    """The user's Case 1: starts in sync and slides steadily late.
    0:00 → 0.0s, 1:00 → +0.3s, 2:00 → +1.0s, 3:00 → +1.8s.
    That must read as a TEMPO problem and recommend a LOWER BPM, not a jump."""
    times = [t * 0.5 for t in range(361)]           # 3 minutes of 8th notes
    pts = _series(lambda t: 0.010 * t, times)       # 10 ms of drift per second
    d = diagnose(pts, _bars(91), _beats(361))

    assert d.classification == "global_tempo_mismatch"
    assert d.jumps == []                            # a drift is NOT a jump
    drift = [s for s in d.segments if s.kind == "drift"]
    assert drift, f"expected a drift segment, got {[s.kind for s in d.segments]}"
    s = drift[0]
    assert s.slope == pytest.approx(0.010, abs=1e-3)
    # 120 BPM chart running 1% fast → the recording is really ~118.8 BPM.
    assert s.original_bpm == pytest.approx(120.0, abs=0.5)
    assert s.recommended_bpm == pytest.approx(120.0 / 1.01, abs=0.5)
    assert s.recommended_bpm < s.original_bpm       # slow it down, not up


def test_sudden_jump_is_not_reported_as_a_tempo_problem() -> None:
    """The user's Case 2: in sync until 1:10, then abruptly +2.0s and steady.
    A BPM change here would smear a local error over correct music."""
    times = [t * 0.5 for t in range(361)]
    pts = _series(lambda t: 0.0 if t < 70.0 else 2.0, times)
    d = diagnose(pts, _bars(91), _beats(361))

    assert d.classification == "sudden_offset"
    assert len(d.jumps) == 1
    j = d.jumps[0]
    assert j.chart_time == pytest.approx(70.0, abs=1.0)
    assert j.step_s == pytest.approx(2.0, abs=0.01)
    assert j.measure > 1                            # located on a real measure
    # Both sides are themselves in sync — nothing to re-tempo.
    assert all(s.kind == "synced" for s in d.segments)
    assert d.first_divergence_s == pytest.approx(70.0, abs=1.0)


def test_a_perfectly_synced_chart_is_left_alone() -> None:
    """No drift, no jump: the tool must propose nothing."""
    times = [t * 0.5 for t in range(241)]
    d = diagnose(_series(lambda t: 0.0, times), _bars(61), _beats(241))
    assert d.classification == "in_sync"
    assert d.jumps == []
    assert all(s.kind == "synced" for s in d.segments)
    assert d.first_divergence_s is None


def test_local_drift_leaves_the_synced_part_untouched() -> None:
    """Sync is correct for the first half and drifts only after — the fix must
    be scoped to the second half, which is the whole point of the feature."""
    times = [t * 0.5 for t in range(361)]
    pts = _series(lambda t: 0.0 if t < 90.0 else 0.012 * (t - 90.0), times)
    d = diagnose(pts, _bars(91), _beats(361))

    assert d.classification in {"local_tempo_mismatch", "mixed"}
    drift = [s for s in d.segments if s.kind == "drift"]
    synced = [s for s in d.segments if s.kind == "synced"]
    assert drift and synced
    assert synced[0].start_chart < 10.0             # the good part is recognised
    assert drift[0].start_chart >= 60.0             # and the fix starts later
    assert d.first_divergence_s is not None and d.first_divergence_s >= 60.0


def test_unmatched_onsets_are_flagged_structural_not_re_tempoed() -> None:
    """Where the tab's notes don't correspond to the audio, no time warp helps —
    it must be labelled structural rather than given a BPM recommendation."""
    times = [t * 0.5 for t in range(241)]
    pts = _series(lambda t: 0.0, times, matched=False)
    d = diagnose(pts, _bars(61), _beats(241))
    assert d.classification == "structural_mismatch"
    assert d.confidence == 0.0
    assert all(s.recommended_bpm == 0.0 or s.kind == "structural" for s in d.segments)


def test_too_few_points_refuses_to_guess() -> None:
    d = diagnose([SyncPoint(0.0, 0.0, True)], _bars(4))
    assert d.classification == "insufficient_data"
    assert d.warnings


def test_build_correspondence_snaps_to_real_attacks() -> None:
    """Chart onsets are matched to the nearest real audio attack; an onset with
    no attack nearby is kept but marked unmatched (not evidence)."""
    chart = [0.0, 1.0, 2.0, 3.0]
    rec = [0.0, 1.03, 2.05, 9.0]          # the 4th has no partner
    pts = build_correspondence(chart, rec, chart_start=0.0, rec_start=0.0)
    assert [p.matched for p in pts] == [True, True, True, False]
    assert pts[1].audio_time == pytest.approx(1.03)
    assert pts[2].residual == pytest.approx(0.05, abs=1e-6)


def test_build_correspondence_handles_empty_input() -> None:
    assert build_correspondence([], [1.0], chart_start=0, rec_start=0) == []
    assert build_correspondence([1.0], [], chart_start=0, rec_start=0) == []


def test_multi_slope_drift_is_split_into_scoped_corrections() -> None:
    """A drift whose RATE changes must become several scoped corrections.

    Uses the reported real-world shape: 0:00 → 0.0s, 1:00 → +0.3s, 2:00 → +1.0s,
    3:00 → +1.8s. Two regressions are guarded here:
    - classifying on a segment's own total drift let a long gentle slide be
      chopped into short pieces that each looked "synced" while the song ended
      almost two seconds out; classification is on the drift RATE instead.
    - the eager split fragmented one smooth passage into many corrections;
      adjacent segments telling the same story are merged.
    """
    import bisect

    kx, ky = [0.0, 60.0, 120.0, 180.0], [0.0, 0.3, 1.0, 1.8]

    def drift(t: float) -> float:
        i = max(0, min(bisect.bisect_right(kx, t) - 1, len(kx) - 2))
        return ky[i] + (t - kx[i]) / (kx[i + 1] - kx[i]) * (ky[i + 1] - ky[i])

    times = [t * 0.5 for t in range(361)]
    d = diagnose(_series(drift, times), _bars(91), _beats(361))

    assert d.classification == "local_tempo_mismatch"
    assert d.jumps == []                                   # gradual, never a jump
    segs = d.segments
    # Not one averaged correction, and not a dozen fragments.
    assert 2 <= len(segs) <= 4, [(s.kind, s.start_chart, s.end_chart) for s in segs]
    assert all(s.kind == "drift" for s in segs)            # nothing here is in sync
    # The rate genuinely increases, so later corrections are stronger.
    assert segs[0].slope < segs[-1].slope
    assert segs[-1].recommended_bpm < segs[0].recommended_bpm < 120.0
    # Every correction is expressed on real measures, in order.
    assert segs[0].start_measure == 1
    assert all(s.end_measure >= s.start_measure for s in segs)
    assert d.first_divergence_s == pytest.approx(0.0, abs=1.0)


def _irregular(limit: float = 120.0, seed: int = 11) -> list[float]:
    """A non-periodic rhythm. Real music is not a uniform grid, and uniformity
    makes jumps genuinely undetectable (a shift of a whole number of grid steps
    produces an identical attack set), so realistic tests must be irregular."""
    import random

    rng = random.Random(seed)
    out, t = [], 0.0
    while t < limit:
        out.append(round(t, 4))
        t += rng.choice([0.25, 0.25, 0.5, 0.5, 0.75, 1.0])
    return out


def test_correspondence_reacquires_after_a_real_jump() -> None:
    """A jump moves the recording far outside the matching window, so plain
    predict-and-snap stops matching and coasts — the residual never steps and the
    jump becomes invisible, which is the one thing this analysis exists to find.
    Re-acquisition must find the displaced music, recover the true step, and
    place it where the music actually moved."""
    chart = _irregular()
    bars = [i * 2.0 for i in range(61)]
    for shift in (1.7, 2.0, 3.5):
        rec = [c if c < 60.0 else c + shift for c in chart]
        d = diagnose(build_correspondence(chart, rec, chart_start=0.0, rec_start=0.0),
                     bars, chart)
        assert d.classification == "sudden_offset", (shift, d.classification)
        assert len(d.jumps) == 1, (shift, d.jumps)
        assert d.jumps[0].step_s == pytest.approx(shift, abs=0.15)
        assert d.jumps[0].chart_time == pytest.approx(60.0, abs=3.0)


def test_a_grid_aligned_shift_is_honestly_reported_as_in_sync() -> None:
    """On a uniform grid, shifting by a whole number of steps leaves the attacks
    exactly where the chart expects them: the music really does line up, only
    some notes have no partner. Claiming a jump there would be an invention."""
    chart = [0.5 * i for i in range(240)]
    rec = [t if t < 60.0 else t + 1.5 for t in chart]     # 1.5s == 3 grid steps
    d = diagnose(build_correspondence(chart, rec, chart_start=0.0, rec_start=0.0),
                 [i * 2.0 for i in range(60)], chart)
    assert d.classification == "in_sync"
    assert d.jumps == []


def test_reacquisition_does_not_invent_a_jump_in_a_clean_song() -> None:
    """The wide re-acquisition search must not fire on music that is simply
    sparse or has a rest — no jump may appear where none exists."""
    chart = _irregular(seed=3)
    rec = list(chart)
    d = diagnose(build_correspondence(chart, rec, chart_start=0.0, rec_start=0.0),
                 [i * 2.0 for i in range(61)], chart)
    assert d.classification == "in_sync"
    assert d.jumps == []
