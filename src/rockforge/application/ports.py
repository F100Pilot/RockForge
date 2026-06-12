"""Ports (interfaces) for every pipeline stage — Clean Architecture boundary.

Each ML stage hides behind a Protocol so models can be swapped (e.g. htdemucs_6s
-> a future BS-RoFormer guitar checkpoint) without touching domain or use cases.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from rockforge.domain.music import NoteEvent, TempoMap, Tuning


class AudioIngestor(Protocol):
    def fetch(self, source: str, workdir: Path) -> Path:
        """Resolve a source (upload path or URL) into a local audio file."""
        ...


class AudioNormalizer(Protocol):
    def normalize(self, audio: Path, workdir: Path, offset_s: float = 0.0) -> Path:
        """Produce a 44.1 kHz stereo WAV with normalized loudness.

        When *offset_s* > 0 the audio is trimmed from that second before
        normalization — the remainder of the pipeline operates on the trimmed
        audio, so transcribed notes stay naturally synchronised.
        """
        ...


class StemSeparator(Protocol):
    def separate_guitar(self, audio: Path, workdir: Path) -> Path:
        """Return path to the aggregated guitar stem."""
        ...


class NoteTranscriber(Protocol):
    def transcribe(self, audio: Path) -> list[NoteEvent]:
        """Polyphonic note events (pitch/onset/duration/bends) from a guitar stem."""
        ...


class BeatTracker(Protocol):
    def track(self, audio: Path) -> TempoMap:
        ...


class TuningEstimator(Protocol):
    def estimate(self, audio: Path, notes: list[NoteEvent]) -> Tuning:
        ...


class GuitarRoleSplitter(Protocol):
    def split(self, notes: list[NoteEvent]) -> tuple[list[NoteEvent], list[NoteEvent]]:
        """EXPERIMENTAL: partition note events into (lead, rhythm) candidates.

        No published method or labelled dataset exists for this task
        (docs/research/01-source-separation.md §Q2). Output must be reviewed.
        """
        ...
