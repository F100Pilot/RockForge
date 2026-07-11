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
from rockforge.application.ports import AudioIngestor, AudioNormalizer, Packager
from rockforge.domain.arrangement import (
    Arrangement,
    ArrangementKind,
    ConfidenceLabel,
    Section,
    SongMetadata,
    ToneChange,
)
from rockforge.domain.errors import IngestionError
from rockforge.domain.music import TabNote, Technique, Tuning
from rockforge.domain.tone import Tone
from rockforge.infrastructure.gpimport.parser import (
    GpSection,
    ParsedGpTrack,
    inspect_gp,
    parse_gp_track,
)
from rockforge.infrastructure.rsxml.vocals import (
    VocalEvent,
    distribute_syllables,
    enforce_max_line_words,
    parse_lyrics,
)

# Minimum lead-in before the first note. DLC Builder's PhraseGenerator inserts a
# count-in phrase before the arrangement content and fails ("no room for an empty
# phrase before the arrangement content starts") when content begins at time 0;
# EOF likewise advises a few seconds of silence at the start. When the user's
# sync point is below this, the shortfall is added as silence.
MIN_LEAD_S = 2.0


# Metrical ratios a beat tracker confuses the true pulse with — not just the
# octave (½/2) but also the triplet / compound-meter grid (⅓, ⅔, 3/2, 3). A
# GP file whose recording is the SAME song has a true tempo ratio near 1, so a
# detected tempo that lands 50% high (3/2) or a third off is almost always one
# of these grid confusions, NOT a real tempo difference. Including them lets the
# suggestion snap back to ~1.0 instead of proposing a bogus ×1.5 scale.
_TEMPO_METRICAL_FACTORS = (1 / 4, 1 / 3, 1 / 2, 2 / 3, 1.0, 3 / 2, 2.0, 3.0, 4.0)


def suggest_tempo_scale(gp_bpm: float, detected_bpm: float) -> float:
    """Metrically-corrected tempo_scale aligning the GP tempo to a detected one.

    Beat trackers routinely report a tempo at the wrong metrical level — an
    octave off (half/double) or on the triplet/compound grid (e.g. 1.5× the true
    pulse). Since the GP file and the recording are the same song, the true ratio
    is near 1, so we pick the metrical multiple of ``detected_bpm``
    (``_TEMPO_METRICAL_FACTORS``) whose resulting scale sits closest to 1.0 —
    fixing the "auto-sync jumps the BPM ~50%" case where only ½/1/2 were tried
    and a 3/2 detection had no nearby octave to snap to.
    ``tempo_scale = gp_bpm / effective_recording_bpm`` because the GP timeline is
    stretched/compressed to the recording's tempo (parser scales the effective BPM
    inversely). Used both for whole-song sync and for a local re-tempo from a point.
    """
    if gp_bpm <= 0 or detected_bpm <= 0:
        raise IngestionError("gp_bpm and detected_bpm must be positive to suggest a tempo")
    candidates = [detected_bpm * f for f in _TEMPO_METRICAL_FACTORS]
    best = min(candidates, key=lambda b: abs((gp_bpm / b) - 1.0))
    return gp_bpm / best


def suggest_sync(
    gp_bpm: float, detected_bpm: float, first_onset_s: float
) -> tuple[float, float]:
    """Propose (tempo_scale, offset_s) aligning the GP chart to a recording.

    ``offset_s`` is where audible content begins in the recording — the second the
    first note should be heard. This is a *suggestion*: the user reviews it in the
    tab viewer before rebuilding, never silently applied.
    """
    return suggest_tempo_scale(gp_bpm, detected_bpm), max(0.0, first_onset_s)


@dataclass(frozen=True)
class ArrangementSync:
    """Per-arrangement chart-timing overrides (tempo + drift anchors).

    These only touch one arrangement's own note/beat/section/lyric times, so
    dragging a note in the Lead chart never moves the Rhythm chart. The sync
    *offset* is deliberately NOT here: all arrangements share one audio track,
    so where the recording starts is a property of the recording, shared by
    every arrangement (a per-arrangement offset would desync the charts from
    each other against the same .wem). Per-arrangement uniform shifts are still
    available as a single-anchor round.
    """

    tempo_scale: float = 1.0
    sync_anchor_stages: list[list[tuple[float, float]]] = field(default_factory=list)


@dataclass(frozen=True)
class GpJobSpec:
    gp_path: Path
    audio_source: str
    # Each arrangement is an OPTIONAL, independently-assigned slot: the user maps a
    # GP track to it (or leaves it empty). Nothing is auto-generated — the song
    # gets exactly the arrangements assigned here. When ALL are empty, tracks are
    # auto-picked as a convenience (lead+rhythm, or a lone track → Combined).
    lead_track: int | None = None
    rhythm_track: int | None = None
    combo_track: int | None = None
    # Optional SECOND Lead/Rhythm charts from other GP tracks — produced as
    # non-representative "Alternate" arrangements the player can pick in game.
    alt_lead_track: int | None = None
    alt_rhythm_track: int | None = None
    offset_s: float = 0.0  # second in the recording where the song's first note is heard
    # Extra silence (seconds) prepended at the very start, on top of the
    # automatic MIN_LEAD_S lead-in — user-controlled "intro silence" that pushes
    # the whole bundle (audio + notes + lyrics) later together. 0 = none.
    lead_in_s: float = 0.0
    # Multiplicative stretch (>1) / compression (<1) of the whole musical
    # timeline, applied at parse time around the song's start — corrects a
    # constant GP-vs-recording tempo mismatch (the linear part of sync drift)
    # in one move, before any sync_anchor_stages fine-tuning. Used as the
    # default for arrangements without an explicit arrangement_sync override.
    tempo_scale: float = 1.0
    lrc_text: str | None = None
    tone_base: str | None = None
    tone_names: list[str] = field(default_factory=list)
    tone_changes: list[ToneChange] = field(default_factory=list)
    # Full gear definitions for the referenced tones (built in the tone editor).
    # When present they are serialized into the .rs2dlc so the tones work in-game;
    # tone_base/tone_names reference these by key.
    tones: list[Tone] = field(default_factory=list)
    # Manual drift-correction rounds. Each round is a list of (chart_time_s,
    # corrected_time_s) anchor pairs, expressed in the timeline produced by the
    # *previous* round (i.e. as shown in the tab viewer at the time the user
    # drew them) — round 0 is in the raw post-offset_s timeline. Rounds are
    # applied in order via piecewise-linear stretch/compress, so corrections
    # made in separate sessions (after reloading a completed job) compose
    # correctly instead of overwriting each other. Default for arrangements
    # without an explicit arrangement_sync override.
    sync_anchor_stages: list[list[tuple[float, float]]] = field(default_factory=list)
    # Per-arrangement tempo + drift overrides, keyed by ArrangementKind.value
    # ("Lead"/"Rhythm"/"Combined"). An arrangement absent here falls back to the
    # job-level tempo_scale / sync_anchor_stages above.
    arrangement_sync: dict[str, ArrangementSync] = field(default_factory=dict)
    # When False, the mute/attack techniques (palm mute, slap, pop, tap) are
    # stripped from every note so they import as plain notes. These are the
    # techniques that change the Rocksmith note sprite (the palm-mute chevron
    # looks like pop/slap "wings"); some GP files mark them where the user wants
    # clean notes, so this is an opt-out.
    import_mute_techniques: bool = True
    # Edited per-word lyrics from the in-app lyrics editor (recording-clock
    # times, before pad_start_s). Takes precedence over lrc_text and GP-embedded
    # lyrics when present.
    lyrics_events: list[VocalEvent] | None = None
    # Optional cover-art image (jpg/png), copied into the bundle and recorded
    # in rockforge_project.json; see Packager.package's cover_art parameter.
    cover_art: Path | None = None
    # When False, the native PSARC's SNG is built with a single full-chart level
    # (no Dynamic Difficulty) — a safety valve for songs where DD misbehaves.
    dynamic_difficulty: bool = True
    # Per-arrangement tuning override, keyed by ArrangementKind.value → the six
    # MIDI pitches (low to high). An arrangement absent here keeps the tuning read
    # from its GP track. Lets the user re-tune an arrangement in the song settings
    # without touching the GP file.
    tuning_overrides: dict[str, tuple[int, int, int, int, int, int]] = field(
        default_factory=dict
    )

    def sync_for(self, kind: ArrangementKind) -> ArrangementSync:
        """Resolve the tempo/drift overrides for one arrangement, falling back
        to the job-level defaults when no per-arrangement entry exists."""
        override = self.arrangement_sync.get(kind.value)
        if override is not None:
            return override
        return ArrangementSync(
            tempo_scale=self.tempo_scale, sync_anchor_stages=self.sync_anchor_stages
        )



# Techniques that alter the in-game note sprite (chevron/"wings"); dropped when
# import_mute_techniques is False.
_MUTE_TECHNIQUES = frozenset(
    {Technique.PALM_MUTE, Technique.SLAP, Technique.POP, Technique.TAP}
)


def _build_time_warp(anchors: list[tuple[float, float]]) -> Callable[[float], float]:
    """Piecewise-linear remap built from (chart_time, corrected_time) points.

    A single anchor is a uniform shift applied everywhere (e.g. "the whole
    song's lead-in is off by X"). With two or more anchors (an excerpt drag),
    notes outside the anchor range are left untouched (identity) — only the
    excerpt between the first and last anchor is rigidly shifted/stretched;
    notes before/after it keep their original position.
    """
    if not anchors:
        return lambda t: t
    pts = sorted(anchors, key=lambda p: p[0])

    def warp(t: float) -> float:
        if len(pts) == 1:
            x0, y0 = pts[0]
            return t + (y0 - x0)
        if t < pts[0][0]:
            return t
        if t > pts[-1][0]:
            return t
        (x0, y0), (x1, y1) = next(
            (a, b) for a, b in zip(pts, pts[1:], strict=False) if a[0] <= t <= b[0]
        )
        if x1 == x0:
            return t + (y0 - x0)
        return y0 + (y1 - y0) * (t - x0) / (x1 - x0)

    return warp


def _strip_mute_techniques(p: ParsedGpTrack) -> ParsedGpTrack:
    """Return a copy of the track with palm mute / slap / pop / tap removed."""
    notes = [
        TabNote(
            string=n.string, fret=n.fret, time=n.time, sustain=n.sustain,
            techniques=frozenset(n.techniques - _MUTE_TECHNIQUES),
            bend_semitones=n.bend_semitones, slide_to_fret=n.slide_to_fret,
        )
        if n.techniques & _MUTE_TECHNIQUES else n
        for n in p.notes
    ]
    return ParsedGpTrack(
        notes=notes, tuning=p.tuning, tempo_map=p.tempo_map,
        sections=p.sections, lyrics=p.lyrics,
    )


def _warp_parsed_track(p: ParsedGpTrack, warp: Callable[[float], float]) -> ParsedGpTrack:
    """Apply a time remap to every timestamp of a parsed track (notes, beats, sections, lyrics)."""
    from rockforge.domain.music import Beat, TempoMap

    notes = [
        TabNote(
            string=n.string, fret=n.fret, time=warp(n.time),
            sustain=max(0.0, warp(n.time + n.sustain) - warp(n.time)),
            techniques=n.techniques, bend_semitones=n.bend_semitones,
            slide_to_fret=n.slide_to_fret,
        )
        for n in p.notes
    ]
    beats = tuple(Beat(time=warp(b.time), measure=b.measure) for b in p.tempo_map.beats)
    sections = [GpSection(name=s.name, start_time=warp(s.start_time)) for s in p.sections]
    lyrics = [type(line)(time=warp(line.time), text=line.text) for line in p.lyrics]
    return ParsedGpTrack(
        notes=notes,
        tuning=p.tuning,
        tempo_map=TempoMap(
            beats=beats,
            average_bpm=p.tempo_map.average_bpm,
            beats_per_measure=p.tempo_map.beats_per_measure,
        ),
        sections=sections,
        lyrics=lyrics,
    )


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
    packager: Packager

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
        pad_start_s = max(0.0, MIN_LEAD_S - spec.offset_s) + max(0.0, spec.lead_in_s)
        score_shift = spec.offset_s + pad_start_s  # max(offset_s, MIN_LEAD_S) + lead_in_s

        stage("ingest")
        raw = self.ingestor.fetch(spec.audio_source, workdir)
        stage("normalize")
        normalized = self.normalizer.normalize(raw, workdir, pad_start_s=pad_start_s)

        stage("parse_gp")
        # Explicit per-arrangement track assignment: each slot the user filled maps
        # its track to that arrangement kind, verbatim. Combo is a first-class slot,
        # not derived. Only when NOTHING is assigned do we auto-pick a sensible
        # default (lead+rhythm, or a lone track → Combined).
        slots: list[tuple[ArrangementKind, int | None]] = [
            (ArrangementKind.LEAD, spec.lead_track),
            (ArrangementKind.RHYTHM, spec.rhythm_track),
            (ArrangementKind.COMBINED, spec.combo_track),
            (ArrangementKind.ALTERNATE_LEAD, spec.alt_lead_track),
            (ArrangementKind.ALTERNATE_RHYTHM, spec.alt_rhythm_track),
        ]
        if all(idx is None for _, idx in slots):
            lead_idx, rhythm_idx = auto_pick_tracks(spec.gp_path)
            if lead_idx is None and rhythm_idx is None:
                raise IngestionError("no eligible 6-string guitar track found in the GP file")
            warnings.append(
                "tracks auto-selected by name heuristic — confirm they are the right ones"
            )
            slots = [(ArrangementKind.LEAD, lead_idx), (ArrangementKind.RHYTHM, rhythm_idx)]

        tracks: list[tuple[ArrangementKind, int]] = [
            (kind, idx) for kind, idx in slots if idx is not None
        ]
        # A lone Lead (nothing else assigned) is a single all-in-one chart →
        # Combined, the conventional single-arrangement choice.
        if len(tracks) == 1 and tracks[0][0] is ArrangementKind.LEAD:
            tracks = [(ArrangementKind.COMBINED, tracks[0][1])]
        chosen = [idx for _, idx in tracks]
        if len(chosen) != len(set(chosen)):
            raise IngestionError("each arrangement must use a different GP track")

        # Each arrangement is parsed and drift-corrected independently with its
        # own tempo_scale / sync_anchor_stages, so corrections never leak
        # between charts. The offset (and thus the shared audio lead-in) is
        # common to all of them.
        parsed: dict[ArrangementKind, ParsedGpTrack] = {}
        for kind, idx in tracks:
            sync = spec.sync_for(kind)
            p = parse_gp_track(spec.gp_path, idx, score_shift, sync.tempo_scale)
            warnings.extend(f"{kind.value}: {w}" for w in p.warnings)
            for stage_anchors in sync.sync_anchor_stages:
                if not stage_anchors:
                    continue
                p = _warp_parsed_track(p, _build_time_warp(stage_anchors))
            parsed[kind] = p

            if sync.tempo_scale != 1.0:
                warnings.append(
                    f"{kind.value}: tempo scaled by {sync.tempo_scale:.3f}× "
                    f"({1.0 / sync.tempo_scale:.1%} of the GP tempo) to match the recording"
                )
            points = sum(len(s) for s in sync.sync_anchor_stages)
            if points:
                rounds = sum(1 for s in sync.sync_anchor_stages if s)
                warnings.append(
                    f"{kind.value}: {points} manual drift-correction point(s) across "
                    f"{rounds} round(s) applied to the chart"
                )

        if not spec.import_mute_techniques:
            stripped = sum(
                1 for p in parsed.values() for n in p.notes if n.techniques & _MUTE_TECHNIQUES
            )
            parsed = {kind: _strip_mute_techniques(p) for kind, p in parsed.items()}
            if stripped:
                warnings.append(
                    f"palm mute / slap / pop / tap removed from {stripped} note(s) on request "
                    "(imported as plain notes)"
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
        def _tuning_for(kind: ArrangementKind, parsed_tuning: Tuning) -> Tuning:
            override = spec.tuning_overrides.get(kind.value)
            if override is None or len(override) != 6:
                return parsed_tuning
            return Tuning(midi=override, cent_offset=parsed_tuning.cent_offset)

        arrangements = [
            Arrangement(
                kind=kind,
                metadata=metadata,
                tuning=_tuning_for(kind, p.tuning),
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
                tones=list(spec.tones),
            )
            for kind, p in parsed.items()
        ]

        stage("lyrics")
        vocals: list[VocalEvent] = []
        lyrics_from_gp = False
        if spec.lyrics_events:
            vocals = [
                VocalEvent(time=e.time + pad_start_s, length=e.length, lyric=e.lyric)
                for e in spec.lyrics_events
            ]
            warnings.append("lyrics from the in-app editor (per-word timing) used")
        elif spec.lrc_text:
            # Lyric timestamps (LRC or UltraStar TXT) are synced to the recording as
            # supplied, so they only move by the silence we actually prepended
            # (pad_start_s) — not by the full score shift, which also absorbs the
            # score's own zero offset.
            vocals = parse_lyrics(spec.lrc_text, pad_start_s)
            if not vocals:
                warnings.append("lyrics file contained no recognizable timestamped lines")
        elif first.lyrics:
            # GP lyrics carry per-syllable note alignment implicitly: each
            # syllable lands on the next note attack. Distribute the line text
            # over the actual (already warped + offset) note onsets so the
            # timing matches what the GP file shows, rather than an even spread.
            onsets = sorted({n.time for n in first.notes})
            vocals = distribute_syllables(
                [(line.time, line.text) for line in first.lyrics], onsets
            )
            lyrics_from_gp = True
            warnings.append(
                "lyrics taken from the GP file, aligned per syllable to the note "
                "onsets (melismas — one syllable held over several notes — are not "
                "modelled and may drift until the next line)"
            )

        if pad_start_s > 0.0:
            warnings.append(
                f"sync offset was {spec.offset_s:.2f}s; added {pad_start_s:.2f}s of silence to "
                f"reach the {MIN_LEAD_S:.0f}s minimum lead-in DLC Builder needs for the "
                f"count-in. The song's first note now plays at {score_shift:.2f}s — use the "
                f"visual sync tool if the chart and audio still drift."
            )

        vocals = enforce_max_line_words(vocals)  # cap long lyric lines in-game

        stage("package")
        packaging = self.packager.package(
            arrangements,
            normalized,
            workdir / "bundle",
            vocals=vocals or None,
            cover_art=spec.cover_art,
            dynamic_difficulty=spec.dynamic_difficulty,
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
        # Surface GP-embedded lyrics to the editor/tab viewer in the recording
        # clock (un-padded): the build re-adds pad_start_s, so subtract it here
        # to round-trip correctly. Only when the lyrics actually came from the GP
        # file (not user-supplied LRC/editor rows, which the editor already has).
        gp_lyrics = (
            tuple(
                VocalEvent(time=max(0.0, v.time - pad_start_s), length=v.length, lyric=v.lyric)
                for v in vocals
            )
            if lyrics_from_gp
            else ()
        )
        return PipelineResult(
            packaging=packaging,
            note_counts={a.kind.value: len(a.notes) for a in arrangements},
            warnings=tuple(warnings),
            gp_lyrics=gp_lyrics,
        )
