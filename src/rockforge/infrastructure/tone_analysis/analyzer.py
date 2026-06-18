"""Spectral analysis of a guitar stem to classify tone character.

Extracts features from the separated guitar audio and maps them to broad
tone categories (clean, crunch, high-gain) using spectral heuristics.
librosa is imported lazily (ml extra).

Honesty note: this does NOT identify the actual amp/pedal used in the
recording — it classifies the *character* of the guitar sound and
suggests a plausible Rocksmith gear preset. The user reviews and adjusts.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ToneProfile:
    """Spectral characteristics of a guitar audio segment."""

    gain_level: float
    brightness: float
    low_end: float
    dynamic_range: float

    @property
    def category(self) -> str:
        if self.gain_level < 0.25:
            return "clean"
        if self.gain_level < 0.55:
            return "crunch"
        return "high_gain"


def analyze_guitar_tone(audio: Path) -> ToneProfile:
    """Classify the tone character of a guitar audio file.

    Returns a ToneProfile with normalized 0-1 features derived from
    spectral analysis. librosa imported lazily (ml extra).
    """
    import librosa
    import numpy as np

    y, sr = librosa.load(str(audio), sr=None, mono=True)
    if len(y) == 0:
        raise ValueError("empty audio file")

    rms = librosa.feature.rms(y=y)[0]
    zcr = librosa.feature.zero_crossing_rate(y=y)[0]
    centroid = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
    contrast = librosa.feature.spectral_contrast(y=y, sr=sr)
    rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr, roll_percent=0.85)[0]

    mean_zcr = float(np.mean(zcr))
    mean_centroid = float(np.mean(centroid))
    mean_rms = float(np.mean(rms))
    std_rms = float(np.std(rms))
    mean_contrast = float(np.mean(contrast))
    mean_rolloff = float(np.mean(rolloff))

    # Gain estimation: combine zero-crossing rate (distortion makes it high)
    # with inverse spectral contrast (distorted signals are spectrally flat).
    # ZCR of clean guitar ~0.02-0.06; high-gain ~0.08-0.20+.
    zcr_norm = min(1.0, max(0.0, (mean_zcr - 0.02) / 0.16))
    # Spectral contrast: clean guitar has high contrast (~30-50 dB across bands);
    # distorted has low contrast (~5-15 dB). Invert and normalize.
    contrast_norm = min(1.0, max(0.0, 1.0 - (mean_contrast - 5.0) / 40.0))
    gain_level = 0.6 * zcr_norm + 0.4 * contrast_norm

    # Brightness: spectral centroid normalized. Guitar centroid typically
    # 1000-6000 Hz; higher = brighter/more treble.
    brightness = min(1.0, max(0.0, (mean_centroid - 1000.0) / 4000.0))

    # Low-end: inverse of rolloff position. Low rolloff = more bass content.
    low_end = min(1.0, max(0.0, 1.0 - (mean_rolloff - 2000.0) / 8000.0))

    # Dynamic range: ratio of RMS std to mean. High = dynamic (clean);
    # low = compressed (distorted).
    dynamic_range = min(1.0, max(0.0, (std_rms / (mean_rms + 1e-8))))

    return ToneProfile(
        gain_level=round(gain_level, 3),
        brightness=round(brightness, 3),
        low_end=round(low_end, 3),
        dynamic_range=round(dynamic_range, 3),
    )
