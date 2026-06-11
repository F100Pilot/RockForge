"""Polyphonic note transcription via Spotify Basic Pitch (Apache-2.0).

Why Basic Pitch: the only actively maintained, permissively licensed,
instrument-agnostic polyphonic transcriber with pitch-bend output
(docs/research/02-transcription.md §1). Known limits: generic (not
guitar-specific), no string/fret output, degrades on distorted tones.
The QMUL guitar models (ICASSP 2024 / GAPS) are stronger on GuitarSet but are
research code; they can be wired in later behind the same NoteTranscriber port.
"""

from __future__ import annotations

from pathlib import Path

from rockforge.domain.errors import TranscriptionError
from rockforge.domain.music import NoteEvent

GUITAR_MIDI_RANGE = (28, 96)  # ~E1 (drop tunings) to C7 — filter obvious bleed


class BasicPitchTranscriber:
    """Implements rockforge.application.ports.NoteTranscriber."""

    def __init__(self, onset_threshold: float = 0.5, frame_threshold: float = 0.3) -> None:
        self._onset = onset_threshold
        self._frame = frame_threshold

    def transcribe(self, audio: Path) -> list[NoteEvent]:
        try:
            from basic_pitch import ICASSP_2022_MODEL_PATH
            from basic_pitch.inference import predict
        except ImportError as exc:
            raise TranscriptionError(
                "basic-pitch is not installed (pip install 'rockforge[ml]')"
            ) from exc

        _, _, note_events = predict(
            str(audio),
            ICASSP_2022_MODEL_PATH,
            onset_threshold=self._onset,
            frame_threshold=self._frame,
        )
        out: list[NoteEvent] = []
        for start, end, pitch, amplitude, pitch_bends in note_events:
            if not (GUITAR_MIDI_RANGE[0] <= int(pitch) <= GUITAR_MIDI_RANGE[1]):
                continue
            bend = 0.0
            if pitch_bends:
                # basic-pitch reports bends in 1/3-semitone bins around the note
                bend = max(pitch_bends, key=abs) / 3.0
            out.append(
                NoteEvent(
                    pitch=int(pitch),
                    start=float(start),
                    duration=max(0.0, float(end) - float(start)),
                    confidence=float(amplitude),
                    bend_semitones=float(bend),
                )
            )
        out.sort(key=lambda n: (n.start, n.pitch))
        return out
