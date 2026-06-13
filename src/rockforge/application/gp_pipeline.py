"""GenerateFromGpUseCase — the high-fidelity alternative to the audio-ML path.

Notes/frets/techniques/tempo/sections come exactly from a GP3/GP4/GP5 file;
the recording is only normalized and packaged. Synchronization is the one thing
the GP file cannot know, so it is a single user-supplied number: offset_s = the
moment (seconds) at which the song's first note is actually heard in the
recording. The score (note/beat/section times) and the GP's measure-anchored
lyrics are shifted forward to land there, so note 0 lines up with where the
music starts; the recording itself is left untouched (its own intro provides the
lead-in). Crucially we do NOT pad the audio by offset_s as well — doing so would
move the music forward by the same amount and re-open the gap, which is the bug
that made the chart and audio drift apart.

The one exception is the minimum lead-in: DLC Builder's phrase generator needs
room before the first note for the count-in (it errors outright when content
starts at time 0). When offset_s is below MIN_LEAD_S we prepend just the
shortfall as silence so there is always room — see MIN_LEAD_S.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from rockforge.application.pipeline import PipelineResult
from rockforge.application.ports import AudioIngestor, AudioNormalizer
from rockforge.domain.arrangement import (
    Arrangement,
    ArrangementKind,
    ConfidenceLabel,
    Section,
    SongMetadata,
    ToneChange,
)
from rockforge.domain.errors import IngestionError
from rockforge.infrastructure.gpimport.parser import ParsedGpTrack, inspect_gp, parse_gp_track
from rockforge.infrastructure.packaging.dlcbuilder import DlcBuilderPackager
from rockforge.infrastructure.rsxml.vocals import VocalEvent, parse_lrc

# Minimum lead-in before the first note. DLC Builder's PhraseGenerator inserts a
# count-in phrase before the arrangement content and fails ("no room for an empty
# phrase before the arrangement content starts") when content begins at time 0;
# EOF likewise advises a few seconds of silence at the start. When the user's
# sync point is below this, the shortfall is added as silence.
MIN_LEAD_S = 2.0


@dataclass(frozen=True)
class GpJobSpec:
    gp_path: Path
    audio_source: str
    lead_track: int | None = None
    rhythm_track: int | None = None
    offset_s: float = 0.0  # second in the recording where the song's first note is heard
    lrc_text: str | None = None
    tone_base: str | None = None
    tone_names: list[str] = field(default_factory=list)
    tone_changes: list[ToneChange] = field(default_factory=list)


def auto_pick_tracks(gp_path: Path) -> tuple[int | None, int | None]:
    """Heuristic track selection by name when the user does not choose.

    Returns (lead, rhythm); falls back to the first 6-string non-percussion
    track as a combined arrangement (rhythm slot left None).
    """
    info = inspect_gp(gp_path)
    eligible = [t for t in info.tracks if not t.is_percussion and t.string_count == 6]
    if not eligible:
        return None, None
    lead = next((t.index for t in eligible if "lead" in t.name.lower()), None)
    rhythm = next((t.index for t in eligible if "rhythm" in t.name.lower()), None)
    if lead is None and rhythm is None:
        return eligible[0].index, None
    return lead, rhythm


@dataclass
class GenerateFromGpUseCase:
    ingestor: AudioIngestor
    normalizer: AudioNormalizer
    packager: DlcBuilderPackager

    def run(
        self,
        spec: GpJobSpec,
        metadata: SongMetadata,
        workdir: Path,
        on_stage: Callable[[str], None] | None = None,
    ) -> PipelineResult:
        def stage(name: str) -> None:
            if on_stage is not None:
                on_stage(name)

        if spec.offset_s < 0.0:
            raise IngestionError(
                "sync offset must be >= 0 — it is the second in the recording where the "
                "song starts, never a negative time"
            )

        warnings: list[str] = []
        # Place the first note at the recording's music start (offset_s); pad only
        # the shortfall up to MIN_LEAD_S so the count-in phrase always has room.
        # The score shifts by the full content time; the audio (and thus an LRC
        # synced to it) shifts only by what silence we actually prepend.
        pad_start_s = max(0.0, MIN_LEAD_S - spec.offset_s)
        score_shift = spec.offset_s + pad_start_s  # == max(offset_s, MIN_LEAD_S)

        stage("ingest")
        raw = self.ingestor.fetch(spec.audio_source, workdir)
        stage("normalize")
        normalized = self.normalizer.normalize(raw, workdir, pad_start_s=pad_start_s)

        stage("parse_gp")
        lead_idx, rhythm_idx = spec.lead_track, spec.rhythm_track
        if lead_idx is None and rhythm_idx is None:
            lead_idx, rhythm_idx = auto_pick_tracks(spec.gp_path)
            if lead_idx is None and rhythm_idx is None:
                raise IngestionError("no eligible 6-string guitar track found in the GP file")
            warnings.append(
                "tracks auto-selected by name heuristic — confirm they are the right ones"
            )

        parsed: dict[ArrangementKind, ParsedGpTrack] = {}
        if lead_idx is not None and lead_idx == rhythm_idx:
            raise IngestionError("lead and rhythm cannot use the same GP track")
        if lead_idx is not None:
            kind = ArrangementKind.LEAD if rhythm_idx is not None else ArrangementKind.COMBINED
            parsed[kind] = parse_gp_track(spec.gp_path, lead_idx, score_shift)
        if rhythm_idx is not None:
            parsed[ArrangementKind.RHYTHM] = parse_gp_track(
                spec.gp_path, rhythm_idx, score_shift
            )

        stage("build_arrangements")
        first = next(iter(parsed.values()))
        song_length = (
            max(
                max((n.time + n.sustain for n in p.notes), default=0.0)
                for p in parsed.values()
            )
            + 1.0
        )
        metadata = SongMetadata(
            title=metadata.title,
            artist=metadata.artist,
            album=metadata.album,
            year=metadata.year,
            song_length=song_length,
        )
        confidence = {
            "notes": ConfidenceLabel.MEASURED,  # exact from the authored GP file
            "sync_offset": ConfidenceLabel.HEURISTIC,  # manual user offset
            "lyrics": ConfidenceLabel.HEURISTIC if not spec.lrc_text else ConfidenceLabel.MEASURED,
        }
        arrangements = [
            Arrangement(
                kind=kind,
                metadata=metadata,
                tuning=p.tuning,
                tempo_map=p.tempo_map,
                notes=p.notes,
                sections=[
                    Section(name=s.name, start_time=s.start_time, number=i + 1)
                    for i, s in enumerate(p.sections)
                ],
                stage_confidence=dict(confidence),
                tone_base=spec.tone_base,
                tone_names=list(spec.tone_names),
                tone_changes=list(spec.tone_changes),
            )
            for kind, p in parsed.items()
        ]

        stage("lyrics")
        vocals: list[VocalEvent] = []
        if spec.lrc_text:
            # LRC timestamps are synced to the recording as supplied, so they only
            # move by the silence we actually prepended (pad_start_s) — not by the
            # full score shift, which also absorbs the score's own zero offset.
            vocals = parse_lrc(spec.lrc_text, pad_start_s)
            if not vocals:
                warnings.append("LRC file contained no timestamped lines")
        elif first.lyrics:
            vocals = [
                VocalEvent(time=line.time, length=2.0, lyric=line.text)
                for line in first.lyrics
            ]
            warnings.append(
                "lyrics taken from the GP file: line-level timing only (anchored to "
                "measures) — supply an LRC file for proper sync"
            )

        if pad_start_s > 0.0:
            warnings.append(
                f"sync offset was {spec.offset_s:.2f}s; added {pad_start_s:.2f}s of silence to "
                f"reach the {MIN_LEAD_S:.0f}s minimum lead-in DLC Builder needs for the "
                f"count-in. The song's first note now plays at {score_shift:.2f}s — use the "
                f"visual sync tool if the chart and audio still drift."
            )

        stage("package")
        packaging = self.packager.package(
            arrangements, normalized, workdir / "bundle", vocals=vocals or None
        )
        if packaging.wem_path is None:
            warnings.append(
                "no .wem produced: no local Wwise installation found "
                "(set ROCKFORGE_WWISE_ROOT or WWISEROOT)"
            )
        if packaging.psarc_path is None:
            warnings.append(
                "no PSARC produced: final packing is delegated to DLC Builder "
                "(bundle is import-ready); configure ROCKFORGE_PSARC_PACKER_CMD to automate it"
            )
        return PipelineResult(
            packaging=packaging,
            note_counts={a.kind.value: len(a.notes) for a in arrangements},
            warnings=tuple(warnings),
        )
