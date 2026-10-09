"""A small Standard MIDI File reader/writer — notes and tempo only.

Every transcriber hands back a .mid; this reads one without adding a
dependency (mido/pretty_midi are not RockForge dependencies).
"""

from __future__ import annotations

import struct
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

DRUM_CHANNEL = 9
GUITAR_PROGRAMS = range(24, 32)  # General MIDI: acoustic ... guitar harmonics


@dataclass(frozen=True)
class MidiNote:
    start: float
    end: float
    pitch: int
    velocity: int = 100
    program: int = 0
    channel: int = 0


def _varlen(data: bytes, pos: int) -> tuple[int, int]:
    value = 0
    while True:
        byte = data[pos]
        pos += 1
        value = (value << 7) | (byte & 0x7F)
        if not byte & 0x80:
            return value, pos


def read_midi(path: Path) -> list[MidiNote]:
    return parse_midi(path.read_bytes())


def parse_midi(data: bytes) -> list[MidiNote]:
    if data[:4] != b"MThd":
        raise ValueError("not a MIDI file")
    hlen = struct.unpack(">I", data[4:8])[0]
    _fmt, ntracks, division = struct.unpack(">HHH", data[8:14])
    pos = 8 + hlen
    tempos: list[tuple[int, int]] = []  # (tick, microseconds per quarter)
    raw: list[tuple[int, int, int, int, int, int]] = []  # start, end, pitch, vel, prog, ch
    for _ in range(ntracks):
        if data[pos:pos + 4] != b"MTrk":
            raise ValueError("malformed MIDI track")
        length = struct.unpack(">I", data[pos + 4:pos + 8])[0]
        pos += 8
        end = pos + length
        tick, status = 0, 0
        programs = [0] * 16
        open_notes: dict[tuple[int, int], list[tuple[int, int, int]]] = {}
        while pos < end:
            delta, pos = _varlen(data, pos)
            tick += delta
            byte = data[pos]
            if byte & 0x80:
                status = byte
                pos += 1
            if status == 0xFF:
                kind = data[pos]
                size, pos = _varlen(data, pos + 1)
                if kind == 0x51 and size == 3:
                    tempos.append((tick, int.from_bytes(data[pos:pos + 3], "big")))
                pos += size
                continue
            if status in (0xF0, 0xF7):
                size, pos = _varlen(data, pos)
                pos += size
                continue
            kind, ch = status & 0xF0, status & 0x0F
            if kind in (0xC0, 0xD0):
                if kind == 0xC0:
                    programs[ch] = data[pos]
                pos += 1
                continue
            a, b = data[pos], data[pos + 1]
            pos += 2
            if kind == 0x90 and b > 0:
                open_notes.setdefault((ch, a), []).append((tick, b, programs[ch]))
            elif kind == 0x80 or (kind == 0x90 and b == 0):
                stack = open_notes.get((ch, a))
                if stack:
                    start, vel, prog = stack.pop(0)
                    raw.append((start, tick, a, vel, prog, ch))
        pos = end
    to_seconds = _clock(sorted(tempos), division)
    return sorted(
        (MidiNote(to_seconds(s), to_seconds(e), p, v, pr, c) for s, e, p, v, pr, c in raw),
        key=lambda n: (n.start, n.pitch),
    )


def _clock(tempos: list[tuple[int, int]], division: int) -> Callable[[int], float]:
    if division & 0x8000:  # SMPTE: frames per second x ticks per frame
        fps = 256 - (division >> 8)
        per_tick = 1.0 / (fps * (division & 0xFF))
        return lambda tick: tick * per_tick
    marks: list[tuple[int, float, float]] = []  # tick, seconds at tick, seconds per tick
    seconds, last_tick, per_tick = 0.0, 0, 500_000 / 1e6 / division
    for tick, uspq in tempos:
        seconds += (tick - last_tick) * per_tick
        last_tick, per_tick = tick, uspq / 1e6 / division
        marks.append((tick, seconds, per_tick))
    first = (0, 0.0, 500_000 / 1e6 / division)

    def to_seconds(tick: int) -> float:
        base = first
        for mark in marks:
            if mark[0] > tick:
                break
            base = mark
        return base[1] + (tick - base[0]) * base[2]

    return to_seconds


def guitar_notes(notes: Iterable[MidiNote]) -> list[MidiNote]:
    """The guitar part of a transcriber's output: the General MIDI guitar
    programs when the file uses them (multi-instrument models write bass,
    keys, … too), else every note that is not on the drum channel (a
    guitar-only model often leaves the program at 0)."""
    pitched = [n for n in notes if n.channel != DRUM_CHANNEL]
    guitars = [n for n in pitched if n.program in GUITAR_PROGRAMS]
    return guitars or pitched


def write_midi(tracks: Sequence[tuple[str, Sequence[MidiNote]]], path: Path) -> None:
    """One track per (name, notes), 120 BPM at 480 ticks per quarter, so a
    second is 960 ticks — for listening to the right answer in a DAW."""
    ppq = 480
    chunks = []
    for index, (name, notes) in enumerate(tracks):
        ch = index % 16 if index % 16 != DRUM_CHANNEL else 15
        events: list[tuple[int, bytes]] = []
        for n in notes:
            on = round(n.start * 2 * ppq)
            off = max(round(n.end * 2 * ppq), on + 1)
            events.append((on, bytes([0x90 | ch, n.pitch, max(1, min(127, n.velocity))])))
            events.append((off, bytes([0x80 | ch, n.pitch, 0])))
        events.sort(key=lambda e: (e[0], e[1][0] & 0xF0 == 0x90))
        body = bytearray()
        title = name.encode("utf-8")[:127]
        body += b"\x00\xff\x03" + bytes([len(title)]) + title
        body += b"\x00" + bytes([0xC0 | ch, 29])  # overdriven guitar
        if index == 0:
            body += b"\x00\xff\x51\x03" + (500_000).to_bytes(3, "big")
        last = 0
        for tick, msg in events:
            body += _encode_varlen(tick - last) + msg
            last = tick
        body += b"\x00\xff\x2f\x00"
        chunks.append(b"MTrk" + struct.pack(">I", len(body)) + bytes(body))
    header = b"MThd" + struct.pack(">IHHH", 6, 1, len(chunks), ppq)
    path.write_bytes(header + b"".join(chunks))


def _encode_varlen(value: int) -> bytes:
    out = [value & 0x7F]
    value >>= 7
    while value:
        out.append((value & 0x7F) | 0x80)
        value >>= 7
    return bytes(reversed(out))
