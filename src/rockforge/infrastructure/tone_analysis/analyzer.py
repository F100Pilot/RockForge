"""Spectral analysis of a guitar stem to classify tone character.

Extracts features from the separated guitar audio and maps them to broad
tone categories (clean, crunch, high-gain) using spectral heuristics.
The librosa half runs through ``_librosa_runner``, so it works both in a
Python install and in the standalone .exe (see ``infrastructure/ml_python``).

Honesty note: this does NOT identify the actual amp/pedal used in the
recording — it classifies the *character* of the guitar sound and
suggests a plausible Rocksmith gear preset. The user reviews and adjusts.

Why the earlier version under-read gain ("usually clean"):
- it averaged over the WHOLE stem, so silences, clean intros and breaks
  dragged the gain estimate down (a mostly-distorted song read as clean);
- it relied on zero-crossing rate and spectral centroid, both dominated by
  *brightness* — a dark, low-tuned or palm-muted high-gain tone reads low on
  both — so heavy music was systematically classified too clean;
- the computed dynamic range was never actually used.

This version measures distortion with brightness-independent cues (spectral
flatness and dynamic compression / crest factor) and computes them only over
the frames where the guitar is actually playing loud.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

from rockforge.infrastructure import _librosa_runner, ml_python


@dataclass(frozen=True)
class ToneProfile:
    """Spectral characteristics of a guitar audio segment (features in 0-1)."""

    gain_level: float
    brightness: float
    low_end: float
    dynamic_range: float
    flatness: float = 0.0  # spectral flatness cue (distortion → higher)
    compression: float = 0.0  # dynamic compression cue (distortion → higher)

    @property
    def category(self) -> str:
        if self.gain_level < 0.25:
            return "clean"
        if self.gain_level < 0.5:
            return "crunch"
        return "high_gain"


def _clamp01(v: float) -> float:
    return min(1.0, max(0.0, v))


# Spectral flatness log-range: ~0.002 (tonal/clean) → ~0.04 (saturated). Raw
# flatness is tiny and spans orders of magnitude, so it is normalized in log10.
_FLAT_LOG_MIN = -2.7  # log10(0.002)
_FLAT_LOG_MAX = -1.4  # log10(0.04)


def analyze_guitar_tone(audio: Path) -> ToneProfile:
    """Classify the tone character of a guitar audio file.

    The librosa MEASUREMENT lives in ``_librosa_runner.tone_features`` (one
    implementation, callable in-process or run by the configured ML
    interpreter — see ``infrastructure/ml_python.py``, which is what lets the
    standalone `.exe` do this at all); mapping the features to a
    :class:`ToneProfile` stays here, pure, so CI can test the calibration
    without an ML stack.
    """
    if ml_python.librosa_here():
        features = _librosa_runner.tone_features(str(audio))
    else:
        features = {
            k: float(v)
            for k, v in dict(ml_python.run_librosa("tone", audio)["features"]).items()
        }
    return profile_from_features(**features)


def profile_from_features(
    *,
    zcr: float,
    centroid: float,
    contrast: float,
    rolloff: float,
    flatness: float,
    crest: float,
    rms_std_ratio: float,
) -> ToneProfile:
    """Map the measured features to a :class:`ToneProfile`. Pure — no librosa.

    Split out of :func:`analyze_guitar_tone` so the weights, thresholds and
    category boundaries can be unit-tested in CI, which has no ML stack: the
    whole calibration used to sit inline in a librosa-importing function and was
    therefore covered by nothing. Same split ``normalize/loudness.py`` already
    uses for ``parse_ebur128_i`` / ``volume_for_loudness``.
    """
    # --- Distortion cues (each 0-1), combined into a gain estimate ---
    # Spectral flatness: a clean note is tonal (sparse harmonics → very low
    # flatness); saturation fills the spectrum. The raw values are tiny and span
    # orders of magnitude (~0.001 clean → ~0.03 distorted), so normalize on a LOG
    # scale — a linear range floored this to 0 for real guitar stems.
    flat_log = math.log10(max(flatness, 1e-6))
    flat_norm = _clamp01((flat_log - _FLAT_LOG_MIN) / (_FLAT_LOG_MAX - _FLAT_LOG_MIN))
    # Spectral contrast (peak-to-valley per band): strong for a clean tone
    # (~25 dB+), flattened by distortion (~10-18 dB). Invert.
    contrast_norm = _clamp01((28.0 - contrast) / 20.0)
    # Compression from the crest factor (brightness-independent) — the most
    # reliable cue in practice, so it carries the most weight.
    compression = _clamp01((3.5 - crest) / 2.0)
    # ZCR still helps for bright overdrive, but weight it low — it under-reads
    # dark/low-tuned high-gain, which was the main source of the "too clean" bias.
    zcr_norm = _clamp01((zcr - 0.03) / 0.14)

    gain_level = _clamp01(
        0.34 * compression + 0.28 * contrast_norm + 0.22 * flat_norm + 0.16 * zcr_norm
    )

    # Brightness: spectral centroid, guitar range ~1-6 kHz.
    brightness = _clamp01((centroid - 1000.0) / 4000.0)
    # Low-end: inverse of the rolloff position (low rolloff = more bass).
    low_end = _clamp01(1.0 - (rolloff - 2000.0) / 8000.0)
    # Dynamic range of the active region (informational; high = dynamic/clean).
    dynamic_range = _clamp01(rms_std_ratio)

    return ToneProfile(
        gain_level=round(gain_level, 3),
        brightness=round(brightness, 3),
        low_end=round(low_end, 3),
        dynamic_range=round(dynamic_range, 3),
        flatness=round(flat_norm, 3),
        compression=round(compression, 3),
    )
