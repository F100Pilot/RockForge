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

import json
import os
import tempfile
from pathlib import Path

from rockforge.infrastructure import _librosa_runner, ml_python


def detect_tempo_from(audio: Path, start_s: float, expected_bpm: float | None = None) -> float:
    """Estimate the recording's tempo (BPM) from ``start_s`` to the end.

    Used by the per-point "new beat" tool: the user clicks where the chart drifts
    out of the recording and we re-tempo the following notes to the local BPM
    measured from that instant.

    The measurement itself lives in ``_librosa_runner`` so it has ONE
    implementation reachable two ways: called directly here when this process
    has librosa, and run by the configured ML interpreter when it does not (the
    standalone `.exe` — see ``infrastructure/ml_python.py``). The in-process
    path is kept because this is a per-click tool: paying an interpreter start
    and a librosa import on every click would make the workflow unusable.
    """
    if ml_python.librosa_here():
        return _librosa_runner.tempo_from(str(audio), start_s, expected_bpm)
    result = ml_python.run_librosa(
        "tempo", audio, start=start_s, expected_bpm=expected_bpm or 0.0
    )
    return float(result["bpm"])


def align_to_recording(audio: Path, beats: list[float], notes: list[float]) -> dict[str, object]:
    """EXPERIMENTAL — the chart's beats moved to where the recording plays
    them (``_librosa_runner.align_beats``), for the viewer's "Sincronizar
    automaticamente" card. ``beats``/``notes`` are seconds of the recording as
    the chart shows them now. The envelope needs librosa; the alignment itself
    is plain Python, and both run wherever librosa is (here, or the configured
    ML interpreter, given the long lists through a JSON file)."""
    if ml_python.librosa_here():
        env, hop = _librosa_runner.onset_envelope(str(audio))
        result = _librosa_runner.align_beats(env, hop, beats, notes)
        result["duration"] = round(len(env) * hop, 3)
        return result
    fd, spec = tempfile.mkstemp(prefix="rf-beatalign-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump({"beats": beats, "notes": notes}, fh)
        runner = ml_python.runner_path(
            Path(_librosa_runner.__file__).resolve().parent, "_librosa_runner.py"
        )
        return ml_python.run_json(runner, ["beatalign", "--audio", str(audio), "--spec", spec])
    finally:
        Path(spec).unlink(missing_ok=True)


def detect_attacks(audio: Path) -> dict[str, object]:
    """Where the recording has attacks (``_librosa_runner.attacks``), for the
    score's "Ataques da gravação" lane: ``{"attacks": [[time, strength], …],
    "duration": seconds}``, in the clock of ``audio``."""
    if ml_python.librosa_here():
        return _librosa_runner.attacks(str(audio))
    return ml_python.run_librosa("attacks", audio)


def estimate_tuning_cents(audio: Path) -> float:
    """Estimate the recording's reference-pitch deviation from A440, in cents.

    Standalone (not a port method) so the GP-sync API can call it directly for
    the auto-tuning proposal, and tests can monkeypatch it without librosa
    installed. This is the only part of tuning detection that is reliable from
    polyphonic audio (see module docstring) — string/drop tuning is NOT
    detected and must come from the GP file or human confirmation.
    """
    if ml_python.librosa_here():
        return _librosa_runner.tuning_cents(str(audio))
    return float(ml_python.run_librosa("tuning", audio)["cents"])
