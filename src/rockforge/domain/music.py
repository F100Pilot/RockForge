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

    def __post_init__(self) -> None:
        if not 0 <= self.string <= 5:
            raise ValueError(f"string out of range: {self.string}")
        if not 0 <= self.fret <= MAX_FRET:
            raise ValueError(f"fret out of range: {self.fret}")


SUSTAIN_GAP_S = 0.05  # small silence between a sustain's end and the next attack


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
            if na.sustain <= 0 or na.slide_to_fret is not None:
                continue
            interval = notes[b].time - notes[a].time
            if interval <= 0:
                continue
            g = min(gap, interval * 0.15)
            new_sustain = min(na.sustain, interval - g)
            if new_sustain < na.sustain:
                result[a] = replace(na, sustain=max(0.0, new_sustain))
    return result
