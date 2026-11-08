"""The example project the tutorial walks through: an invented tab, and a
synthesized recording that starts late, plays slower and speeds up at bar 9 —
in the amounts the guide gives as the answers."""

from __future__ import annotations

import struct
import wave
from pathlib import Path

from rockforge.infrastructure import example_song as ex
from rockforge.infrastructure.gpimport.parser import inspect_gp, parse_gp_track


def _samples(path: Path) -> tuple[list[int], int]:
    with wave.open(str(path)) as w:
        rate, n = w.getframerate(), w.getnframes()
        return list(struct.unpack(f"<{n}h", w.readframes(n))), rate


def _energy(s: list[int], rate: int, at: float, ms: float) -> float:
    a = max(0, int(at * rate))
    b = int((at + ms / 1000) * rate)
    return sum(abs(v) for v in s[a:b]) / max(1, b - a)


def test_the_tab_is_the_riff_at_the_tabs_own_tempo(tmp_path: Path) -> None:
    gp5 = ex.write_example_gp5(tmp_path / "ex.gp5", "Exemplo", "RockForge")
    info = inspect_gp(gp5)
    assert (info.title, info.tempo, len(info.tracks)) == ("Exemplo", ex.TAB_BPM, 1)
    notes = parse_gp_track(gp5, 0).notes
    assert len(notes) == 112
    assert notes[0].time == 0.0
    assert round(notes[-1].time, 3) == round((ex.BARS * 4 - 1) * 60 / ex.TAB_BPM, 3)


def test_the_recording_plays_it_late_slower_and_then_faster(tmp_path: Path) -> None:
    wav = ex.write_example_recording(tmp_path / "ex.wav")
    s, rate = _samples(wav)
    assert rate == ex.RATE
    assert abs(len(s) / rate - (ex.recording_time(ex.BARS * 4) + ex.TAIL_S)) < 0.01
    assert _energy(s, rate, 0.2, 1000) == 0  # silence before the song starts
    # Every note attacks where recording_time says: before bar 9 at the slower
    # tempo, after it at the faster one (the tutorial's three answers).
    for quarter in (0, 4, 20, (ex.CHANGE_BAR - 1) * 4, 40, 60):
        t = ex.recording_time(quarter)
        assert _energy(s, rate, t, 25) > 2 * _energy(s, rate, t - 0.03, 25), quarter
    assert ex.recording_time(0) == ex.RECORDING_START_S
    assert abs(ex.recording_time(4) - ex.recording_time(0) - 4 * 60 / ex.RECORDING_BPM) < 1e-9
    late = (ex.CHANGE_BAR - 1) * 4
    assert abs(ex.recording_time(late + 4) - ex.recording_time(late)
               - 4 * 60 / ex.RECORDING_BPM_LATER) < 1e-9


def test_the_files_are_the_same_every_time(tmp_path: Path) -> None:
    a = ex.write_example_recording(tmp_path / "a.wav").read_bytes()
    b = ex.write_example_recording(tmp_path / "b.wav").read_bytes()
    assert a == b
