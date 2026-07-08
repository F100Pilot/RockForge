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
    bend_semitones: float = 0.0
    slide_to_fret: int | None = None

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
