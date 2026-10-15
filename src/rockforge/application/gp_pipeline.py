"""GenerateFromGpUseCase — builds the arrangements from a Guitar Pro file.

Notes/frets/techniques/tempo/sections come exactly from a GP3/GP4/GP5 file;
the recording is only normalized and packaged. Synchronization is the one thing
the GP file cannot know, so it is a single user-supplied number: offset_s = the
moment (seconds) at which the song's first note is actually heard in the
recording (negative when bar 1 comes before the recording starts, see
MIN_OFFSET_S). The score (note/beat/section times) and the GP's measure-anchored
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

import math
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from pathlib import Path

from rockforge.application.ports import (
    AudioIngestor,
    AudioNormalizer,
    Packager,
    PackagingResult,
    VocalEvent,
)
from rockforge.domain.arrangement import (
    Arrangement,
    ArrangementKind,
    ConfidenceLabel,
    Section,
    SongMetadata,
    ToneChange,
)
from rockforge.domain.errors import IngestionError
from rockforge.domain.music import (
    BASS_LOW_TUNING_LIMIT,
    TabNote,
    Technique,
    Tuning,
    apply_sustain_gap,
    resolve_links,
)
from rockforge.domain.tone import Tone
from rockforge.infrastructure.gpimport.parser import (
    GpSection,
    ParsedGpTrack,
    inspect_gp,
    parse_gp_track,
)
from rockforge.infrastructure.rsxml.vocals import (
    distribute_syllables,
    enforce_max_line_words,
    parse_lyrics,
)


@dataclass(frozen=True)
class PipelineResult:
    packaging: PackagingResult
    note_counts: dict[str, int]
    warnings: tuple[str, ...]
    # Lyrics extracted from a GP file (recording clock, i.e. un-padded), so the
    # worker can surface them in the "Letras" editor / tab viewer. Empty unless
    # GP-embedded lyrics were used (not when the user supplied LRC/editor rows).
    gp_lyrics: tuple[VocalEvent, ...] = ()
    # The notes of the track the GP lyrics are sung on, as (time, length, midi)
    # in the same recording clock — a reference the viewer can play to hear
    # where the words should fall. midi is None when the file gives no pitch.
    vocal_melody: tuple[tuple[float, float, int | None], ...] = ()
    # Whether the GP file carries lyrics at all (used or not), so the editor can
    # offer to go back to them after its own rows replaced them.
    gp_has_lyrics: bool = False

# Minimum lead-in before the first note. DLC Builder's PhraseGenerator inserts a
# count-in phrase before the arrangement content and fails ("no room for an empty
# phrase before the arrangement content starts") when content begins at time 0;
# EOF likewise advises a few seconds of silence at the start. When the user's
# sync point is below this, the shortfall is added as silence.
MIN_LEAD_S = 2.0
# Bar 1 may start BEFORE the recording (count-in bars the recording does not
# have): a negative offset_s. The lead-in pad then grows by that much, so the
# chart keeps its place against the audio (score_shift - pad_start_s == offset_s).
# Bounded like PDF-to-GP5's "Início" field.
MIN_OFFSET_S = -60.0


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
    fixing the "the BPM jumps ~50%" case where only ½/1/2 were tried
    and a 3/2 detection had no nearby octave to snap to. "Closest to 1.0" is
    measured in LOG space: ``abs(scale - 1)`` is asymmetric (a candidate an
    octave high scores 0.5, one an octave low scores 1.0), so on a genuinely
    ambiguous half/double pair it always preferred the FASTER reading — the
    "always a higher tempo, never a lower one" bias, which then compresses the
    chart. ``abs(log(scale))`` treats the two directions alike.
    ``tempo_scale = gp_bpm / effective_recording_bpm`` because the GP timeline is
    stretched/compressed to the recording's tempo (parser scales the effective BPM
    inversely). Used both for whole-song sync and for a local re-tempo from a point.
    """
    if gp_bpm <= 0 or detected_bpm <= 0:
        raise IngestionError("gp_bpm and detected_bpm must be positive to suggest a tempo")
    candidates = [detected_bpm * f for f in _TEMPO_METRICAL_FACTORS]
    best = min(candidates, key=lambda b: abs(math.log(gp_bpm / b)))
    return gp_bpm / best


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
class ArrangementTones:
    """One arrangement's own tone setup: which of the song's tones is its base,
    which four it can switch to, and where it switches — so a Lead can take a
    solo tone where the Rhythm keeps its crunch (Rocksmith's tones are per
    arrangement). The gear definitions (``GpJobSpec.tones``) stay song-level."""

    tone_base: str | None = None
    tone_names: list[str] = field(default_factory=list)
    tone_changes: list[ToneChange] = field(default_factory=list)


@dataclass(frozen=True)
class NoteOverride:
    """One in-app note-editor edit: upserts a note at (time, string), or
    deletes the note already there when ``deleted`` is True (the other fields
    are then ignored). Bundle-clock time, like tone_changes/section_overrides
    — the note editor places these directly on the already-warped score, so
    no extra per-arrangement time-warp is applied to them."""

    time: float
    string: int
    fret: int = 0
    sustain: float = 0.0
    techniques: frozenset[Technique] = field(default_factory=frozenset)
    bend_semitones: float = 0.0
    slide_to_fret: int | None = None
    deleted: bool = False


# How far an edit's time may sit from the note it targets. The editor only
# ever sees times read back from the built XML, which the writer rounds to the
# millisecond (``rsxml/writer.py``), while the notes here carry the parser's
# full-precision float — so an exact (6-decimal) match silently missed about
# half of them: a deleted note stayed in the song and an edited one gained a
# twin beside it. Two notes on one string are never this close.
NOTE_OVERRIDE_MATCH_S = 0.005


def _apply_note_overrides(
    notes: list[TabNote], overrides: list[NoteOverride]
) -> list[TabNote]:
    """Merge in-app note edits on top of the GP-parsed notes.

    Keyed by (time, string) — an override either replaces the note on that
    string within ``NOTE_OVERRIDE_MATCH_S`` of its time (upsert) or removes it
    (deleted=True); with no such note, an upsert inserts a new one. A replaced
    note keeps its own exact time, so it stays in step with the notes around
    it. Not applied inside _warp_parsed_track: overrides are placed by the user
    on the ALREADY-warped score, so they land directly in the final coordinate
    space rather than needing to be warped again.
    """
    merged = list(notes)
    for ov in overrides:
        hit = min(
            (
                i for i, n in enumerate(merged)
                if n.string == ov.string and abs(n.time - ov.time) <= NOTE_OVERRIDE_MATCH_S
            ),
            key=lambda i: abs(merged[i].time - ov.time),
            default=None,
        )
        if ov.deleted:
            if hit is not None:
                del merged[hit]
            continue
        note = TabNote(
            string=ov.string,
            fret=ov.fret,
            time=merged[hit].time if hit is not None else ov.time,
            sustain=ov.sustain,
            techniques=ov.techniques,
            bend_semitones=ov.bend_semitones,
            slide_to_fret=ov.slide_to_fret,
        )
        if hit is None:
            merged.append(note)
        else:
            merged[hit] = note
    return sorted(merged, key=lambda n: (n.time, n.string))


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
    # A 4/5-string bass track → the Bass arrangement (folded onto four strings).
    bass_track: int | None = None
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
    # Per-arrangement tone setups, keyed like arrangement_sync. An arrangement
    # absent here uses the song-level tone_base / tone_names / tone_changes.
    arrangement_tones: dict[str, ArrangementTones] = field(default_factory=dict)
    # Where each bar starts in the recording, from an external source — today
    # Songsterr's human-marked per-measure video timestamps. When set, the
    # parser re-times the score onto them (relative to bar 1, so offset_s keeps
    # its meaning) before tempo_scale and the anchor stages, which then only
    # correct whatever those times got wrong. Empty = the file's own timing.
    bar_times: tuple[float, ...] = ()
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
    # MIDI pitches (low to high; four for the Bass). An arrangement absent here
    # keeps the tuning read from its GP track. Lets the user re-tune an
    # arrangement in the song settings without touching the GP file.
    tuning_overrides: dict[str, tuple[int, ...]] = field(default_factory=dict)
    # How far the recording sits from A440, in cents — the same for every chart,
    # since they share one recording. Guitar Pro files carry no such value, so
    # without this every chart said 0; the game's tuner then asked for A440 on a
    # recording that is not there. None keeps what the parser read.
    cent_offset: float | None = None
    # In-app section-editor overrides (bundle-clock times, like tone_changes —
    # no per-arrangement warp applied). When set (even to an empty list),
    # REPLACES the GP-parsed section markers for EVERY arrangement; None keeps
    # each arrangement's own GP-authored sections untouched.
    section_overrides: list[Section] | None = None
    # In-app note-editor edits, keyed by ArrangementKind.value — unlike
    # tone_changes/section_overrides these are genuinely per-arrangement (Lead
    # and Rhythm have entirely different note content), so each kind's list is
    # independent; an arrangement absent here (or with an empty list) is
    # completely unaffected. Applied AFTER parsing/warp/mute-stripping, so the
    # user always edits the FINAL note set, and a manual edit is never
    # silently stripped by import_mute_techniques=False.
    note_overrides: dict[str, list[NoteOverride]] = field(default_factory=dict)

    def tones_for(self, kind: ArrangementKind) -> ArrangementTones:
        """This arrangement's tone setup, else the song-level one."""
        own = self.arrangement_tones.get(kind.value)
        if own is not None:
            return own
        return ArrangementTones(
            tone_base=self.tone_base, tone_names=list(self.tone_names),
            tone_changes=list(self.tone_changes),
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


def _check_anchor_order(anchors: list[tuple[float, float]]) -> None:
    """Reject a round of sync anchors whose corrected times contradict their
    chart-time order (e.g. a later note anchored to an earlier recording instant
    than an earlier note) — such a pair makes ``_build_time_warp`` fold back on
    itself, warping the beat grid out of chronological order and crashing deep
    inside ``TempoMap`` with no clue which correction caused it. Two clicks of
    "Mover seguintes" that both touch the arrangement's last note (each anchoring
    it at a different moment) are the usual way to create this by accident.

    Also rejects two anchors sharing the EXACT SAME chart time but anchored to
    different recording instants: the strict ``x1 > x0`` comparison below skips
    a tied pair entirely, so that contradiction previously passed validation
    unnoticed and ``_build_time_warp`` silently picked whichever of the two
    matched first in its scan — exactly the "warped into nonsense" outcome this
    check exists to prevent.
    """
    pts = sorted(anchors, key=lambda p: p[0])
    for (x0, y0), (x1, y1) in zip(pts, pts[1:], strict=False):
        if x1 == x0:
            if y1 != y0:
                raise IngestionError(
                    "sync corrections conflict: two corrections both anchor "
                    f"chart time {x0:.2f}s, but to different recording instants "
                    f"({y0:.2f}s and {y1:.2f}s). Remove or adjust one of "
                    "these corrections (check the pending anchors list)."
                )
            continue
        if y1 < y0:
            raise IngestionError(
                "sync corrections conflict: the point at "
                f"{x1:.2f}s (chart time) is anchored to {y1:.2f}s, which is BEFORE "
                f"the point at {x0:.2f}s anchored to {y0:.2f}s — later chart time "
                "cannot land earlier in the recording. Remove or adjust one of "
                "these corrections (check the pending anchors list)."
            )


def _strip_mute_techniques(p: ParsedGpTrack) -> ParsedGpTrack:
    """Return a copy of the track with palm mute / slap / pop / tap removed."""
    notes = [
        replace(n, techniques=frozenset(n.techniques - _MUTE_TECHNIQUES))
        if n.techniques & _MUTE_TECHNIQUES else n
        for n in p.notes
    ]
    return replace(p, notes=notes)


def _warp_parsed_track(p: ParsedGpTrack, warp: Callable[[float], float]) -> ParsedGpTrack:
    """Apply a time remap to every timestamp of a parsed track (notes, beats, sections, lyrics).

    A sync correction can locally stretch the timeline (a chart interval mapped
    to a wider corrected interval): a note's warped sustain scales by that same
    local factor, which can re-inflate — or even exceed — a sustain that
    ``apply_sustain_gap`` already trimmed to a small gap at parse time (the
    "tall sustain pillars"/fused chord boxes bug, first fixed for the un-warped
    timeline in 4147d89). Re-applying the gap AFTER warping restores the
    invariant regardless of what the correction did to the local tempo.
    """
    from rockforge.domain.music import Beat, TempoMap

    # replace(), not a fresh TabNote: rebuilding it field by field silently
    # dropped every field it did not list (bend curves, fingering, pick
    # direction, unpitched slide-outs) the moment a song had a sync correction.
    notes = apply_sustain_gap([
        replace(
            n,
            time=warp(n.time),
            sustain=max(0.0, warp(n.time + n.sustain) - warp(n.time)),
        )
        for n in p.notes
    ])
    beats = tuple(Beat(time=warp(b.time), measure=b.measure) for b in p.tempo_map.beats)
    sections = [GpSection(name=s.name, start_time=warp(s.start_time)) for s in p.sections]
    lyrics = [type(line)(time=warp(line.time), text=line.text) for line in p.lyrics]
    lyric_notes = (
        tuple(replace(n, time=warp(n.time), end=warp(n.end)) for n in p.lyric_notes)
        if p.lyric_notes is not None
        else None
    )
    return replace(
        p,
        notes=notes,
        tempo_map=TempoMap(
            beats=beats,
            average_bpm=p.tempo_map.average_bpm,
            beats_per_measure=p.tempo_map.beats_per_measure,
        ),
        sections=sections,
        lyrics=lyrics,
        lyric_notes=lyric_notes,
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


def auto_pick_bass(gp_path: Path) -> int | None:
    """The bass track when the user does not choose: a 4/5-string track named
    "bass", else the only 4/5-string track (none when there are several)."""
    eligible = [
        t for t in inspect_gp(gp_path).tracks
        if not t.is_percussion and t.string_count in (4, 5)
    ]
    named = next((t.index for t in eligible if "bass" in t.name.lower()), None)
    if named is not None:
        return named
    return eligible[0].index if len(eligible) == 1 else None


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

        if spec.offset_s < MIN_OFFSET_S:
            raise IngestionError(
                f"sync offset must be >= {MIN_OFFSET_S:g} s — it is the second in the "
                "recording where bar 1 starts (negative: before the recording starts)"
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
            (ArrangementKind.BASS, spec.bass_track),
        ]
        if all(idx is None for _, idx in slots):
            lead_idx, rhythm_idx = auto_pick_tracks(spec.gp_path)
            bass_idx = auto_pick_bass(spec.gp_path)
            if lead_idx is None and rhythm_idx is None and bass_idx is None:
                raise IngestionError("no eligible guitar or bass track found in the GP file")
            warnings.append(
                "tracks auto-selected by name heuristic — confirm they are the right ones"
            )
            slots = [
                (ArrangementKind.LEAD, lead_idx),
                (ArrangementKind.RHYTHM, rhythm_idx),
                (ArrangementKind.BASS, bass_idx),
            ]

        tracks: list[tuple[ArrangementKind, int]] = [
            (kind, idx) for kind, idx in slots if idx is not None
        ]
        # A lone Lead (no other guitar chart assigned — a Bass beside it does not
        # count) is a single all-in-one chart → Combined, the conventional
        # single-arrangement choice.
        guitars = [i for i, (kind, _) in enumerate(tracks) if not kind.is_bass]
        if len(guitars) == 1 and tracks[guitars[0]][0] is ArrangementKind.LEAD:
            tracks[guitars[0]] = (ArrangementKind.COMBINED, tracks[guitars[0]][1])
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
            p = parse_gp_track(
                spec.gp_path, idx, score_shift, sync.tempo_scale, spec.bar_times or None,
                bass=kind.is_bass,
            )
            warnings.extend(f"{kind.value}: {w}" for w in p.warnings)
            for stage_anchors in sync.sync_anchor_stages:
                if not stage_anchors:
                    continue
                _check_anchor_order(stage_anchors)
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

        for kind_value, note_ov in spec.note_overrides.items():
            match = next((k for k in parsed if k.value == kind_value), None)
            if match is None or not note_ov:
                continue
            p = parsed[match]
            parsed[match] = replace(p, notes=_apply_note_overrides(p.notes, note_ov))
            warnings.append(
                f"{kind_value}: {len(note_ov)} manual note edit(s) from the in-app editor applied"
            )

        # Last, after every move a note can make (sync rounds, edits): a link
        # whose pair was separated, re-fretted or re-timed is cleared, and a
        # surviving one ends exactly where its next note starts.
        parsed = {kind: replace(p, notes=resolve_links(p.notes)) for kind, p in parsed.items()}

        stage("build_arrangements")
        # The chart the GP lyrics fall back to (when the file names no vocal
        # track): the first guitar chart, the Bass only when it is alone — the
        # viewer's lyricRefArr follows the same order.
        first = next(
            (p for k, p in parsed.items() if not k.is_bass), next(iter(parsed.values()))
        )
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
            cents = parsed_tuning.cent_offset if spec.cent_offset is None else spec.cent_offset
            if kind.is_bass:
                tuning = (
                    Tuning.for_bass(override, cents) if override is not None and len(override) == 4
                    else replace(parsed_tuning, cent_offset=cents)
                )
                if tuning.needs_low_tuning_fix():
                    # DLC Builder's I41: the game does not detect a bass's notes
                    # in a tuning this low unless written an octave up at 220 Hz.
                    warnings.append(
                        f"{kind.value}: tuning below {BASS_LOW_TUNING_LIMIT} semitones — written "
                        "an octave up at 220 Hz (DLC Builder's low-tuning fix) so the game "
                        "detects its notes"
                    )
                    tuning = tuning.with_low_tuning_fix()
                return tuning
            midi = override if override is not None and len(override) == 6 else parsed_tuning.midi
            return Tuning(midi=midi, cent_offset=cents)

        # Section-editor overrides replace the GP-parsed markers identically for
        # EVERY arrangement (job-level, like tone_changes — no per-arrangement
        # warp applied to the override times, which are already in bundle
        # clock). None keeps each arrangement's own GP-authored sections.
        # Sorted by time; the NUMBER is assigned downstream by
        # domain.number_sections (per name, 1-based) in both the XML writer and
        # the SNG builder, so it is left at the default here rather than being
        # set by position — which numbered the first Solo "2" just because an
        # Intro preceded it.
        override_sections = (
            [
                Section(name=s.name, start_time=s.start_time)
                for s in sorted(spec.section_overrides, key=lambda s: s.start_time)
            ]
            if spec.section_overrides is not None
            else None
        )

        def _sections_for(p: ParsedGpTrack) -> list[Section]:
            if override_sections is not None:
                return override_sections
            # Same as above: the number is assigned per name downstream.
            return [Section(name=s.name, start_time=s.start_time) for s in p.sections]

        arrangements = [
            Arrangement(
                kind=kind,
                metadata=metadata,
                tuning=_tuning_for(kind, p.tuning),
                tempo_map=p.tempo_map,
                notes=p.notes,
                capo=p.capo,
                sections=_sections_for(p),
                stage_confidence=dict(confidence),
                tone_base=spec.tones_for(kind).tone_base,
                tone_names=list(spec.tones_for(kind).tone_names),
                tone_changes=list(spec.tones_for(kind).tone_changes),
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
            # syllable lands on the next note attack OF THE TRACK THEY ARE SUNG
            # ON (usually a vocal track). Distribute the text over those
            # (already warped + offset) attacks, as Guitar Pro does; the charted
            # guitar's notes are only the fallback when the file does not say.
            gp_lines = [(line.time, line.text) for line in first.lyrics]
            if first.lyric_notes:
                # The vocal line also says how long each syllable is sung and
                # where it breathes (its rests), which is where phrases end.
                sung = sorted(first.lyric_notes, key=lambda n: n.time)
                vocals = distribute_syllables(
                    gp_lines,
                    [n.time for n in sung],
                    ends=[n.end for n in sung],
                    rests_before=[n.rest_before for n in sung],
                )
                source = "the track they are written on"
            else:
                vocals = distribute_syllables(gp_lines, sorted({n.time for n in first.notes}))
                source = "this chart (the file does not say which track they are sung on)"
            lyrics_from_gp = True
            warnings.append(
                f"lyrics taken from the GP file, one syllable per note of {source} "
                "(melismas — one syllable held over several notes — are not "
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
        vocal_melody = tuple(
            (max(0.0, n.time - pad_start_s), max(0.0, n.end - n.time), n.midi)
            for n in sorted(first.lyric_notes or (), key=lambda n: n.time)
        )
        return PipelineResult(
            packaging=packaging,
            note_counts={a.kind.value: len(a.notes) for a in arrangements},
            warnings=tuple(warnings),
            gp_lyrics=gp_lyrics,
            vocal_melody=vocal_melody,
            gp_has_lyrics=bool(first.lyrics),
        )
