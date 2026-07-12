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
from rockforge.domain.errors import TranscriptionError
from rockforge.domain.music import (
    Beat,
    NoteEvent,
    TempoMap,
    Tuning,
    clean_transcription,
    tuning_name,
)
from rockforge.infrastructure.fretboard.mapper import infer_legato, map_to_fretboard
from rockforge.infrastructure.packaging.dlcbuilder import PackagingResult
from rockforge.infrastructure.rsxml.vocals import VocalEvent, enforce_max_line_words

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
    # Lyrics extracted from a GP file (recording clock, i.e. un-padded), so the
    # worker can surface them in the "Letras" editor / tab viewer. Empty unless
    # GP-embedded lyrics were used (not when the user supplied LRC/editor rows).
    gp_lyrics: tuple[VocalEvent, ...] = ()


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
        dynamic_difficulty: bool = True,
        on_stage: Callable[[str], None] | None = None,
        lead_source: str | None = None,
        rhythm_source: str | None = None,
        separate_role_stems: bool = False,
    ) -> PipelineResult:
        """When ``lead_source`` and/or ``rhythm_source`` are given, each is
        transcribed INDEPENDENTLY into its own arrangement (no experimental
        lead/rhythm split — each recording is already one guitar); ``source``
        remains the bundle audio (.wem) and the beat/tempo reference. Otherwise
        ``source`` is transcribed into COMBINED plus the experimental split.
        """
        def stage(name: str) -> None:
            if on_stage is not None:
                on_stage(name)

        warnings: list[str] = []
        per_role = lead_source is not None or rhythm_source is not None

        stage("ingest")
        raw = self.ingestor.fetch(source, workdir)                     # 1. ingest
        stage("normalize")
        normalized = self.normalizer.normalize(raw, workdir, offset_s)  # 2. normalize + trim

        # guitar stem of the BUNDLE source: the note source in single-source mode,
        # and (in both modes) the sibling of the vocals stem for lyric transcription.
        guitar_stem: Path | None = None
        # (kind, cleaned NoteEvents, tuning) tuples to fret-map into arrangements.
        to_build: list[tuple[ArrangementKind, list[NoteEvent], Tuning]] = []

        if per_role:
            # Each provided stem → its own arrangement, transcribed in its own
            # sub-workdir so the intermediate files never collide.
            for kind, src in (
                (ArrangementKind.LEAD, lead_source),
                (ArrangementKind.RHYTHM, rhythm_source),
            ):
                if src is None:
                    continue
                sub = workdir / f"stem_{kind.value.lower()}"
                r_raw = self.ingestor.fetch(src, sub)
                r_norm = self.normalizer.normalize(r_raw, sub, offset_s)
                # A per-role stem is ALREADY one isolated guitar, so Demucs is
                # skipped by default — re-separating an isolated guitar is slow
                # (Demucs is the heaviest stage) and can degrade it. Only run it
                # when the user says the stem still has other instruments.
                if separate_role_stems:
                    stage("separate")
                    r_guitar = self.separator.separate_guitar(r_norm, sub)
                else:
                    r_guitar = r_norm
                stage("transcribe")
                r_notes = self.transcriber.transcribe(r_guitar)
                stage("tuning")
                r_tuning = self._resolve_tuning(
                    tuning_override, r_guitar, r_notes, warnings, f"{kind.value}: "
                )
                r_notes = self._clean_and_warn(
                    r_notes, r_tuning, warnings, f"{kind.value}: "
                )
                to_build.append((kind, r_notes, r_tuning))
            if not to_build:
                raise TranscriptionError("no lead/rhythm audio produced any notes")
            warnings.append(
                "per-role transcription: Lead and Rhythm come from separate "
                "recordings, so no experimental split is used"
                + ("" if separate_role_stems else "; stems used as-is (Demucs skipped)")
            )
            if transcribe_lyrics:  # need the vocals stem of the bundle mix
                stage("separate")
                guitar_stem = self.separator.separate_guitar(normalized, workdir)
        else:
            stage("separate")
            guitar_stem = self.separator.separate_guitar(normalized, workdir)  # 3. separate
            stage("transcribe")
            notes = self.transcriber.transcribe(guitar_stem)               # 6. notes

        stage("beat_track")
        tempo_map = self.beat_tracker.track(normalized)

        if not per_role:
            stage("tuning")
            assert guitar_stem is not None
            tuning = self._resolve_tuning(tuning_override, guitar_stem, notes, warnings)
            notes = self._clean_and_warn(notes, tuning, warnings)
            to_build.append((ArrangementKind.COMBINED, notes, tuning))
            if split_lead_rhythm:                                      # 5. EXPERIMENTAL split
                lead, rhythm = self.role_splitter.split(notes)
                if lead and rhythm:
                    to_build.append((ArrangementKind.LEAD, lead, tuning))
                    to_build.append((ArrangementKind.RHYTHM, rhythm, tuning))
                    warnings.append(
                        "lead/rhythm split is EXPERIMENTAL (no published method exists); "
                        "review both arrangements — the COMBINED arrangement is the fallback"
                    )
                else:
                    warnings.append(
                        "lead/rhythm split produced an empty partition; only COMBINED emitted"
                    )

        all_notes = [n for _, ns, _ in to_build for n in ns]
        song_length = self._song_length(all_notes, tempo_map)
        metadata = SongMetadata(
            title=metadata.title,
            artist=metadata.artist,
            album=metadata.album,
            year=metadata.year,
            song_length=song_length,
        )
        tempo_map = self._extend_beats_to(tempo_map, song_length)

        def build(kind: ArrangementKind, events: list[NoteEvent], tng: Tuning) -> Arrangement:
            tab = infer_legato(map_to_fretboard(events, tng, warnings))  # 7. strings/frets
            return Arrangement(                                        # 8. arrangement
                kind=kind,
                metadata=metadata,
                tuning=tng,
                tempo_map=tempo_map,
                notes=tab,
                stage_confidence=dict(_BASE_CONFIDENCE),
            )

        stage("fret_mapping")
        arrangements = [build(kind, events, tng) for kind, events, tng in to_build]

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
            vocals_stem = guitar_stem.parent / "vocals.wav" if guitar_stem else None
            if self.lyric_transcriber is None:
                warnings.append(
                    "lyric transcription requested but whisperx is not installed "
                    "(pip install 'rockforge[lyrics]') — no vocals XML emitted"
                )
            elif vocals_stem is None or not vocals_stem.exists():
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

        if vocals_events:
            vocals_events = enforce_max_line_words(vocals_events)  # cap long lyric lines

        stage("package")
        packaging = self.packager.package(
            arrangements, normalized, workdir / "bundle", vocals=vocals_events,
            cover_art=cover_art, dynamic_difficulty=dynamic_difficulty,
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

    def _resolve_tuning(
        self,
        override: Tuning | None,
        guitar_stem: Path,
        notes: list[NoteEvent],
        warnings: list[str],
        prefix: str = "",
    ) -> Tuning:
        if override is not None:
            warnings.append(
                f"{prefix}tuning supplied by user override (automatic estimate skipped)"
            )
            return override
        tuning = self.tuning_estimator.estimate(guitar_stem, notes)
        warnings.append(
            f"{prefix}tuning guessed from the transcription: {tuning_name(tuning.midi)} "
            f"— string-tuning detection from audio is unreliable; set it in the "
            f"tuning selector if it's wrong (a wrong tuning drops real low notes)"
        )
        return tuning

    @staticmethod
    def _clean_and_warn(
        notes: list[NoteEvent], tuning: Tuning, warnings: list[str], prefix: str = ""
    ) -> list[NoteEvent]:
        """Prune spurious out-of-range / fragment notes and surface one aggregated
        warning per category (a distorted mix yields hundreds of ghosts)."""
        cleanup = clean_transcription(notes, tuning)
        if cleanup.dropped_out_of_range:
            warnings.append(
                f"{prefix}dropped {cleanup.dropped_out_of_range} transcribed note(s) "
                f"outside the guitar's playable range for this tuning (sub-harmonic/"
                f"octave ghosts from the mix — automatic transcription is approximate)"
            )
        if cleanup.dropped_too_short:
            warnings.append(
                f"{prefix}dropped {cleanup.dropped_too_short} very short transcribed "
                f"note(s) (detector fragments/noise)"
            )
        if cleanup.merged_fragments:
            warnings.append(
                f"{prefix}merged {cleanup.merged_fragments} fragmented note(s) back "
                f"into sustained notes"
            )
        return cleanup.notes

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
