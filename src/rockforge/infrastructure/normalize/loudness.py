"""Loudness measurement + Wwise volume calculation (DLC Builder "Calculate Volumes").

Rocksmith plays the song audio at a Wwise bus volume (dB) baked into the ``.bnk``
Sound object. DLC Builder's "Calculate Volumes" measures the audio's loudness and
picks that volume so every song sits at a consistent level; RockForge shipped a
neutral ``0.0`` instead.

The recording itself is NOT reprocessed (``normalize/ffmpeg.py``): it gets a
LINEAR gain toward the configurable target (``runtime_settings.loudness_target()``,
default -12 LUFS), capped so its true peak stays under ``PEAK_CEILING_DBTP``
(:func:`recording_gain_db`), and the Wwise bus volume measured here makes up
whatever that ceiling held back. That is DLC Builder's approach (it never
touches the audio and sets the volume to ``-16 - loudness``); the single-pass
``loudnorm`` used before reshaped every song with a moving gain and a limiter.
The song-select **preview**, a trimmed clip with its own loudness, is measured
separately so it matches.

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

# Fallback loudness/volume target. The EFFECTIVE target is the user-configurable
# one from ``runtime_settings.loudness_target()`` (default -12 LUFS) — a louder,
# music-game level than the -16 broadcast reference, which read too quiet next to
# retail Rocksmith DLC (its masters are loud; DLC Builder's Calculate Volumes
# attenuates ~-3/-4 dB). ``calculate_volume`` resolves the runtime value; this
# constant is only the pure default for :func:`volume_for_loudness`.
TARGET_LUFS = -12.0
# Never boost or cut more than this — a boost beyond the .wem's headroom would
# clip; a huge cut would bury a genuinely quiet mix.
VOLUME_CLAMP_DB = 8.0
LOUDNESS_TIMEOUT_S = 600

_EBUR128_I = re.compile(r"I:\s*(-?\d+(?:\.\d+)?)\s*LUFS")
# The summary's "True peak:" block ("Peak:  0.5 dBFS"); -inf for digital silence.
_EBUR128_TP = re.compile(r"True peak:\s*\n\s*Peak:\s*(-?(?:\d+(?:\.\d+)?|inf))\s*dBFS")


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


def parse_ebur128_true_peak(stderr: str) -> float | None:
    """The true peak (dBFS) from ffmpeg ``ebur128=peak=true`` stderr, or None."""
    matches = _EBUR128_TP.findall(stderr)
    if not matches:
        return None
    return float("-inf") if matches[-1] == "-inf" else float(matches[-1])


def measure_levels(
    audio: Path, ffmpeg: str = "ffmpeg", start_s: float = 0.0
) -> tuple[float | None, float | None]:
    """``(integrated loudness LUFS, true peak dBFS)`` of ``audio`` from ``start_s``
    in one ffmpeg pass; ``(None, None)`` when it cannot be measured."""
    try:
        proc = subprocess.run(
            [
                ffmpeg, "-nostdin",
                *(["-ss", str(start_s)] if start_s > 0 else []),
                "-i", str(audio), "-af", "ebur128=peak=true", "-f", "null", "-",
            ],
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
            timeout=LOUDNESS_TIMEOUT_S,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None, None
    return parse_ebur128_i(proc.stderr), parse_ebur128_true_peak(proc.stderr)


#: The loudest a sample may end up after the linear gain (true peak, dBFS): room
#: for the Vorbis encode's own overshoot, like the -1.5 the limiter used to target.
PEAK_CEILING_DBTP = -1.0


def recording_gain_db(
    loudness: float | None, true_peak: float | None, target: float = TARGET_LUFS
) -> float:
    """The LINEAR gain (dB) to apply to the recording itself. Pure.

    Toward ``target``, but never so much that the true peak passes
    :data:`PEAK_CEILING_DBTP` — which also pulls a master whose peaks are already
    over 0 dBFS back under it before it is written as 16-bit PCM (where an over
    is simply cut off). Whatever the ceiling holds back is left to the Wwise
    volume (:func:`calculate_volume` measures the result). 0 when unknown."""
    if loudness is None or loudness == float("-inf"):
        return 0.0
    gain = target - loudness
    if true_peak is not None and true_peak != float("-inf"):
        gain = min(gain, PEAK_CEILING_DBTP - true_peak)
    return round(gain, 2)


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
    audio: Path, ffmpeg: str = "ffmpeg", target: float | None = None
) -> float:
    """The Wwise bus volume (dB) for ``audio`` — measure its loudness and offset
    it to ``target`` (the runtime loudness target when unset, so it stays in step
    with the normalization). ``0.0`` when measurement is unavailable."""
    if target is None:
        from rockforge import runtime_settings

        target = runtime_settings.loudness_target()
    return volume_for_loudness(measure_loudness_lufs(audio, ffmpeg), target)
