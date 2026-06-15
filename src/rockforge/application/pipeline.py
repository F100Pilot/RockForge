"""GenerateCdlcUseCase — orchestrates the 10-stage pipeline (docs/RELATORIO-TECNICO.md §7).

Every stage result carries an explicit confidence label; nothing is silently
defaulted. The lead/rhythm split is EXPERIMENTAL and a COMBINED arrangement is
always produced as the trustworthy fallback.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from rockforge.application.ports import (
    AudioIngestor,
    AudioNormalizer,
    BeatTracker,
    GuitarRoleSplitter,
    LyricTranscriber,
    NoteTranscriber,
    Packager,
    StemSeparator,
    TuningEstimator,
)
from rockforge.domain.arrangement import (
    Arrangement,
    ArrangementKind,
    ConfidenceLabel,
    SongMetadata,
)
from rockforge.domain.music import Beat, NoteEvent, TempoMap, Tuning
from rockforge.infrastructure.fretboard.mapper import infer_legato, map_to_fretboard
from rockforge.infrastructure.packaging.dlcbuilder import PackagingResult
from rockforge.infrastructure.rsxml.vocals import VocalEvent

_BASE_CONFIDENCE: dict[str, ConfidenceLabel] = {
    "separation": ConfidenceLabel.MEASURED,  # htdemucs_6s: published model, quality "okay"
    "transcription": ConfidenceLabel.MEASURED,  # basic-pitch: published, degrades w/ distortion
    "tempo": ConfidenceLabel.MEASURED,  # librosa DP tracker: published, below neural SOTA
    "time_signature": ConfidenceLabel.HEURISTIC,  # fixed 4/4 assumption — not detected
    "tuning": ConfidenceLabel.HEURISTIC,  # cents offset measured; drop-tuning hint heuristic
    "fret_mapping": ConfidenceLabel.HEURISTIC,  # deterministic playability optimization
    "legato_techniques": ConfidenceLabel.HEURISTIC,
    "lead_rhythm_split": ConfidenceLabel.EXPERIMENTAL,  # no published method exists
}


@dataclass(frozen=True)
class PipelineResult:
    packaging: PackagingResult
    note_counts: dict[str, int]
    warnings: tuple[str, ...]


@dataclass
class GenerateCdlcUseCase:
    ingestor: AudioIngestor
    normalizer: AudioNormalizer
    separator: StemSeparator
    transcriber: NoteTranscriber
    beat_tracker: BeatTracker
    tuning_estimator: TuningEstimator
    role_splitter: GuitarRoleSplitter
    packager: Packager
    lyric_transcriber: LyricTranscriber | None = None

    def run(
        self,
        source: str,
        metadata: SongMetadata,
        workdir: Path,
        split_lead_rhythm: bool = True,
        tuning_override: Tuning | None = None,
        offset_s: float = 0.0,
        transcribe_lyrics: bool = False,
        lyrics_events: list[VocalEvent] | None = None,
        cover_art: Path | None = None,
        on_stage: Callable[[str], None] | None = None,
    ) -> PipelineResult:
        def stage(name: str) -> None:
            if on_stage is not None:
                on_stage(name)

        warnings: list[str] = []
        stage("ingest")
        raw = self.ingestor.fetch(source, workdir)                     # 1. ingest
        stage("normalize")
        normalized = self.normalizer.normalize(raw, workdir, offset_s)  # 2. normalize + trim
        stage("separate")
        guitar_stem = self.separator.separate_guitar(normalized, workdir)  # 3. separate
        stage("transcribe")
        notes = self.transcriber.transcribe(guitar_stem)               # 6. notes (4/5 below)
        stage("beat_track")
        tempo_map = self.beat_tracker.track(normalized)
        stage("tuning")
        if tuning_override is not None:
            tuning = tuning_override  # human-confirmed tuning takes precedence
            warnings.append("tuning supplied by user override (automatic estimate skipped)")
        else:
            tuning = self.tuning_estimator.estimate(guitar_stem, notes)

        song_length = self._song_length(notes, tempo_map)
        metadata = SongMetadata(
            title=metadata.title,
            artist=metadata.artist,
            album=metadata.album,
            year=metadata.year,
            song_length=song_length,
        )
        tempo_map = self._extend_beats_to(tempo_map, song_length)

        def build(kind: ArrangementKind, events: list[NoteEvent]) -> Arrangement:
            tab = infer_legato(map_to_fretboard(events, tuning, warnings))  # 7. strings/frets
            return Arrangement(                                        # 8. arrangement
                kind=kind,
                metadata=metadata,
                tuning=tuning,
                tempo_map=tempo_map,
                notes=tab,
                stage_confidence=dict(_BASE_CONFIDENCE),
            )

        stage("fret_mapping")
        arrangements = [build(ArrangementKind.COMBINED, notes)]
        if split_lead_rhythm:                                          # 5. EXPERIMENTAL split
            lead, rhythm = self.role_splitter.split(notes)
            if lead and rhythm:
                arrangements.append(build(ArrangementKind.LEAD, lead))
                arrangements.append(build(ArrangementKind.RHYTHM, rhythm))
                warnings.append(
                    "lead/rhythm split is EXPERIMENTAL (no published method exists); "
                    "review both arrangements — the COMBINED arrangement is the fallback"
                )
            else:
                warnings.append(
                    "lead/rhythm split produced an empty partition; only COMBINED emitted"
                )

        # Optional automatic lyrics (EXPERIMENTAL): WhisperX over the vocals
        # stem Demucs htdemucs_6s produces next to the guitar stem. LRC input
        # (GP flow) remains the preferred, measured-timing source.
        vocals_events = None
        if lyrics_events:
            stage("lyrics")
            vocals_events = lyrics_events
            warnings.append("lyrics from the in-app editor (per-word timing) used")
        elif transcribe_lyrics:
            stage("lyrics")
            vocals_stem = guitar_stem.parent / "vocals.wav"
            if self.lyric_transcriber is None:
                warnings.append(
                    "lyric transcription requested but whisperx is not installed "
                    "(pip install 'rockforge[lyrics]') — no vocals XML emitted"
                )
            elif not vocals_stem.exists():
                warnings.append(
                    "lyric transcription skipped: separation produced no vocals stem"
                )
            else:
                vocals_events = self.lyric_transcriber.transcribe(vocals_stem) or None
                if vocals_events is None:
                    warnings.append(
                        "lyric transcription found no words (instrumental or "
                        "low-confidence vocals) — no vocals XML emitted"
                    )
                else:
                    warnings.append(
                        "lyrics transcribed automatically (WhisperX) — EXPERIMENTAL: "
                        "review text and timing; provide an LRC file for measured timing"
                    )

        stage("package")
        packaging = self.packager.package(
            arrangements, normalized, workdir / "bundle", vocals=vocals_events, cover_art=cover_art
        )  # 9/10
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

    @staticmethod
    def _song_length(notes: list[NoteEvent], tempo_map: TempoMap) -> float:
        last_note = max((n.start + n.duration for n in notes), default=0.0)
        last_beat = tempo_map.beats[-1].time if tempo_map.beats else 0.0
        return max(last_note, last_beat) + 1.0

    @staticmethod
    def _extend_beats_to(tempo_map: TempoMap, end: float) -> TempoMap:
        """Ensure the ebeat grid covers the whole song (Rocksmith requires it)."""
        beats = list(tempo_map.beats)
        if len(beats) < 2:
            return tempo_map
        interval = beats[-1].time - beats[-2].time
        if interval <= 0:
            return tempo_map
        i = len(beats)
        t = beats[-1].time + interval
        bpmeas = tempo_map.beats_per_measure
        while t <= end:
            measure = (i // bpmeas + 1) if i % bpmeas == 0 else -1
            beats.append(Beat(time=t, measure=measure))
            t += interval
            i += 1
        return TempoMap(
            beats=tuple(beats),
            average_bpm=tempo_map.average_bpm,
            beats_per_measure=tempo_map.beats_per_measure,
        )
