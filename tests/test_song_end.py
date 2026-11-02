"""Where the song ends (GitHub issue #10): the recording's end by default, or
the user's own end point ("Fim da música") — never before the last note.

The song's length used to be the last note + 1 s whatever the recording, so a
chart that rests through the outro cut the rest of the song in game.
"""

from __future__ import annotations

import wave
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from tests.test_gp_pipeline import FakeIngestor, two_track_gp5  # noqa: F401  (fixture)

from rockforge.application.gp_pipeline import GenerateFromGpUseCase, GpJobSpec
from rockforge.domain.arrangement import SongMetadata
from rockforge.infrastructure.packaging.dlcbuilder import DlcBuilderPackager

RATE = 8000


class _WavNormalizer:
    """Writes a silent WAV of ``seconds`` plus the pad, as ffmpeg would."""

    def __init__(self, seconds: float) -> None:
        self.seconds = seconds

    def normalize(self, audio: Path, workdir: Path, offset_s: float = 0.0,
                  pad_start_s: float = 0.0) -> Path:
        out = workdir / "normalized.wav"
        with wave.open(str(out), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(RATE)
            w.writeframes(b"\0\0" * int((self.seconds + pad_start_s) * RATE))
        return out


def _song_length(spec: GpJobSpec, tmp: Path, seconds: float, name: str) -> tuple[float, list[str]]:
    uc = GenerateFromGpUseCase(ingestor=FakeIngestor(), normalizer=_WavNormalizer(seconds),
                               packager=DlcBuilderPackager())
    result = uc.run(spec, SongMetadata(title="T", artist="A"), tmp / name)
    xml = next(p for p in result.packaging.xml_paths if p.name.startswith("arrangement_"))
    return float(ET.parse(xml).getroot().findtext("songLength") or 0), result.warnings


def test_the_song_lasts_until_the_recording_ends(two_track_gp5: Path, tmp_path: Path) -> None:  # noqa: F811
    # Notes end at about 3.5 s (2 s lead-in + three quarter notes); the
    # recording runs 60 s, so the game must not stop 1 s after the last note.
    spec = GpJobSpec(gp_path=two_track_gp5, audio_source="x.wav", lead_track=0)
    length, _ = _song_length(spec, tmp_path, 60.0, "a")
    assert length == pytest.approx(62.0)  # 60 s of recording + the 2 s lead-in pad


def test_the_user_can_end_the_song_earlier_but_never_before_the_last_note(
    two_track_gp5: Path, tmp_path: Path  # noqa: F811
) -> None:
    def run(end: float, name: str) -> tuple[float, list[str]]:
        spec = GpJobSpec(gp_path=two_track_gp5, audio_source="x.wav", lead_track=0,
                         song_end_s=end)
        return _song_length(spec, tmp_path, 60.0, name)

    length, warnings = run(30.0, "a")
    assert length == pytest.approx(32.0)  # recording seconds + the pad
    assert not any("song end" in w for w in warnings)
    length, warnings = run(0.5, "b")  # before the last note: 1 s after it
    assert length < 10.0
    assert any("before the last note" in w for w in warnings)
    length, warnings = run(500.0, "c")  # past the recording: with the recording
    assert length == pytest.approx(62.0)
    assert any("after the recording ends" in w for w in warnings)


def test_an_unreadable_recording_still_ends_after_the_last_note(
    two_track_gp5: Path, tmp_path: Path  # noqa: F811
) -> None:
    from tests.test_gp_pipeline import make_use_case

    spec = GpJobSpec(gp_path=two_track_gp5, audio_source="x.wav", lead_track=0)
    result = make_use_case().run(spec, SongMetadata(title="T", artist="A"), tmp_path / "w")
    xml = next(p for p in result.packaging.xml_paths if p.name.startswith("arrangement_"))
    last = max(float(n.get("time", "0")) + float(n.get("sustain", "0"))
               for n in ET.parse(xml).getroot().iter("note"))
    assert float(ET.parse(xml).getroot().findtext("songLength") or 0) == pytest.approx(last + 1.0)
