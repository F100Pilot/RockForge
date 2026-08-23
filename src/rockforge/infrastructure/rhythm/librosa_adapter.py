"""Beat/tempo and reference-tuning estimation via librosa (ISC licence).

librosa is deliberately the default: madmom's models are CC BY-NC-SA
(non-commercial) and Essentia is AGPL (docs/research/02-transcription.md §4).
Trade-off accepted: neural trackers (Beat This!, madmom) report better F1.

What remains here backs the two MANUAL tools that ask a direct question about
one point in the recording: "what is the tempo from here?" (the per-point
re-tempo) and "how far from A440 is this?" (the tuning proposal). The
whole-song estimators that used to live here (beat grids, onset series,
average tempo) were removed with the automatic sync features they served —
they were not reliable enough on real material to be worth keeping.

Limitations stated up front:
- time-signature detection is NOT performed (weakest link in the literature).
- estimate_tuning yields the deviation from A440 in cents; it does NOT detect
  drop/open string tunings. String-tuning detection from polyphonic audio has
  no production-grade solution (research §5) — the user must confirm tuning.
"""

from __future__ import annotations

from pathlib import Path


def detect_tempo_from(audio: Path, start_s: float, expected_bpm: float | None = None) -> float:
    """Estimate the recording's tempo (BPM) from ``start_s`` to the end.

    Used by the per-point "new beat" tool: the user clicks where the chart drifts
    out of the recording and we re-tempo the following notes to the local BPM
    measured from that instant. librosa imported lazily (ml extra).

    ``expected_bpm`` is passed to librosa as ``start_bpm``. This matters a lot:
    librosa's estimator weights the autocorrelation peaks by a log-normal prior
    centred on ``start_bpm``, which defaults to **120**. Left at that default the
    prior systematically pulls the answer toward 120 — a song at 70 reads as 140,
    the "always a higher tempo, never a lower one" bias — and the re-tempo then
    compresses the tail and the chart runs fast. The caller already knows what
    the chart plays at the clicked point, so centring the prior there asks the
    narrow question ("is the recording faster or slower than this?") instead of
    the open one librosa answers badly.
    """
    import librosa
    import numpy as np

    y, sr = librosa.load(str(audio), sr=None, mono=True, offset=max(0.0, start_s))
    if len(y) == 0:
        raise ValueError("no audio after the requested start point")
    kwargs = {"start_bpm": float(expected_bpm)} if expected_bpm and expected_bpm > 0 else {}
    tempo, _ = librosa.beat.beat_track(y=y, sr=sr, **kwargs)
    return float(np.atleast_1d(tempo)[0])


def estimate_tuning_cents(audio: Path) -> float:
    """Estimate the recording's reference-pitch deviation from A440, in cents.

    Standalone (not a port method) so the GP-sync API can call it directly for
    the auto-tuning proposal, and tests can monkeypatch it without librosa
    installed. This is the only part of tuning detection that is reliable from
    polyphonic audio (see module docstring) — string/drop tuning is NOT
    detected and must come from the GP file or human confirmation.
    """
    import librosa

    y, sr = librosa.load(str(audio), sr=None, mono=True)
    return float(librosa.estimate_tuning(y=y, sr=sr)) * 100.0
