"""Standard MIDI File (SMF) tempo-map reader for MIDI-driven dynamic sync.

RIPX (and any DAW) can export a MIDI whose tempo track carries the recording's
real tempo per measure — a *ground-truth* tempo curve, unlike librosa's
estimate. This reads that curve: the absolute time (seconds) of every beat and
every measure downbeat, from the SMF's tempo (FF 51) and time-signature (FF 58)
meta events. It is a deterministic, single-implementation format parser (like
the .gp parsers), so it lives in infrastructure and is imported directly — no
extra dependency (the SMF byte layout is simple enough to parse natively).

Only PPQ (ticks-per-quarter) division is supported; SMPTE-division files raise
(RIPX and virtually all DAWs export PPQ).
"""

from __future__ import annotations

from dataclasses import dataclass

from rockforge.domain.errors import IngestionError

_DEFAULT_TEMPO_US = 500_000  # 120 BPM, the SMF default before any tempo event


@dataclass(frozen=True)
class MidiTempo:
    """A recording's tempo curve read from a MIDI file.

    ``measures`` and ``beats`` are absolute times in seconds (the MIDI clock,
    which for a DAW export derived from the recording is the recording clock);
    ``average_bpm`` is the quarter-note tempo averaged over the song.
    """

    measures: list[float]
    beats: list[float]
    average_bpm: float


def _read_varlen(data: bytes, i: int) -> tuple[int, int]:
    """Read a variable-length quantity; return (value, next_index)."""
    value = 0
    for _ in range(4):  # SMF varlen is at most 4 bytes
        if i >= len(data):
            raise IngestionError("truncated MIDI file (variable-length quantity)")
        b = data[i]
        i += 1
        value = (value << 7) | (b & 0x7F)
        if not (b & 0x80):
            return value, i
    raise IngestionError("malformed MIDI variable-length quantity")


def _collect_events(data: bytes) -> tuple[int, list[tuple[int, int]], list[tuple[int, int, int]]]:
    """Parse the SMF header + tracks, returning (ppq, tempo_events,
    timesig_events) where tempo_events are (tick, us_per_quarter) and
    timesig_events are (tick, numerator, denominator), each in absolute ticks.
    """
    if data[:4] != b"MThd":
        raise IngestionError("not a Standard MIDI File (missing MThd header)")
    if len(data) < 14:
        raise IngestionError("truncated MIDI header")
    division = int.from_bytes(data[12:14], "big")
    if division & 0x8000:
        raise IngestionError(
            "SMPTE-division MIDI is not supported; export with PPQ (ticks-per-quarter) timing"
        )
    ppq = division if division > 0 else 480

    tempos: list[tuple[int, int]] = []
    timesigs: list[tuple[int, int, int]] = []
    i = 8 + int.from_bytes(data[4:8], "big")  # skip the header chunk body
    while i + 8 <= len(data):
        chunk_id = data[i : i + 4]
        length = int.from_bytes(data[i + 4 : i + 8], "big")
        body_start = i + 8
        body_end = body_start + length
        i = body_end
        if chunk_id != b"MTrk":
            continue  # skip unknown chunks
        j = body_start
        tick = 0
        status = 0
        while j < body_end:
            delta, j = _read_varlen(data, j)
            tick += delta
            if j >= body_end:
                break
            b = data[j]
            if b & 0x80:
                status = b
                j += 1
            # else: running status — reuse the previous status byte
            if status == 0xFF:  # meta event
                meta_type = data[j]
                j += 1
                mlen, j = _read_varlen(data, j)
                payload = data[j : j + mlen]
                j += mlen
                if meta_type == 0x51 and mlen == 3:  # set tempo
                    tempos.append((tick, int.from_bytes(payload, "big")))
                elif meta_type == 0x58 and mlen >= 2:  # time signature
                    timesigs.append((tick, payload[0], 1 << payload[1]))
            elif status in (0xF0, 0xF7):  # sysex — skip by its length
                slen, j = _read_varlen(data, j)
                j += slen
            elif 0x80 <= status <= 0xEF:  # channel voice message
                # Program change (0xC) and channel pressure (0xD) carry 1 data
                # byte; everything else carries 2.
                j += 1 if (status & 0xF0) in (0xC0, 0xD0) else 2
            else:
                raise IngestionError("unexpected MIDI status byte")
    return ppq, tempos, timesigs


def parse_midi_tempo(data: bytes) -> MidiTempo:
    """Read a MIDI file's tempo curve into per-beat and per-measure absolute
    times (seconds). The tempo track's set-tempo events give the seconds-per-
    tick over each span; the time-signature events give the beat unit and how
    many beats make a measure. Both default sanely (120 BPM, 4/4) when absent.
    """
    ppq, tempos, timesigs = _collect_events(data)
    tempos.sort(key=lambda e: e[0])
    timesigs.sort(key=lambda e: e[0])
    if not tempos or tempos[0][0] > 0:
        tempos.insert(0, (0, _DEFAULT_TEMPO_US))
    if not timesigs or timesigs[0][0] > 0:
        timesigs.insert(0, (0, 4, 4))

    def tick_seconds(target: int) -> float:
        """Absolute seconds at ``target`` ticks, integrating the tempo map."""
        secs = 0.0
        for idx, (tk, us) in enumerate(tempos):
            nxt = tempos[idx + 1][0] if idx + 1 < len(tempos) else None
            seg_end = target if nxt is None else min(target, nxt)
            if seg_end > tk:
                secs += (seg_end - tk) * (us / 1_000_000.0) / ppq
            if nxt is None or target <= nxt:
                break
        return secs

    # The last tick worth emitting: the furthest tempo/timesig event (the file
    # carries no note data here, so extend one measure past the last marker).
    last_tick = max(
        (tempos[-1][0], timesigs[-1][0]),
    )

    beats: list[float] = []
    measures: list[float] = []
    last_beat_tick = 0
    for idx, (tk, num, den) in enumerate(timesigs):
        span_end = timesigs[idx + 1][0] if idx + 1 < len(timesigs) else None
        beat_ticks = (4 * ppq) // den  # ticks per notated beat
        measure_ticks = beat_ticks * num
        t = tk
        # Emit through the next time-sig change, or one measure past the last
        # marker for the final (open-ended) span.
        stop = span_end if span_end is not None else last_tick + measure_ticks
        beat_in_measure = 0
        while t < stop:
            beats.append(tick_seconds(t))
            if beat_in_measure == 0:
                measures.append(tick_seconds(t))
            last_beat_tick = t
            t += beat_ticks
            beat_in_measure = (beat_in_measure + 1) % num

    if len(beats) < 2:
        raise IngestionError("MIDI file has no usable tempo/beat information")

    # Quarter-note tempo averaged over the emitted span (quarters elapsed × 60 /
    # seconds elapsed) — robust to the artificial one-measure tail extension.
    total_s = beats[-1] - beats[0]
    quarters = last_beat_tick / ppq
    average_bpm = (quarters * 60.0 / total_s) if total_s > 0 and quarters > 0 else 120.0
    return MidiTempo(measures=measures, beats=beats, average_bpm=round(average_bpm, 2))
