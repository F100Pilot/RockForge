"""Arrangement aggregate: what gets rendered into a Song2014 XML file."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from rockforge.domain.music import TabNote, TempoMap, Tuning


class ArrangementKind(Enum):
    LEAD = "Lead"
    RHYTHM = "Rhythm"
    COMBINED = "Combined"  # fallback when lead/rhythm split is not trusted


class ConfidenceLabel(Enum):
    """Per-stage confidence labelling surfaced to the user (docs/RELATORIO-TECNICO.md)."""

    MEASURED = "measured"  # backed by published benchmarks for comparable material
    HEURISTIC = "heuristic"  # deterministic rule, no published accuracy
    EXPERIMENTAL = "experimental"  # no published method exists for this task


@dataclass(frozen=True)
class Section:
    name: str
    start_time: float
    number: int = 1


@dataclass(frozen=True)
class SongMetadata:
    title: str
    artist: str
    album: str = ""
    year: int | None = None
    song_length: float = 0.0


@dataclass
class Arrangement:
    kind: ArrangementKind
    metadata: SongMetadata
    tuning: Tuning
    tempo_map: TempoMap
    notes: list[TabNote]
    sections: list[Section] = field(default_factory=list)
    capo: int = 0
    stage_confidence: dict[str, ConfidenceLabel] = field(default_factory=dict)

    def validate(self) -> list[str]:
        """Domain-level validation; returns human-readable problems (empty = valid)."""
        problems: list[str] = []
        if not self.notes:
            problems.append("arrangement has no notes")
        if self.metadata.song_length <= 0:
            problems.append("song_length must be positive")
        last_beat = self.tempo_map.beats[-1].time if self.tempo_map.beats else 0.0
        for n in self.notes:
            if n.time > self.metadata.song_length:
                problems.append(f"note at {n.time:.3f}s beyond song end")
            if n.time > last_beat:
                problems.append(f"note at {n.time:.3f}s beyond final ebeat {last_beat:.3f}s")
                break
        return problems
