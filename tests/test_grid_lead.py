"""A chart whose bar 1 comes long after the recording starts (GitHub issue #19).

The game starts a song at its first beat, so a grid that began 20 s into the
recording skipped the whole intro — a PDF whose "x19" multi-bar rest the
converter did not read, a GP file that starts at the first note. The grid is
now carried back towards the recording's start, with plain beats, so bar 1
keeps its number.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from tests.test_gp_pipeline import FakeIngestor, two_track_gp5  # noqa: F401  (fixture)
from tests.test_song_end import _WavNormalizer

from rockforge.application.gp_pipeline import GenerateFromGpUseCase, GpJobSpec
from rockforge.domain.arrangement import SongMetadata
from rockforge.domain.music import GRID_LEAD_GAP_S, Beat, TempoMap, extend_grid_back
from rockforge.infrastructure.packaging.dlcbuilder import DlcBuilderPackager


def _grid(start: float, step: float = 0.5, beats: int = 8) -> TempoMap:
    return TempoMap(
        beats=tuple(Beat(time=start + i * step, measure=(i // 4 + 1) if i % 4 == 0 else -1)
                    for i in range(beats)),
        average_bpm=120.0,
    )


def test_a_grid_that_starts_late_is_carried_back_to_the_start() -> None:
    late = _grid(20.25)
    out = extend_grid_back(late)
    assert 0.0 <= out.beats[0].time < 0.5
    times = [b.time for b in out.beats]
    steps = {round(b - a, 6) for a, b in zip(times, times[1:], strict=False)}
    assert steps == {0.5}  # the first bar's own spacing all the way back
    added = out.beats[: len(out.beats) - len(late.beats)]
    assert all(b.measure == -1 for b in added)  # plain beats: bar 1 stays bar 1
    assert out.beats[len(added):] == late.beats
    assert [b.measure for b in out.beats if b.measure > 0] == [1, 2]


def test_a_grid_that_starts_early_enough_is_left_alone() -> None:
    for start in (2.0, 5.5, GRID_LEAD_GAP_S):
        grid = _grid(start)
        assert extend_grid_back(grid) is grid


def test_a_song_whose_bar_one_is_twenty_seconds_in_starts_at_the_recordings_start(
    two_track_gp5: Path, tmp_path: Path  # noqa: F811
) -> None:
    uc = GenerateFromGpUseCase(ingestor=FakeIngestor(), normalizer=_WavNormalizer(60.0),
                               packager=DlcBuilderPackager())
    spec = GpJobSpec(gp_path=two_track_gp5, audio_source="x.wav", lead_track=0, offset_s=20.0)
    result = uc.run(spec, SongMetadata(title="T", artist="A"), tmp_path / "o")
    xml = next(p for p in result.packaging.xml_paths if p.name.startswith("arrangement_"))
    root = ET.parse(xml).getroot()
    beats = root.findall("ebeats/ebeat")
    assert float(beats[0].get("time")) < 1.0
    assert float(root.findtext("startBeat") or 99) < 1.0
    first_bar = next(b for b in beats if b.get("measure") == "1")
    assert float(first_bar.get("time")) == pytest.approx(20.0, abs=0.01)  # bar 1 where it was
    notes = sorted(float(n.get("time")) for n in root.iter("note"))
    assert notes[0] == pytest.approx(20.0, abs=0.01)  # the notes did not move
    assert any("beats were added before it" in w for w in result.warnings)

    # and the native SNG built from it passes the checker
    from rockforge.domain.arrangement import Arrangement  # noqa: F401
    from rockforge.infrastructure.packaging.psarc import sng
    from rockforge.infrastructure.packaging.psarc.verify import check_sng
    from rockforge.infrastructure.rsxml.reader import read_arrangement_xml

    arr = read_arrangement_xml(xml)
    model = sng.from_arrangement(arr)
    assert check_sng(model) == []
    assert model.metadata.start_time < 1.0
