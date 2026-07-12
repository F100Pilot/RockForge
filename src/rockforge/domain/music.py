"""Core music domain model. Pure, deterministic, fully typed — no ML dependencies."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from enum import Enum

# Rocksmith string convention (Song2014): string 0 = lowest-pitched string.
STANDARD_E_MIDI: tuple[int, ...] = (40, 45, 50, 55, 59, 64)  # E2 A2 D3 G3 B3 E4
MAX_FRET = 24


class Technique(Enum):
    """Playing techniques representable in the Song2014 note schema.

    Only BEND and SLIDE have published evidence of detectability from audio
    (and only on isolated notes — see docs/research/02-transcription.md).
    HAMMER_ON / PULL_OFF here are rule-based inferences, not model output.
    TAP/SLAP/POP/ACCENT come from the GP path (PyGuitarPro beat/note effects);
    they have no audio-based detector.
    """

    BEND = "bend"
    SLIDE = "slide"
    HAMMER_ON = "hammerOn"
    PULL_OFF = "pullOff"
    HARMONIC = "harmonic"
    PALM_MUTE = "palmMute"
    VIBRATO = "vibrato"
    TAP = "tap"
    SLAP = "slap"
    POP = "pluck"
    ACCENT = "accent"
    FRET_MUTE = "mute"  # fret-hand mute / dead note (the "X" in tab)
    PINCH_HARMONIC = "pinchHarmonic"  # artificial/pinch harmonic (distinct glyph)
    TREMOLO = "tremolo"  # tremolo picking (rapid repick)
    LET_RING = "letRing"  # note is left to ring into the following notes


@dataclass(frozen=True)
class BendPoint:
    """One point on a note's bend curve.

    ``position`` is a fraction (0..1) of the note's duration; ``step`` is the
    bend amount in half-steps at that instant (0 = unbent). A single-point curve
    is a bend that reaches ``step`` at ``position``; multiple points describe
    pre-bends, releases and bend-and-hold shapes.
    """

    position: float
    step: float


def expand_slide_ins(
    notes: Sequence[TabNote],
    *,
    min_room: float = 0.05,
    max_dt: float = 0.12,
    max_scoop_frets: int = 5,
) -> list[TabNote]:
    """Turn ``slide_in_from`` scoops into real slides.

    A GP "slide into" a note (from below/above) has no source note — it's a
    flourish. Rocksmith has no slide-in attribute either (only slideTo out to a
    fret), so we represent it the way real charts do, in one of two ways per note:

    - **Room before it** (no note crowding the attack): insert a short lead-in
      note a few frets away that slides INTO the target, ending at its attack.
    - **A note immediately precedes it** on the string (a dense lick): make THAT
      note slide into the target instead — no extra note — provided it isn't
      already sliding and is within a few frets (so the slide reads as a scoop,
      not a huge jump).

    If neither fits (a big pitch jump with no room), the note is left plain — the
    honest limit, since Rocksmith can't show a free-floating scoop there. The
    marker is cleared on the target either way.
    """
    by_string: dict[int, list[int]] = {}
    for i, n in enumerate(notes):
        by_string.setdefault(n.string, []).append(i)
    result = list(notes)
    lead_ins: list[TabNote] = []
    for idxs in by_string.values():
        idxs.sort(key=lambda i: notes[i].time)
        for pos, i in enumerate(idxs):
            n = result[i]
            if n.slide_in_from is None:
                continue
            result[i] = replace(n, slide_in_from=None)
            source = n.slide_in_from
            prev_i = idxs[pos - 1] if pos > 0 else None
            prev_end = (notes[prev_i].time + notes[prev_i].sustain
                        if prev_i is not None else float("-inf"))
            room = n.time - prev_end
            if room > min_room and source != n.fret:
                dt = min(max_dt, room * 0.8)
                lead_ins.append(TabNote(
                    string=n.string, fret=source, time=n.time - dt, sustain=dt,
                    techniques=frozenset({Technique.SLIDE}), slide_to_fret=n.fret,
                ))
            elif prev_i is not None:
                p = result[prev_i]
                if (p.slide_to_fret is None and p.slide_unpitch_to is None
                        and p.fret != n.fret and abs(p.fret - n.fret) <= max_scoop_frets):
                    result[prev_i] = replace(
                        p,
                        techniques=p.techniques | {Technique.SLIDE},
                        slide_to_fret=n.fret,
                        sustain=max(p.sustain, n.time - p.time),
                    )
    out = result + lead_ins
    out.sort(key=lambda x: (x.time, x.string))
    return out


def expand_trills(notes: Sequence[TabNote], *, period: float = 0.06) -> list[TabNote]:
    """Expand ``trill_fret`` notes into the alternating hammer-on/pull-off burst
    Rocksmith uses to render a trill (it has no trill attribute).

    Each trill note becomes a run alternating between its own fret and the trill
    fret across its sustain, one step every ``period`` seconds (2–24 steps). The
    first step is the picked attack; each later step is a hammer-on (to a higher
    fret) or pull-off (to a lower one), so the game plays it legato.
    """
    out: list[TabNote] = []
    for n in notes:
        if n.trill_fret is None or n.sustain <= 0 or not 0 <= n.trill_fret <= MAX_FRET:
            out.append(replace(n, trill_fret=None) if n.trill_fret is not None else n)
            continue
        steps = max(2, min(24, round(n.sustain / period)))
        dt = n.sustain / steps
        for k in range(steps):
            fret = n.fret if k % 2 == 0 else n.trill_fret
            if k == 0:
                techs = frozenset(n.techniques - {Technique.HAMMER_ON, Technique.PULL_OFF})
            else:
                prev = n.fret if (k - 1) % 2 == 0 else n.trill_fret
                techs = frozenset({Technique.HAMMER_ON if fret > prev else Technique.PULL_OFF})
            out.append(TabNote(
                string=n.string, fret=fret, time=n.time + k * dt, sustain=dt,
                techniques=techs,
            ))
    out.sort(key=lambda x: (x.time, x.string))
    return out


def is_composite_bend(points: Sequence[BendPoint]) -> bool:
    """True when a bend curve's strength actually CHANGES along the note.

    A curve whose step is constant — a plain hold, including a flat pre-bend held
    at one value — carries no extra shape: it is emitted as a single point at the
    note's end (a visible bend-up to the peak), the shape a decoded DLC Builder
    SNG uses and the one verified safe in game. Only a genuine bend-and-release or
    multi-step curve (two or more distinct strengths) needs the full multi-point
    curve. Keeping flat bends single-point also avoids a bend point at the note's
    exact attack, which is the fragile case.
    """
    return len({round(p.step, 3) for p in points}) > 1


@dataclass(frozen=True)
class Tuning:
    """Per-string MIDI pitches, low to high (Rocksmith string 0..5)."""

    midi: tuple[int, int, int, int, int, int] = (40, 45, 50, 55, 59, 64)
    cent_offset: float = 0.0  # deviation from A440 in cents

    def offsets_from_standard(self) -> tuple[int, ...]:
        """Semitone offsets per string relative to E standard (Song2014 <tuning> format)."""
        return tuple(m - s for m, s in zip(self.midi, STANDARD_E_MIDI, strict=True))

    def candidate_positions(self, pitch: int) -> list[tuple[int, int]]:
        """All playable (string, fret) pairs for a MIDI pitch."""
        out: list[tuple[int, int]] = []
        for string, open_pitch in enumerate(self.midi):
            fret = pitch - open_pitch
            if 0 <= fret <= MAX_FRET:
                out.append((string, fret))
        return out


@dataclass(frozen=True)
class NoteEvent:
    """A transcribed note, before string/fret assignment."""

    pitch: int  # MIDI
    start: float  # seconds
    duration: float  # seconds
    confidence: float = 1.0
    bend_semitones: float = 0.0

    def __post_init__(self) -> None:
        if not 0 <= self.pitch <= 127:
            raise ValueError(f"MIDI pitch out of range: {self.pitch}")
        if self.duration < 0 or self.start < 0:
            raise ValueError("start/duration must be non-negative")


MIN_NOTE_DURATION_S = 0.04  # shorter transcribed notes are fragments/noise
MERGE_GAP_S = 0.03  # same-pitch notes within this gap are one fragmented note


@dataclass(frozen=True)
class TranscriptionCleanup:
    """Result of :func:`clean_transcription` — the kept notes plus drop counts,
    so the pipeline can surface ONE aggregated warning instead of one per note."""

    notes: list[NoteEvent]
    dropped_out_of_range: int
    dropped_too_short: int
    merged_fragments: int


def clean_transcription(
    notes: list[NoteEvent],
    tuning: Tuning,
    min_duration: float = MIN_NOTE_DURATION_S,
    merge_gap: float = MERGE_GAP_S,
) -> TranscriptionCleanup:
    """Remove notes a polyphonic transcriber (Basic Pitch) spuriously emits on a
    full electric-guitar mix, BEFORE fret mapping:

    - **Out of range for the tuning:** below the lowest open string or above the
      highest string's 24th fret. On a distorted mix Basic Pitch reports many
      sub-harmonic ghosts below low E (MIDI 37-39 in standard tuning) and octave
      harmonics far above the neck — all unplayable, and each otherwise triggers
      a separate "dropped unplayable note" warning from the mapper.
    - **Too short:** fragments under ``min_duration`` are detector noise.
    - **Fragmented sustains:** a held note split into several same-pitch segments
      with tiny gaps is merged back into one (keeps the earliest onset, extends
      to the last segment's end, keeps the highest confidence).

    Honest: this only prunes clearly-spurious/unplayable notes and re-joins
    fragments; it never invents notes or octave-shifts (a note detected an octave
    off is dropped, not silently 'corrected').
    """
    lo = min(tuning.midi)
    hi = max(tuning.midi) + MAX_FRET
    kept: list[NoteEvent] = []
    dropped_range = dropped_short = 0
    for n in notes:
        if not (lo <= n.pitch <= hi):
            dropped_range += 1
            continue
        if n.duration < min_duration:
            dropped_short += 1
            continue
        kept.append(n)

    # Merge same-pitch fragments (sort by pitch then time; join near-adjacent).
    kept.sort(key=lambda n: (n.pitch, n.start))
    merged: list[NoteEvent] = []
    merged_count = 0
    for n in kept:
        if merged and merged[-1].pitch == n.pitch:
            prev = merged[-1]
            prev_end = prev.start + prev.duration
            if n.start <= prev_end + merge_gap:
                new_end = max(prev_end, n.start + n.duration)
                merged[-1] = replace(
                    prev,
                    duration=new_end - prev.start,
                    confidence=max(prev.confidence, n.confidence),
                    bend_semitones=prev.bend_semitones or n.bend_semitones,
                )
                merged_count += 1
                continue
        merged.append(n)
    merged.sort(key=lambda n: (n.start, n.pitch))
    return TranscriptionCleanup(
        notes=merged,
        dropped_out_of_range=dropped_range,
        dropped_too_short=dropped_short,
        merged_fragments=merged_count,
    )


@dataclass(frozen=True)
class Beat:
    time: float
    measure: int  # measure number; -1 when not a downbeat (ebeat convention)


@dataclass(frozen=True)
class TempoMap:
    """Beat grid for the song. Rocksmith consumes explicit ebeats, not a fixed BPM."""

    beats: tuple[Beat, ...]
    average_bpm: float
    beats_per_measure: int = 4  # time-signature detection is weak (see report); default flagged

    def __post_init__(self) -> None:
        if self.average_bpm <= 0:
            raise ValueError("average_bpm must be positive")
        times = [b.time for b in self.beats]
        if times != sorted(times):
            raise ValueError("beats must be in chronological order")


@dataclass(frozen=True)
class TabNote:
    """A note placed on the fretboard."""

    string: int  # 0 = lowest string
    fret: int
    time: float
    sustain: float
    techniques: frozenset[Technique] = field(default_factory=frozenset)
    bend_semitones: float = 0.0  # peak of the bend (half-steps); 0 = no bend
    slide_to_fret: int | None = None
    slide_unpitch_to: int | None = None  # target fret of an unpitched slide-out
    bend_points: tuple[BendPoint, ...] = ()  # full bend curve; empty = single peak
    left_hand: int = -1  # fretting finger (0-4), -1 = unspecified
    pick_direction: int = 0  # 0 = unspecified, 1 = down, 2 = up
    slide_in_from: int | None = None  # scoop: fret a slide-into starts from
    trill_fret: int | None = None  # trill: fret to rapidly alternate with

    def __post_init__(self) -> None:
        if not 0 <= self.string <= 5:
            raise ValueError(f"string out of range: {self.string}")
        if not 0 <= self.fret <= MAX_FRET:
            raise ValueError(f"fret out of range: {self.fret}")


SUSTAIN_GAP_S = 0.05  # small silence between a sustain's end and the next attack

# A chord repeated within this gap of an identical chord is "high density": the
# game draws it condensed (a small strum marker) instead of a full chord box.
HIGH_DENSITY_MAX_GAP_S = 0.35


def _chord_shape(group: Sequence[TabNote]) -> frozenset[tuple[int, int]]:
    return frozenset((n.string, n.fret) for n in group)


def high_density_flags(
    chord_groups: Sequence[Sequence[TabNote]], max_gap: float = HIGH_DENSITY_MAX_GAP_S
) -> list[bool]:
    """Mark repeated identical chords (every one after the first in a fast run) as
    high density, so Rocksmith renders them condensed.

    A fast repeated strum — e.g. an 8th-note power-chord chug — otherwise emits a
    full chord box per hit; stacked back-to-back on the highway those sprites
    overlap into a corrupt lateral blur (NOT a sustain trail). Real charts (and
    DLC Builder's DDC) condense the repeats via the ``highDensity`` flag; the
    first hit of a run stays low density so its shape is still shown.

    ``chord_groups`` must be in time order (as produced by ``_group_chords``).
    A run is broken by a different chord shape or a gap wider than ``max_gap``.
    """
    flags = [False] * len(chord_groups)
    for i in range(1, len(chord_groups)):
        prev, cur = chord_groups[i - 1], chord_groups[i]
        if not prev or not cur:
            continue
        if cur[0].time - prev[0].time <= max_gap and _chord_shape(prev) == _chord_shape(cur):
            flags[i] = True
    return flags


def apply_sustain_gap(
    notes: Sequence[TabNote], gap: float = SUSTAIN_GAP_S
) -> list[TabNote]:
    """Trim each note's sustain so it ends a small gap before the NEXT note on the
    same string.

    A GP note's duration usually fills the whole beat, so consecutive notes'
    sustains run right into the following attack — on the Rocksmith highway the
    sustain trail touches the next note with no separation. Leaving a small gap
    both matches how real charts are authored and reads cleaner graphically.

    Only trims, never extends; the gap shrinks for closely-spaced notes (never
    more than 15% of the interval) so fast passages keep most of their length.
    Shift/legato slide notes (``slide_to_fret`` set) are left untouched — their
    sustain must reach the slide's landing note.
    """
    by_string: dict[int, list[int]] = {}
    for i, n in enumerate(notes):
        by_string.setdefault(n.string, []).append(i)
    result = list(notes)
    for idxs in by_string.values():
        idxs.sort(key=lambda i: notes[i].time)
        for a, b in zip(idxs, idxs[1:], strict=False):
            na = result[a]
            if (na.sustain <= 0 or na.slide_to_fret is not None
                    or Technique.LET_RING in na.techniques):
                continue
            interval = notes[b].time - notes[a].time
            if interval <= 0:
                continue
            g = min(gap, interval * 0.15)
            new_sustain = min(na.sustain, interval - g)
            if new_sustain < na.sustain:
                result[a] = replace(na, sustain=max(0.0, new_sustain))
    return result
