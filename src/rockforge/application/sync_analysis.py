"""Diagnose HOW a Guitar Pro chart is out of sync with its recording.

The existing aligners (``align_chart_to_recording``, ``align_bars_to_downbeats``)
answer "where should each note go"; they emit a corrected timeline but never say
*what kind* of problem they were correcting. That distinction is what decides the
right fix, and getting it wrong makes things worse:

- **Progressive drift** — the residual grows steadily: the chart's tempo differs
  slightly from the recording's. Fixing it means changing the BPM *of that span*.
- **A sudden jump** — the residual steps: a bar too many/few, a missing rest, a
  repeat the parser did not expand. Changing the BPM here is actively wrong; it
  smears a local error across music that was already correct. The fix is a shift
  at one point (or an edit to the tab).
- **A structural mismatch** — the chart's notes simply do not correspond to the
  audio there. No time warp can fix content.

Everything below derives from ONE primitive: the correspondence series, i.e. the
pairs (chart_time, audio_time) where a chart note onset was matched to a real
attack in the recording. Its residual ``d(t) = audio − chart`` is the drift
curve; segmenting that curve is the whole diagnosis.

Pure and dependency-free (no audio, no I/O) so it is unit-testable without the
ml extra: callers pass in onsets already detected by the infrastructure adapters.
"""

from __future__ import annotations

import bisect
from dataclasses import dataclass

# A note lands "on time" for a rhythm game within a few tens of ms; below this a
# span is called synced rather than drifting.
NEGLIGIBLE_DRIFT_S = 0.05
# A residual step this large that happens within JUMP_MAX_GAP_S of chart time
# cannot be gradual drift at any plausible tempo error — it is a discontinuity.
JUMP_MIN_STEP_S = 0.12
JUMP_MAX_GAP_S = 1.5
# Minimum chart seconds a drift segment must span to be worth reporting (a
# correction over a couple of seconds is noise, not a tempo error).
MIN_SEGMENT_S = 12.0
# Drift RATE below which a span counts as in sync. Classifying on a segment's
# own total instead would hide a long gentle drift: chop a 0.3 s/minute slide
# into 8-second pieces and every piece looks synced while the song ends a second
# out. This is the rate that accumulates a negligible error over ~30 s of music.
NEGLIGIBLE_SLOPE = NEGLIGIBLE_DRIFT_S / 30.0
# Fraction of nearby chart onsets that must have matched a real attack for a
# span to be trusted; below this the tab likely does not correspond to the audio.
MIN_CONFIDENCE = 0.5
# Re-acquisition after the match is lost. A real jump moves the recording by far
# more than the matching window, so predict-and-snap simply stops matching and
# coasts — the residual never steps and the jump becomes invisible, which is the
# one thing this analysis exists to find. After this many consecutive misses we
# search much wider for a shift that re-explains the music.
# Judged over a WINDOW, not as a consecutive run: after a jump an irregular
# rhythm still throws the odd coincidental match, and a run counter that resets
# on each of those only recovers tens of seconds later — which would report the
# jump far from where it happened.
REACQUIRE_WINDOW = 8
REACQUIRE_AFTER = 4
# How far a jump may move the recording, and how many upcoming onsets must agree
# before a shift is believed (one note could match by luck; several cannot).
REACQUIRE_MAX_SHIFT_S = 10.0
REACQUIRE_HORIZON = 10
REACQUIRE_MIN_SUPPORT = 4


@dataclass(frozen=True)
class SyncPoint:
    """One chart onset and where it actually sounds in the recording."""

    chart_time: float
    audio_time: float
    matched: bool  # False = predicted (no real attack found), not evidence

    @property
    def residual(self) -> float:
        """Seconds the recording runs LATE relative to the chart (+ = chart early)."""
        return self.audio_time - self.chart_time


@dataclass(frozen=True)
class DriftSegment:
    """A span of the song sharing one tempo relationship to the recording."""

    kind: str  # "synced" | "drift" | "structural"
    start_chart: float
    end_chart: float
    start_measure: int
    end_measure: int
    drift_start_s: float
    drift_end_s: float
    slope: float  # seconds of drift gained per chart second
    tempo_ratio: float  # recording seconds per chart second (1.0 = in step)
    original_bpm: float
    recommended_bpm: float
    confidence: float


@dataclass(frozen=True)
class SyncJump:
    """A step discontinuity — a structural difference, NOT a tempo error."""

    chart_time: float
    measure: int
    step_s: float  # + = the recording is suddenly later than the chart expects
    confidence: float


@dataclass(frozen=True)
class SyncDiagnosis:
    points: list[SyncPoint]
    segments: list[DriftSegment]
    jumps: list[SyncJump]
    classification: str  # see _classify
    confidence: float
    first_divergence_s: float | None  # chart time where sync is first lost
    warnings: list[str]


def _theil_sen(pts: list[tuple[float, float]]) -> float:
    """Median pairwise slope — robust to the outliers a mis-snapped onset makes."""
    n = len(pts)
    if n < 2:
        return 0.0
    # Cap the pair count: the median of a large uniform sample of pairs is a fine
    # stand-in for all of them, and this keeps a long song from going quadratic.
    step = 1 if n <= 60 else n // 60
    slopes = [
        (pts[j][1] - pts[i][1]) / (pts[j][0] - pts[i][0])
        for i in range(0, n, step)
        for j in range(i + 1, n, step)
        if pts[j][0] - pts[i][0] > 1e-6
    ]
    return sorted(slopes)[len(slopes) // 2] if slopes else 0.0


def _median(xs: list[float]) -> float:
    return sorted(xs)[len(xs) // 2] if xs else 0.0


def _reacquire(
    upcoming: list[float],
    ro: list[float],
    r_pred: float,
    rho: float,
    win: float,
) -> float | None:
    """Find the time shift that makes the music line up again after a lost match.

    Not a single-note snap: each real attack near the prediction proposes a
    candidate shift, and a candidate is only believed when it also explains
    several of the NEXT chart onsets. One note can match by luck; a run cannot.
    Ties go to the smallest shift, so a genuine small gap is never explained away
    as a large one.
    """
    if not upcoming or not ro:
        return None
    lo = bisect.bisect_left(ro, r_pred - REACQUIRE_MAX_SHIFT_S)
    hi = bisect.bisect_right(ro, r_pred + REACQUIRE_MAX_SHIFT_S)
    c0 = upcoming[0]
    best: tuple[int, float] | None = None
    for a in ro[lo:hi]:
        shift = a - r_pred
        support = 0
        for c in upcoming[:REACQUIRE_HORIZON]:
            pred = r_pred + shift + rho * (c - c0)
            i = bisect.bisect_left(ro, pred)
            if any(
                0 <= j < len(ro) and abs(ro[j] - pred) <= win for j in (i - 1, i)
            ):
                support += 1
        if support >= REACQUIRE_MIN_SUPPORT and (
            best is None or support > best[0] or (support == best[0] and abs(shift) < abs(best[1]))
        ):
            best = (support, shift)
    return best[1] if best else None


def build_correspondence(
    chart_onsets: list[float],
    rec_onsets: list[float],
    *,
    chart_start: float,
    rec_start: float,
    win: float = 0.12,
    rho_min: float = 0.75,
    rho_max: float = 1.30,
) -> list[SyncPoint]:
    """Match each chart note onset to the real attack it should sound at.

    Same predict-and-snap idea the dynamic aligner uses: each onset is predicted
    into the recording at a running tempo ratio and snapped to the nearest real
    attack within ``win``. Unlike the aligner this keeps EVERY point (matched or
    not) and does not decimate to anchors — the diagnosis needs the raw evidence.
    """
    co = sorted(t for t in chart_onsets if t >= chart_start - 1e-9)
    ro = sorted(rec_onsets)
    if not co or not ro:
        return []
    out: list[SyncPoint] = []
    last_c, last_r, rho = chart_start, rec_start, 1.0
    recent: list[tuple[float, float]] = []
    recent_ok: list[bool] = []
    lost_at = 0
    for idx, c in enumerate(co):
        if len(recent_ok) > REACQUIRE_WINDOW:
            recent_ok.pop(0)
        r_pred = last_r + rho * (c - last_c)
        i = bisect.bisect_left(ro, r_pred)
        cand = [ro[j] for j in (i - 1, i) if 0 <= j < len(ro) and abs(ro[j] - r_pred) <= win]
        if cand:
            r_val = min(cand, key=lambda x: abs(x - r_pred))
            if not recent_ok or recent_ok[-1]:
                lost_at = len(out) + 1  # a clean run; nothing to back-fill from
            recent_ok.append(True)
            out.append(SyncPoint(chart_time=c, audio_time=r_val, matched=True))
            recent.append((c, r_val))
            if len(recent) > 12:
                recent.pop(0)
            if len(recent) >= 4:
                rho = max(rho_min, min(rho_max, 0.75 * rho + 0.25 * _theil_sen(recent)))
        else:
            recent_ok.append(False)
            r_val = r_pred
            if sum(1 for ok in recent_ok if not ok) >= REACQUIRE_AFTER:
                shift = _reacquire(co[idx:], ro, r_pred, rho, win)
                if shift is not None:
                    # The music was found again, displaced. Back-fill the points
                    # since the match was lost: any of them that DOES line up
                    # under the recovered shift already belonged after the jump,
                    # so the residual steps where the music actually moved rather
                    # than where we happened to notice.
                    for j in range(lost_at, len(out)):
                        cand_t = out[j].audio_time + shift
                        k = bisect.bisect_left(ro, cand_t)
                        hit = [
                            ro[m] for m in (k - 1, k)
                            if 0 <= m < len(ro) and abs(ro[m] - cand_t) <= win
                        ]
                        if hit:
                            out[j] = SyncPoint(
                                chart_time=out[j].chart_time,
                                audio_time=min(hit, key=lambda x: abs(x - cand_t)),
                                matched=True,
                            )
                    r_val = r_pred + shift
                    recent_ok.clear()
                    recent.clear()
                    lost_at = len(out) + 1
                    out.append(SyncPoint(chart_time=c, audio_time=r_val, matched=True))
                    last_c, last_r = c, r_val
                    continue
            out.append(SyncPoint(chart_time=c, audio_time=r_val, matched=False))
        last_c, last_r = c, r_val
    return out


def _split_on_jumps(pts: list[SyncPoint]) -> tuple[list[list[SyncPoint]], list[int]]:
    """Cut the series where the residual steps. Returns (pieces, jump indices)."""
    pieces: list[list[SyncPoint]] = []
    jumps: list[int] = []
    cur: list[SyncPoint] = []
    for i, p in enumerate(pts):
        if cur:
            prev = cur[-1]
            dc = p.chart_time - prev.chart_time
            dd = p.residual - prev.residual
            if abs(dd) >= JUMP_MIN_STEP_S and 0 < dc <= JUMP_MAX_GAP_S:
                pieces.append(cur)
                jumps.append(i)
                cur = []
        cur.append(p)
    if cur:
        pieces.append(cur)
    return pieces, jumps


def _segment_piece(pts: list[SyncPoint], depth: int = 0) -> list[list[SyncPoint]]:
    """Recursively split a piece where one straight line does not describe it."""
    if depth >= 4 or len(pts) < 6:
        return [pts]
    span = pts[-1].chart_time - pts[0].chart_time
    if span < 2 * MIN_SEGMENT_S:
        return [pts]
    xy = [(p.chart_time, p.residual) for p in pts]
    slope = _theil_sen(xy)
    inter = _median([y - slope * x for x, y in xy])
    # Worst deviation from the fitted line, ignoring the ends (where a split
    # cannot help) and only where both halves would still be long enough.
    worst_i, worst = -1, 0.0
    for i, (x, y) in enumerate(xy):
        if x - xy[0][0] < MIN_SEGMENT_S or xy[-1][0] - x < MIN_SEGMENT_S:
            continue
        err = abs(y - (slope * x + inter))
        if err > worst:
            worst_i, worst = i, err
    if worst_i < 0 or worst < NEGLIGIBLE_DRIFT_S * 2:
        return [pts]
    return _segment_piece(pts[:worst_i], depth + 1) + _segment_piece(pts[worst_i:], depth + 1)


def _merge_similar(groups: list[list[SyncPoint]]) -> list[list[SyncPoint]]:
    """Join neighbouring groups that describe the SAME tempo relationship.

    The recursive split is deliberately eager (it must not miss a real change of
    slope), which chops a smoothly drifting passage into several pieces telling
    the same story. Reporting those as separate corrections would be noise, so
    adjacent groups whose slopes agree — within a tolerance that scales with the
    slope itself — are put back together.
    """
    if len(groups) < 2:
        return groups
    out = [groups[0]]
    for g in groups[1:]:
        prev = out[-1]
        s_prev = _theil_sen([(p.chart_time, p.residual) for p in prev])
        s_cur = _theil_sen([(p.chart_time, p.residual) for p in g])
        tol = max(NEGLIGIBLE_SLOPE, 0.25 * max(abs(s_prev), abs(s_cur)))
        if abs(s_prev - s_cur) <= tol:
            out[-1] = prev + g
        else:
            out.append(g)
    return out


def _measure_of(bars: list[float], t: float) -> int:
    """1-based measure containing chart time ``t`` (0 when unknown)."""
    if not bars:
        return 0
    i = bisect.bisect_right(bars, t + 1e-6)
    return max(1, min(len(bars), i))


def _authored_bpm(bars: list[float], beats: list[float], a: float, b: float) -> float:
    """The chart's own BPM over [a, b], from its beat grid (honours tempo changes)."""
    grid = beats or bars
    inside = [t for t in grid if a - 1e-6 <= t <= b + 1e-6]
    if len(inside) < 2:
        return 0.0
    span = inside[-1] - inside[0]
    return round((len(inside) - 1) * 60.0 / span, 3) if span > 1e-6 else 0.0


def _confidence(pts: list[SyncPoint]) -> float:
    return sum(1 for p in pts if p.matched) / len(pts) if pts else 0.0


def _classify(segments: list[DriftSegment], jumps: list[SyncJump]) -> str:
    """Overall label, mirroring the categories a user has to act on."""
    if any(s.kind == "structural" for s in segments):
        return "structural_mismatch"
    drifting = [s for s in segments if s.kind == "drift"]
    if jumps and drifting:
        return "mixed"
    if jumps:
        return "sudden_offset"
    if not drifting:
        return "in_sync"
    if len(drifting) == 1 and len(segments) == 1:
        return "global_tempo_mismatch"
    return "local_tempo_mismatch"


def diagnose(
    points: list[SyncPoint],
    bars: list[float],
    beats: list[float] | None = None,
    *,
    warnings: list[str] | None = None,
) -> SyncDiagnosis:
    """Classify how the chart diverges from the recording and what would fix it.

    ``bars``/``beats`` are the chart's own measure downbeats and beat grid (chart
    seconds), used to express each finding in measures and to read the authored
    BPM of a span — so a recommendation respects tempo changes already in the file.
    """
    warns = list(warnings or [])
    if len(points) < 4:
        return SyncDiagnosis(
            points=points, segments=[], jumps=[],
            classification="insufficient_data", confidence=0.0,
            first_divergence_s=None,
            warnings=[*warns, "not enough matched onsets to analyse the synchronisation"],
        )

    pieces, jump_idx = _split_on_jumps(points)
    jumps: list[SyncJump] = []
    for i in jump_idx:
        prev, cur = points[i - 1], points[i]
        jumps.append(SyncJump(
            chart_time=cur.chart_time,
            measure=_measure_of(bars, cur.chart_time),
            step_s=round(cur.residual - prev.residual, 4),
            confidence=_confidence(points[max(0, i - 8):i + 8]),
        ))

    segments: list[DriftSegment] = []
    for piece in pieces:
        for seg in _merge_similar(_segment_piece(piece)):
            if len(seg) < 2:
                continue
            a, b = seg[0].chart_time, seg[-1].chart_time
            xy = [(p.chart_time, p.residual) for p in seg]
            slope = _theil_sen(xy)
            conf = _confidence(seg)
            total = slope * (b - a)
            if conf < MIN_CONFIDENCE:
                kind = "structural"
            elif abs(slope) < NEGLIGIBLE_SLOPE and abs(total) < NEGLIGIBLE_DRIFT_S:
                kind = "synced"
            else:
                kind = "drift"
            ratio = 1.0 + slope
            bpm = _authored_bpm(bars, beats or [], a, b)
            segments.append(DriftSegment(
                kind=kind,
                start_chart=round(a, 4), end_chart=round(b, 4),
                start_measure=_measure_of(bars, a), end_measure=_measure_of(bars, b),
                drift_start_s=round(seg[0].residual, 4),
                drift_end_s=round(seg[-1].residual, 4),
                slope=round(slope, 6),
                tempo_ratio=round(ratio, 6),
                original_bpm=bpm,
                # The chart is too fast when the residual grows, so the real tempo
                # is the authored one divided by the ratio.
                recommended_bpm=round(bpm / ratio, 3) if bpm and ratio > 1e-6 else 0.0,
                confidence=round(conf, 3),
            ))

    first_div: float | None = None
    for s in segments:
        if s.kind != "synced":
            first_div = s.start_chart
            break
    if jumps and (first_div is None or jumps[0].chart_time < first_div):
        first_div = jumps[0].chart_time

    overall = _classify(segments, jumps)
    conf = _confidence(points)
    return SyncDiagnosis(
        points=points, segments=segments, jumps=jumps,
        classification=overall, confidence=round(conf, 3),
        first_divergence_s=first_div, warnings=warns,
    )
