"""Beat/tempo and reference-tuning estimation via librosa (ISC licence).

librosa is deliberately the default: madmom's models are CC BY-NC-SA
(non-commercial) and Essentia is AGPL (docs/research/02-transcription.md §4).
Trade-off accepted: neural trackers (Beat This!, madmom) report better F1.

Limitations stated up front:
- time-signature detection is NOT performed (weakest link in the literature);
  beats_per_measure defaults to 4 and is labelled HEURISTIC in the output.
- estimate_tuning yields the deviation from A440 in cents; it does NOT detect
  drop/open string tunings. String-tuning detection from polyphonic audio has
  no production-grade solution (research §5) — the user must confirm tuning.
"""

from __future__ import annotations

from pathlib import Path

from rockforge.domain.music import Beat, NoteEvent, TempoMap, Tuning

_DROP_D_MIDI = (38, 45, 50, 55, 59, 64)


def detect_tempo_and_onset(audio: Path) -> tuple[float, float]:
    """Estimate (bpm, first_onset_seconds) for automatic GP→recording sync.

    Standalone (not a port method) so the API can call it directly for the
    auto-sync proposal, and tests can monkeypatch it without librosa installed.
    The onset is the first audible attack — used as the proposed offset_s (the
    second the song's first note is heard). librosa imported lazily (ml extra).
    """
    import librosa
    import numpy as np

    y, sr = librosa.load(str(audio), sr=None, mono=True)
    tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
    bpm = float(np.atleast_1d(tempo)[0])
    onsets = librosa.onset.onset_detect(y=y, sr=sr, units="time")
    first_onset = float(onsets[0]) if len(onsets) else 0.0
    return bpm, first_onset


def detect_tempo_from(audio: Path, start_s: float) -> float:
    """Estimate the recording's tempo (BPM) from ``start_s`` to the end.

    Used by the per-point "new beat" tool: the user clicks where the chart drifts
    out of the recording and we re-tempo the following notes to the local BPM
    measured from that instant. librosa imported lazily (ml extra).
    """
    import librosa
    import numpy as np

    y, sr = librosa.load(str(audio), sr=None, mono=True, offset=max(0.0, start_s))
    if len(y) == 0:
        raise ValueError("no audio after the requested start point")
    tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
    return float(np.atleast_1d(tempo)[0])


class LibrosaRhythmAdapter:
    """Implements BeatTracker and TuningEstimator ports."""

    def track(self, audio: Path) -> TempoMap:
        import librosa
        import numpy as np

        y, sr = librosa.load(str(audio), sr=None, mono=True)
        tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
        times = librosa.frames_to_time(beat_frames, sr=sr)
        bpm = float(np.atleast_1d(tempo)[0])
        beats_per_measure = 4  # not detected — see module docstring
        beats = tuple(
            Beat(
                time=float(t),
                measure=(i // beats_per_measure + 1) if i % beats_per_measure == 0 else -1,
            )
            for i, t in enumerate(times)
        )
        return TempoMap(beats=beats, average_bpm=bpm, beats_per_measure=beats_per_measure)

    def estimate(self, audio: Path, notes: list[NoteEvent]) -> Tuning:
        import librosa

        y, sr = librosa.load(str(audio), sr=None, mono=True)
        cents = float(librosa.estimate_tuning(y=y, sr=sr)) * 100.0

        # HEURISTIC drop-D hint: transcribed pitches below low E (40) but >= D (38).
        # Flagged for human confirmation — polyphonic tuning detection is unsolved.
        midi = (40, 45, 50, 55, 59, 64)
        if notes:
            lowest = min(n.pitch for n in notes)
            if 38 <= lowest < 40:
                midi = _DROP_D_MIDI
        return Tuning(midi=midi, cent_offset=cents)
