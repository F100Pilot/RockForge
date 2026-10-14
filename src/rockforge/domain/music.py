"""Core music domain model. Pure, deterministic, fully typed — no ML dependencies."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from enum import Enum

# Rocksmith string convention (Song2014): string 0 = lowest-pitched string.
STANDARD_E_MIDI: tuple[int, int, int, int, int, int] = (40, 45, 50, 55, 59, 64)  # E2 A2 D3 G3 B3 E4
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
    """True when a bend curve needs its points: its strength CHANGES along the
    note, or the note is already bent at the attack (a pre-bend).

    Any other curve — a single point, or a flat one that is not bent at the
    attack — is emitted as a single point at the note's end (a visible bend-up to
    the peak), the shape a decoded DLC Builder SNG uses. A flat pre-bend keeps its
    points so it is charted bent from the attack, as alphaTab plays it, instead
    of rising across the note.
    """
    eps = 1e-3
    return len({round(p.step, 3) for p in points}) > 1 or (
        bool(points) and points[0].position <= eps and points[0].step > 0
    )


def alphatab_bend(points: Sequence[BendPoint]) -> tuple[BendPoint, ...]:
    """A bend curve as alphaTab plays it (``Note.finish``, alphaTab 1.8).

    alphaTab keeps the middle point of a three-point bend only when it is a peak
    (a bend-and-release). Otherwise the bend becomes a straight line from its
    origin to its destination: "up to the middle of the note, then held" plays
    as a rise across the whole note, and the same for pre-bends and releases.
    Other point counts are returned unchanged.
    """
    if len(points) != 3:
        return tuple(points)
    origin, middle, destination = (p.step for p in points)
    if (destination > origin and middle > destination) or (
        destination == origin and middle > origin
    ):
        return tuple(points)
    return (points[0], points[2])


def is_plain_rise(points: Sequence[BendPoint]) -> bool:
    """True for a straight rise from unbent at the attack to the peak at the end.

    The chart writes it as the single-peak bend (one point at the note's end):
    the game ramps the pitch up across the note, which is that rise, without a
    bend point at the attack.
    """
    eps = 1e-3
    return (
        len(points) == 2
        and points[0].position <= eps
        and points[0].step == 0
        and points[1].position >= 1 - eps
        and points[1].step > 0
    )


def extend_through_tie(
    note: TabNote, tie_start: float, tie_end: float, tie_bend: Sequence[BendPoint] = ()
) -> TabNote:
    """``note`` held on through a tied continuation (``tie_start``..``tie_end``).

    Rocksmith has no ties, so a tie chain becomes one sustained note — but the tied
    note can carry its own bend (a note held, then bent and released: alphaTab and
    Guitar Pro draw the arrow on the tied note). Its curve joins the held note's,
    both re-timed onto the new length, instead of being dropped. A tie without a
    bend after a bent note holds that bend (the tie keeps the origin's pitch).
    ``note.sustain`` must still be the length it covers so far.
    """
    covered = note.sustain
    total = tie_end - note.time
    if total <= covered:
        return note
    held = list(note.bend_points) or (
        [BendPoint(0.0, note.bend_semitones), BendPoint(1.0, note.bend_semitones)]
        if note.bend_semitones else []
    )
    if not held and not tie_bend:
        return replace(note, sustain=total)
    curve = [(note.time + p.position * covered, p.step) for p in held] or [(note.time, 0.0)]
    if tie_bend:
        length = tie_end - tie_start
        curve += [(tie_start + p.position * length, p.step) for p in tie_bend]
    elif curve[-1][1] > 0:
        curve.append((tie_end, curve[-1][1]))
    points = [
        BendPoint(position=min(1.0, max(0.0, (t - note.time) / total)), step=step)
        for t, step in curve
    ]
    peak = max(p.step for p in points)
    return replace(
        note,
        sustain=total,
        bend_semitones=peak,
        bend_points=tuple(points) if is_composite_bend(points) else (),
        techniques=note.techniques | {Technique.BEND} if peak > 0 else note.techniques,
    )


@dataclass(frozen=True)
class Tuning:
    """Per-string MIDI pitches, low to high (Rocksmith string 0..5)."""

    midi: tuple[int, int, int, int, int, int] = STANDARD_E_MIDI
    cent_offset: float = 0.0  # deviation from A440 in cents

    def __post_init__(self) -> None:
        # Tuning was the one pitch-carrying type here with no invariant, while
        # TabNote/Beat/TempoMap all check theirs. An out-of-range value
        # therefore travelled all the way to the SNG writer, where the semitone
        # offset is packed as an int16 and a nonsense pitch died as a cryptic
        # `struct.error` with nothing pointing back at the tuning.
        if len(self.midi) != 6:
            raise ValueError(f"tuning needs 6 strings, got {len(self.midi)}")
        for string, pitch in enumerate(self.midi):
            if not 0 <= pitch <= 127:
                raise ValueError(f"tuning MIDI pitch out of range on string {string}: {pitch}")
        if not math.isfinite(self.cent_offset):
            raise ValueError(f"cent_offset must be a finite number: {self.cent_offset}")

    def offsets_from_standard(self) -> tuple[int, ...]:
        """Semitone offsets per string relative to E standard (Song2014 <tuning> format)."""
        return tuple(m - s for m, s in zip(self.midi, STANDARD_E_MIDI, strict=True))


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
                trimmed = max(0.0, new_sustain)
                result[a] = replace(
                    na, sustain=trimmed,
                    bend_points=_bend_on_shorter_note(na.bend_points, na.sustain, trimmed),
                )
    return result


def _bend_on_shorter_note(
    points: tuple[BendPoint, ...], old: float, new: float
) -> tuple[BendPoint, ...]:
    """A bend curve (positions are fractions of the sustain) kept at the same
    moments when the sustain is shortened: the bend-and-release of a note trimmed
    for the gap must not happen earlier. A point past the new end lands on it."""
    if not points or new <= 0 or old <= 0:
        return points
    scale = old / new
    return tuple(BendPoint(min(1.0, p.position * scale), p.step) for p in points)
