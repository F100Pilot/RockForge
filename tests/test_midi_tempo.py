"""SMF tempo-map parser (infrastructure/rhythm/midi_tempo.py).

Synthetic MIDI files are built byte-for-byte so the tempo/measure maths is
checked against known inputs without any MIDI dependency.
"""

from __future__ import annotations

import pytest

from rockforge.domain.errors import IngestionError
from rockforge.infrastructure.rhythm.midi_tempo import parse_midi_tempo


def _varlen(n: int) -> bytes:
    out = bytearray([n & 0x7F])
    n >>= 7
    while n:
        out.insert(0, (n & 0x7F) | 0x80)
        n >>= 7
    return bytes(out)


def _tempo(us_per_quarter: int) -> bytes:
    return b"\xFF\x51\x03" + us_per_quarter.to_bytes(3, "big")


def _timesig(num: int, den_pow: int) -> bytes:  # denominator = 2**den_pow
    return bytes([0xFF, 0x58, 0x04, num, den_pow, 24, 8])


def _smf(ppq: int, events: list[tuple[int, bytes]]) -> bytes:
    track = bytearray()
    prev = 0
    for tick, ev in sorted(events, key=lambda e: e[0]):
        track += _varlen(tick - prev) + ev
        prev = tick
    track += _varlen(0) + b"\xFF\x2F\x00"  # end of track
    header = (
        b"MThd"
        + (6).to_bytes(4, "big")
        + (0).to_bytes(2, "big")   # format 0
        + (1).to_bytes(2, "big")   # one track
        + ppq.to_bytes(2, "big")
    )
    return header + b"MTrk" + len(track).to_bytes(4, "big") + bytes(track)


def test_parses_constant_tempo_measure_times() -> None:
    # 120 BPM, 4/4, PPQ 480 → each quarter 0.5s, each measure 2.0s. A redundant
    # tempo marker at tick 3840 extends the emitted span to measure 2.
    data = _smf(480, [(0, _tempo(500_000)), (0, _timesig(4, 2)), (3840, _tempo(500_000))])
    t = parse_midi_tempo(data)
    assert t.measures[:3] == pytest.approx([0.0, 2.0, 4.0])
    assert t.beats[:5] == pytest.approx([0.0, 0.5, 1.0, 1.5, 2.0])
    assert t.average_bpm == pytest.approx(120.0, abs=0.5)


def test_follows_a_tempo_change() -> None:
    # 120 BPM for the first measure, then 240 BPM (0.25s/quarter) from tick 1920.
    data = _smf(480, [(0, _tempo(500_000)), (0, _timesig(4, 2)), (1920, _tempo(250_000))])
    t = parse_midi_tempo(data)
    # Measure 0 downbeat at 0.0, measure 1 downbeat at 2.0s.
    assert t.measures[:2] == pytest.approx([0.0, 2.0])
    # Beats after the change are half as far apart: 2.0, 2.25, 2.5, 2.75.
    assert t.beats[4:8] == pytest.approx([2.0, 2.25, 2.5, 2.75])


def test_defaults_to_120bpm_4_4_without_meta() -> None:
    # No tempo/time-sig events (only a late marker to extend the span): the SMF
    # defaults (120 BPM, 4/4) apply.
    data = _smf(480, [(3840, _timesig(4, 2))])
    t = parse_midi_tempo(data)
    assert t.measures[:2] == pytest.approx([0.0, 2.0])


def test_rejects_non_smf() -> None:
    with pytest.raises(IngestionError, match="Standard MIDI File"):
        parse_midi_tempo(b"not a midi file at all")


def test_rejects_smpte_division() -> None:
    header = (
        b"MThd" + (6).to_bytes(4, "big") + (0).to_bytes(2, "big")
        + (1).to_bytes(2, "big") + (0x8000 | 25).to_bytes(2, "big")  # SMPTE division
    )
    with pytest.raises(IngestionError, match="SMPTE"):
        parse_midi_tempo(header + b"MTrk" + (0).to_bytes(4, "big"))
