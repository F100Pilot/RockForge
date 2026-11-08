"""A backing track: the recording without one separated instrument
("generate a .psarc without one of the stems … a bass backing track",
r/rocksmith 2026-11-08). The stems of one separation add up to the recording,
so the song without the bass is the sum of the bass's siblings."""

from __future__ import annotations

import math
import shutil
import struct
import wave
from pathlib import Path

import pytest

from rockforge.domain.errors import SeparationError
from rockforge.infrastructure.separation.backing import backing_parts, mix_backing

RATE = 8000


def _tone(path: Path, hz: float, amp: float, seconds: float = 0.5) -> list[float]:
    """A 16-bit mono sine, returned as the floats it holds."""
    n = int(RATE * seconds)
    ints = [round(amp * 32767 * math.sin(2 * math.pi * hz * i / RATE)) for i in range(n)]
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(struct.pack(f"<{n}h", *ints))
    return [v / 32768 for v in ints]


def _float_wav(path: Path) -> list[float]:
    """The samples of a 32-bit float WAV (the stdlib's wave reads only PCM)."""
    data = path.read_bytes()
    i = 12
    while i < len(data):
        cid, size = data[i:i + 4], struct.unpack("<I", data[i + 4:i + 8])[0]
        if cid == b"data":
            body = data[i + 8:i + 8 + size]
            return list(struct.unpack(f"<{len(body) // 4}f", body))
        i += 8 + size + (size & 1)
    raise AssertionError("no data chunk")


def test_the_other_stems_of_the_same_separation_are_the_backing(tmp_path: Path) -> None:
    sep = tmp_path / "htdemucs_6s" / "song"
    sep.mkdir(parents=True)
    for name in ("bass", "drums", "guitar", "vocals"):
        (sep / f"{name}.wav").write_bytes(b"")
    (tmp_path / "other_pass.wav").write_bytes(b"")  # another folder is another separation
    assert [p.name for p in backing_parts(sep / "bass.wav")] == [
        "drums.wav", "guitar.wav", "vocals.wav",
    ]


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="needs ffmpeg")
def test_the_backing_is_the_plain_sum_of_the_other_stems(tmp_path: Path) -> None:
    sep = tmp_path / "sep"
    sep.mkdir()
    _tone(sep / "bass.wav", 110, 0.6)
    drums = _tone(sep / "drums.wav", 200, 0.5)
    guitar = _tone(sep / "guitar.wav", 330, 0.5)
    out = mix_backing(backing_parts(sep / "bass.wav"), tmp_path / "backing.wav")
    mixed = _float_wav(out)
    expected = [a + b for a, b in zip(drums, guitar, strict=True)]
    assert len(mixed) == len(expected)
    # A plain sum, not the average amix makes by default: peaks above 0 dBFS
    # stay, in float, for the build's normalizer to bring down.
    assert max(abs(m - e) for m, e in zip(mixed, expected, strict=True)) < 1e-3
    assert max(abs(m) for m in mixed) > 0.95


def test_nothing_to_put_together_is_said(tmp_path: Path) -> None:
    with pytest.raises(SeparationError):
        mix_backing([], tmp_path / "x.wav")
