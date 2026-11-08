"""An invented song to learn syncing on ("Projeto de exemplo").

"Even though there's a user guide and a video it still not easy to operate"
(r/rocksmith, 2026-11-08). A tutorial needs a song whose tab and recording
disagree in KNOWN ways, so each step of the sync guide has something to fix and
a number to check it against. No real song can ship with the app, so both are
made here: a Guitar Pro 5 riff written with PyGuitarPro, and a "recording" of
that riff synthesized with the standard library (a plucked string, a kick on
every beat and a hi-hat on every eighth — something for "Acertar pelos ataques"
and the ear to hold on to).

What the recording does that the tab does not — the tutorial's answers:

- it starts ``RECORDING_START_S`` seconds in (the tab's bar 1 is at 0);
- it plays at ``RECORDING_BPM``, slower than the tab's ``TAB_BPM`` (step 2);
- from bar ``CHANGE_BAR`` it speeds up to ``RECORDING_BPM_LATER`` (step 3:
  "Corrigir daqui" there, or "Marcar a ouvir").

Deterministic: the same files every time, so the guide's numbers hold.
"""

from __future__ import annotations

import math
import random
import struct
import wave
from pathlib import Path

TAB_BPM = 100
RECORDING_START_S = 2.0
RECORDING_BPM = 94.0
CHANGE_BAR = 9
RECORDING_BPM_LATER = 100.0
BARS = 16
RATE = 22050
TAIL_S = 2.0

STANDARD = (64, 59, 55, 50, 45, 40)  # GP string 1 (high e) … 6 (low E)

# Four bars of (GP string, fret, quarters), played four times: three of eighths,
# one of quarters.
def _eighths(*notes: tuple[int, int]) -> tuple[tuple[int, int, float], ...]:
    return tuple((string, fret, 0.5) for string, fret in notes)


_RIFF: tuple[tuple[tuple[int, int, float], ...], ...] = (
    _eighths((6, 0), (6, 0), (6, 3), (6, 0), (6, 5), (6, 0), (6, 3), (6, 2)),
    _eighths((5, 0), (5, 0), (5, 3), (5, 0), (5, 5), (5, 3), (5, 2), (5, 0)),
    _eighths((6, 0), (6, 0), (6, 3), (6, 0), (4, 2), (4, 0), (5, 2), (5, 0)),
    ((6, 0, 1.0), (6, 3, 1.0), (5, 0, 1.0), (5, 2, 1.0)),
)


def _bars() -> list[tuple[tuple[int, int, float], ...]]:
    return [_RIFF[i % len(_RIFF)] for i in range(BARS)]


def write_example_gp5(path: Path, title: str, artist: str) -> Path:
    """The tab: one guitar track at TAB_BPM, 4/4, every bar from the riff."""
    import guitarpro as gp

    song = gp.Song()
    song.title, song.artist, song.tempo = title, artist, TAB_BPM
    while len(song.measureHeaders) < BARS:
        song.measureHeaders.append(gp.MeasureHeader(number=len(song.measureHeaders) + 1))
    for i, header in enumerate(song.measureHeaders):
        # MeasureHeader.start does not accumulate by itself.
        header.start = gp.Duration.quarterTime + i * 4 * gp.Duration.quarterTime
    track = song.tracks[0]
    track.name = "Guitarra"
    track.measures = []
    for header, bar in zip(song.measureHeaders, _bars(), strict=True):
        measure = gp.Measure(track, header)
        voice = measure.voices[0]
        voice.beats = []
        for string, fret, quarters in bar:
            beat = gp.Beat(voice)
            beat.status = gp.BeatStatus.normal
            beat.duration = gp.Duration(value=8 if quarters == .5 else 4)
            note = gp.Note(beat)
            note.string, note.value, note.type = string, fret, gp.NoteType.normal
            beat.notes.append(note)
            voice.beats.append(beat)
        track.measures.append(measure)
    gp.write(song, str(path))
    return path


def recording_time(quarter: float) -> float:
    """Where the recording plays the tab's ``quarter`` (0 = bar 1's downbeat)."""
    change = (CHANGE_BAR - 1) * 4
    if quarter <= change:
        return RECORDING_START_S + quarter * 60 / RECORDING_BPM
    return (RECORDING_START_S + change * 60 / RECORDING_BPM
            + (quarter - change) * 60 / RECORDING_BPM_LATER)


def _pluck(midi: int, seconds: float) -> list[float]:
    hz = 440 * 2 ** ((midi - 69) / 12)
    n = int(seconds * RATE)
    out = []
    for i in range(n):
        t = i / RATE
        env = math.exp(-t / 0.45) * min(1.0, t / 0.003)
        out.append(env * sum(math.sin(2 * math.pi * hz * h * t) / h for h in (1, 2, 3, 4)))
    return out


def _drum(kind: str, rng: random.Random) -> list[float]:
    if kind == "kick":
        n = int(0.18 * RATE)
        out = []
        for i in range(n):
            t = i / RATE
            hz = 55 + 60 * math.exp(-t / 0.02)  # the pitch drops like a kick's
            out.append(math.exp(-t / 0.06) * math.sin(2 * math.pi * hz * t))
        return out
    n = int(0.05 * RATE)
    return [math.exp(-i / RATE / 0.012) * (rng.random() * 2 - 1) * 0.3 for i in range(n)]


def write_example_recording(path: Path) -> Path:
    """The recording: the riff, played as the module docstring says."""
    rng = random.Random(7)
    quarters = 0.0
    events: list[tuple[float, str, int, float]] = []  # (quarter, kind, midi, quarters)
    for bar in _bars():
        for string, fret, q in bar:
            events.append((quarters, "note", STANDARD[string - 1] + fret, q))
            quarters += q
    total_q = quarters
    end = recording_time(total_q) + TAIL_S
    buf = [0.0] * int(end * RATE)
    cache: dict[tuple[int, int], list[float]] = {}

    def add(at: float, samples: list[float], gain: float) -> None:
        start = int(at * RATE)
        for i, v in enumerate(samples):
            if start + i < len(buf):
                buf[start + i] += gain * v

    for q, _kind, midi, length in events:
        t = recording_time(q)
        seconds = max(0.15, recording_time(q + length) - t)
        key = (midi, int(seconds * 100))
        if key not in cache:
            cache[key] = _pluck(midi, key[1] / 100)
        add(t, cache[key], 0.5)
    kick = _drum("kick", rng)
    for beat in range(int(total_q)):
        add(recording_time(beat), kick, 0.6)
    for eighth in range(int(total_q * 2)):
        add(recording_time(eighth / 2), _drum("hat", rng), 0.5)
    peak = max(abs(v) for v in buf) or 1.0
    ints = [round(v / peak * 0.8 * 32767) for v in buf]
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(struct.pack(f"<{len(ints)}h", *ints))
    return path
