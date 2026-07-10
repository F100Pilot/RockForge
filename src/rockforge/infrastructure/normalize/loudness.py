"""Loudness measurement + Wwise volume calculation (DLC Builder "Calculate Volumes").

Rocksmith plays the song audio at a Wwise bus volume (dB) baked into the ``.bnk``
Sound object. DLC Builder's "Calculate Volumes" measures the audio's loudness and
picks that volume so every song sits at a consistent level; RockForge shipped a
neutral ``0.0`` instead.

RockForge already loudnorm's the full song to **-16 LUFS** (EBU R128), so a
normalized full song lands near ``0`` dB — matching a DLC Builder bank, which
also ships ``0`` until its own Calculate Volumes runs. The value this adds is
(a) the song-select **preview**, a trimmed clip whose own loudness differs and
would otherwise blast over (or hide under) the song, and (b) correcting
loudnorm's single-pass approximation — both pulled to the same target so the
levels are consistent.

Measurement uses ffmpeg's ``ebur128`` filter (the same ffmpeg the normalizer
already requires); the stderr parse and the volume formula are split out
(:func:`parse_ebur128_i` / :func:`volume_for_loudness`) so they are unit-tested
without ffmpeg. If ffmpeg is missing or the measurement fails, the volume falls
back to ``0.0`` — exactly the previous behaviour, never a crash.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

# The EBU R128 reference RockForge normalizes the full song to. A different,
# louder target (to match retail Rocksmith exactly) is deliberately NOT guessed:
# a decoded DLC Builder bank ships volume 0 (its Calculate Volumes was never run),
# so there is no verified retail figure to calibrate against — bump this if songs
# read too quiet in-game next to official DLC.
TARGET_LUFS = -16.0
# Never boost or cut more than this — a boost beyond the .wem's headroom would
# clip; a huge cut would bury a genuinely quiet mix.
VOLUME_CLAMP_DB = 8.0
LOUDNESS_TIMEOUT_S = 600

_EBUR128_I = re.compile(r"I:\s*(-?\d+(?:\.\d+)?)\s*LUFS")


def parse_ebur128_i(stderr: str) -> float | None:
    """The integrated loudness (``I``, LUFS) from ffmpeg ``ebur128`` stderr.

    ebur128 prints a running ``I:`` per frame and one final ``I:`` in the
    ``Summary`` block; the last match is the whole-file integrated value.
    ``None`` when no ``I:`` line is present (measurement produced nothing)."""
    matches = _EBUR128_I.findall(stderr)
    return float(matches[-1]) if matches else None


def volume_for_loudness(loudness: float | None, target: float = TARGET_LUFS) -> float:
    """Wwise volume (dB) that brings ``loudness`` to ``target``, clamped to
    ``±VOLUME_CLAMP_DB``. ``0.0`` when ``loudness`` is unknown (a safe no-op)."""
    if loudness is None:
        return 0.0
    v = max(-VOLUME_CLAMP_DB, min(VOLUME_CLAMP_DB, target - loudness))
    return round(v, 1)


def measure_loudness_lufs(audio: Path, ffmpeg: str = "ffmpeg") -> float | None:
    """Integrated loudness of ``audio`` (LUFS) via ffmpeg ``ebur128``.

    ``None`` if ffmpeg is missing, times out, or prints no loudness — the caller
    then uses ``0.0`` dB (the previous, uncalibrated behaviour)."""
    try:
        proc = subprocess.run(
            [ffmpeg, "-nostdin", "-i", str(audio), "-af", "ebur128", "-f", "null", "-"],
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
            timeout=LOUDNESS_TIMEOUT_S,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None
    return parse_ebur128_i(proc.stderr)


def calculate_volume(
    audio: Path, ffmpeg: str = "ffmpeg", target: float = TARGET_LUFS
) -> float:
    """The Wwise bus volume (dB) for ``audio`` — measure its loudness and offset
    it to ``target``. ``0.0`` when measurement is unavailable."""
    return volume_for_loudness(measure_loudness_lufs(audio, ffmpeg), target)
