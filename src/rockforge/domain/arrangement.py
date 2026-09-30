"""Arrangement aggregate: what gets rendered into a Song2014 XML file."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
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


def number_sections(
    sections: Sequence[Section], counts: Mapping[str, int] | None = None
) -> tuple[list[Section], dict[str, int]]:
    """Number sections PER NAME, 1-based, in the order given.

    Rocksmith shows a section as "<name> <number>" ("Riff 3"), so the number is
    an ordinal WITHIN that name — not the section's index in the list, which is
    what both callers used to pass. With COUNT/END and several names mixed in,
    an index produced duplicates and gaps (a real build shipped two consecutive
    sections both numbered 2), naming two different passages the same thing.

    ``counts`` carries a running tally in, and the updated tally comes back out,
    so a caller can continue the numbering across several arrangements — which
    is what a DLC Builder build does (its Lead riffs run 1-17 and its Rhythm
    riffs continue 18-34, its noguitars 1-2 then 3-4). Names are matched
    case-insensitively so "Verse"/"verse" share one counter.
    """
    tally = dict(counts or {})
    out: list[Section] = []
    for sec in sections:
        key = sec.name.casefold()
        tally[key] = tally.get(key, 0) + 1
        out.append(replace(sec, number=tally[key]))
    return out, tally


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

    def switch_slots(self) -> list[str]:
        """The tones in slots A-D as the game sees them: the switchable names that
        have a gear definition, in order. A tone change's id is its index here
        (Rocksmith2014.NET sets ``Id = IndexOf(Tones.Names, name)``), so the
        manifest's Tone_A..D and the SNG's tone changes both read this list."""
        defined = {t.key for t in self.tones}
        return [n for n in self.tone_names if n in defined][:4]

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
