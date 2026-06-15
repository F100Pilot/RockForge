"""Ports (interfaces) for every pipeline stage — Clean Architecture boundary.

Each ML stage hides behind a Protocol so models can be swapped (e.g. htdemucs_6s
-> a future BS-RoFormer guitar checkpoint) without touching domain or use cases.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from rockforge.domain.arrangement import Arrangement
from rockforge.domain.music import NoteEvent, TempoMap, Tuning
from rockforge.infrastructure.packaging.dlcbuilder import PackagingResult
from rockforge.infrastructure.rsxml.vocals import VocalEvent


class AudioIngestor(Protocol):
    def fetch(self, source: str, workdir: Path) -> Path:
        """Resolve a source (upload path or URL) into a local audio file."""
        ...


class AudioNormalizer(Protocol):
    def normalize(
        self, audio: Path, workdir: Path, offset_s: float = 0.0, pad_start_s: float = 0.0
    ) -> Path:
        """Produce a 44.1 kHz stereo WAV with normalized loudness.

        When *offset_s* > 0 the audio is trimmed from that second before
        normalization — the remainder of the pipeline operates on the trimmed
        audio, so transcribed notes stay naturally synchronised.

        When *pad_start_s* > 0, that many seconds of silence are prepended —
        used by the GP path to insert a lead-in while shifting the score and
        lyrics by the same amount (see gp_pipeline.GpJobSpec.offset_s).
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


class LyricTranscriber(Protocol):
    def transcribe(self, vocals_stem: Path) -> list[VocalEvent]:
        """Word-level lyric events transcribed from an isolated vocals stem.

        Timestamps come from forced alignment against the audio itself, so
        they share the recording's clock (same timeline as the notes XML).
        Returns [] when the stem is (near-)silent or no word passes the
        confidence filter — callers must treat that as "no vocals", not error.
        """
        ...


class Packager(Protocol):
    def package(
        self,
        arrangements: list[Arrangement],
        audio: Path,
        out_dir: Path,
        vocals: list[VocalEvent] | None = None,
        cover_art: Path | None = None,
    ) -> PackagingResult:
        """Write the arrangement bundle (and PSARC, if the backend can produce one).

        *cover_art*, if given, is an image file (jpg/png) copied into the
        bundle as the album art — see ``rockforge_project.json``'s
        ``cover_art`` field. The retail in-game DDS texture/``albumArt`` URN is
        not produced yet (honesty note in ``packaging/psarc/packer.py``).
        """
        ...
