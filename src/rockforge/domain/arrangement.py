"""Arrangement aggregate: what gets rendered into a Song2014 XML file."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from rockforge.domain.music import TabNote, TempoMap, Tuning
from rockforge.domain.tone import Tone


class ArrangementKind(Enum):
    LEAD = "Lead"
    RHYTHM = "Rhythm"
    COMBINED = "Combined"  # fallback when lead/rhythm split is not trusted
    # Alternate (bonus) arrangements: a SECOND Lead/Rhythm chart on the same path,
    # flagged non-representative — Rocksmith lists it as an alternate the player can
    # pick (a decoded DLC Builder CDLC encodes "Alternate Lead" as ArrangementName
    # Lead, RouteMask 1, Representative 0, bonusArr 1, its own IDs and a `lead2`
    # asset). They fold onto their base path for every format detail but that flag.
    ALTERNATE_LEAD = "Alternate Lead"
    ALTERNATE_RHYTHM = "Alternate Rhythm"

    @property
    def is_alternate(self) -> bool:
        return self in (ArrangementKind.ALTERNATE_LEAD, ArrangementKind.ALTERNATE_RHYTHM)

    @property
    def base_kind(self) -> ArrangementKind:
        """The primary kind this arrangement's path/name/route derive from."""
        return {
            ArrangementKind.ALTERNATE_LEAD: ArrangementKind.LEAD,
            ArrangementKind.ALTERNATE_RHYTHM: ArrangementKind.RHYTHM,
        }.get(self, self)


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


@dataclass(frozen=True)
class ToneChange:
    """Switch to a named tone at a point in time (names map to DLC Builder tones)."""

    time: float
    name: str


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
    # Rocksmith supports a base tone + up to 4 switchable tone slots (tonea-toned).
    # tone_base / tone_names reference tones by key; the XML and the .rs2dlc carry
    # those keys. ``tones`` holds the full gear definitions (optional — when empty,
    # the keys are names DLC Builder resolves from its own tone library).
    tone_base: str | None = None
    tone_names: list[str] = field(default_factory=list)
    tone_changes: list[ToneChange] = field(default_factory=list)
    tones: list[Tone] = field(default_factory=list)

    def validate(self) -> list[str]:
        """Domain-level validation; returns human-readable problems (empty = valid)."""
        problems: list[str] = []
        if len(self.tone_names) > 4:
            problems.append("Rocksmith supports at most 4 switchable tones (tonea-toned)")
        known = set(self.tone_names) | ({self.tone_base} if self.tone_base else set())
        for tc in self.tone_changes:
            if tc.name not in known:
                problems.append(
                    f"tone change at {tc.time:.3f}s references unknown tone '{tc.name}'"
                )
        # When full gear definitions are supplied, every referenced tone key must
        # have one (otherwise the .rs2dlc would carry a BaseTone/Tones name with no
        # matching Tones entry and DLC Builder flags it as missing).
        if self.tones:
            defined = {t.key for t in self.tones}
            for key in known:
                if key not in defined:
                    problems.append(f"tone '{key}' is referenced but has no gear definition")
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
