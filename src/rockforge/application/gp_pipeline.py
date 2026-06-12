"""GenerateFromGpUseCase — the high-fidelity alternative to the audio-ML path.

Notes/frets/techniques/tempo/sections come exactly from a GP3/GP4/GP5 file;
the recording is only normalized and packaged. Synchronization between score
and recording is a user-supplied offset: offset_s seconds of silence are
prepended to the recording, and the score (note/beat times) and LRC lyrics are
shifted forward by the same amount, so everything still lines up after the new
lead-in. Lyrics taken from the GP file's measure-anchored lyrics are already in
score time and shift along with the notes.
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


@dataclass(frozen=True)
class GpJobSpec:
    gp_path: Path
    audio_source: str
    lead_track: int | None = None
    rhythm_track: int | None = None
    offset_s: float = 0.0  # silence (s) added to the recording's start; score/lyrics shift too
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
            raise IngestionError("sync offset must be >= 0 — it adds a lead-in, never removes one")

        warnings: list[str] = []
        stage("ingest")
        raw = self.ingestor.fetch(spec.audio_source, workdir)
        stage("normalize")
        # offset_s adds a silent lead-in to the recording; the score and
        # lyrics are shifted forward by the same amount below.
        normalized = self.normalizer.normalize(raw, workdir, pad_start_s=spec.offset_s)

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
            parsed[kind] = parse_gp_track(spec.gp_path, lead_idx, spec.offset_s)
        if rhythm_idx is not None:
            parsed[ArrangementKind.RHYTHM] = parse_gp_track(
                spec.gp_path, rhythm_idx, spec.offset_s
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
            # LRC timestamps are against the original recording, before the
            # offset_s lead-in was added; shift them forward to match.
            vocals = parse_lrc(spec.lrc_text, spec.offset_s)
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

        if spec.offset_s == 0.0:
            warnings.append(
                "sync offset is 0.0s — verify the score's first note lines up with the "
                "recording and rebuild with an offset (seconds of silence to add to the "
                "recording's start) if needed"
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
