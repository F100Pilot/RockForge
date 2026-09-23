"""The librosa measurements, as functions AND as a standalone script.

librosa is the one ML stage RockForge did NOT already run out-of-process:
Demucs, WhisperX and Banquet are all subprocesses, but tone analysis, the
per-point tempo ("Corrigir daqui") and the tuning proposal imported librosa
directly. That is what kept them out of the standalone `.exe`, which has its
own Python and can never import the user's packages.

So this module is written to be usable **both ways**, with one implementation
of each measurement:

- imported and called directly, when the running process has librosa
  (``start.bat``) — no subprocess cost on a per-click tool;
- executed as a script by another interpreter (``ml_python.run_json``), when it
  does not (the `.exe`).

It therefore imports NOTHING from ``rockforge`` — same rule as
``_whisperx_runner.py`` and ``_demucs_patcher.py``, and the reason it can be
run by an interpreter that has librosa but has never heard of RockForge.

Each function returns plain floats (a JSON-able dict for the tone features), so
the two transports cannot disagree about anything but the transport.
"""

from __future__ import annotations

import argparse
import json
import sys


def tempo_from(audio: str, start_s: float, expected_bpm: float | None = None) -> float:
    """Estimate the recording's tempo (BPM) from ``start_s`` to the end.

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

    y, sr = librosa.load(audio, sr=None, mono=True, offset=max(0.0, start_s))
    if len(y) == 0:
        raise ValueError("no audio after the requested start point")
    kwargs = {"start_bpm": float(expected_bpm)} if expected_bpm and expected_bpm > 0 else {}
    tempo, _ = librosa.beat.beat_track(y=y, sr=sr, **kwargs)
    return float(np.atleast_1d(tempo)[0])


def tuning_cents(audio: str) -> float:
    """The recording's reference-pitch deviation from A440, in cents."""
    import librosa

    y, sr = librosa.load(audio, sr=None, mono=True)
    return float(librosa.estimate_tuning(y=y, sr=sr)) * 100.0


def tone_features(audio: str) -> dict[str, float]:
    """The spectral features a guitar tone is classified from.

    Only the MEASUREMENT lives here; mapping these to a ``ToneProfile`` is pure
    and stays in ``tone_analysis/analyzer.py`` where CI can test it without an
    ML stack.
    """
    import librosa
    import numpy as np

    y, sr = librosa.load(audio, sr=None, mono=True)
    if len(y) == 0:
        raise ValueError("empty audio file")

    # Peak-normalize so the thresholds below are independent of how loud the
    # stem happens to be (Demucs output level varies wildly).
    peak = float(np.max(np.abs(y)))
    if peak > 0:
        y = y / peak

    rms = librosa.feature.rms(y=y)[0]
    zcr = librosa.feature.zero_crossing_rate(y=y)[0]
    centroid = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
    contrast = librosa.feature.spectral_contrast(y=y, sr=sr)
    rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr, roll_percent=0.85)[0]
    flatness = librosa.feature.spectral_flatness(y=y)[0]

    # Align frame counts (features can differ by one frame) then keep only the
    # frames where the guitar is actually playing — above 30% of the peak RMS —
    # so silence, count-ins and clean breaks don't pull the estimate toward clean.
    n = min(len(rms), len(zcr), len(centroid), len(rolloff), len(flatness), contrast.shape[1])
    rms, zcr = rms[:n], zcr[:n]
    centroid, rolloff, flatness = centroid[:n], rolloff[:n], flatness[:n]
    contrast = contrast[:, :n]

    peak_rms = float(np.max(rms)) if n else 0.0
    active = rms >= 0.3 * peak_rms if peak_rms > 0 else np.ones(n, dtype=bool)
    if not bool(active.any()):
        active = np.ones(n, dtype=bool)

    act_rms = rms[active]
    mean_rms = float(np.mean(act_rms))
    return {
        "zcr": float(np.mean(zcr[active])),
        "centroid": float(np.mean(centroid[active])),
        "contrast": float(np.mean(contrast[:, active])),
        "rolloff": float(np.mean(rolloff[active])),
        "flatness": float(np.mean(flatness[active])),
        # Crest factor over the active region: clean, transient picking keeps
        # peaks well above the average (~3-6); heavy distortion sustains and
        # compresses it toward ~1.5-2.5. Low crest ⇒ compressed ⇒ distorted.
        "crest": float(np.max(act_rms)) / (mean_rms + 1e-8),
        "rms_std_ratio": float(np.std(act_rms)) / (mean_rms + 1e-8),
    }


def main(argv: list[str] | None = None) -> int:
    """Print ONE line of JSON on stdout. ``ml_python.run_json`` reads the last
    line, so librosa's own warnings on stderr (or a chatty backend on stdout)
    cannot corrupt the answer."""
    parser = argparse.ArgumentParser(description="librosa measurements for RockForge")
    parser.add_argument("command", choices=("tempo", "tuning", "tone"))
    parser.add_argument("--audio", required=True)
    parser.add_argument("--start", type=float, default=0.0)
    parser.add_argument("--expected-bpm", type=float, default=0.0)
    args = parser.parse_args(argv)

    if args.command == "tempo":
        result: dict[str, object] = {
            "bpm": tempo_from(args.audio, args.start, args.expected_bpm or None)
        }
    elif args.command == "tuning":
        result = {"cents": tuning_cents(args.audio)}
    else:
        result = {"features": tone_features(args.audio)}
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
