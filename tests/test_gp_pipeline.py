"""End-to-end GP use case test: real parser + real packager, fake audio stages."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import guitarpro as gp
import pytest

from rockforge.application.gp_pipeline import GenerateFromGpUseCase, GpJobSpec
from rockforge.domain.arrangement import SongMetadata, ToneChange
from rockforge.infrastructure.packaging.dlcbuilder import DlcBuilderPackager


class FakeIngestor:
    def fetch(self, source: str, workdir: Path) -> Path:
        workdir.mkdir(parents=True, exist_ok=True)
        p = workdir / "input.wav"
        p.write_bytes(b"RIFF")
        return p


class FakeNormalizer:
    def normalize(self, audio: Path, workdir: Path) -> Path:
        return audio


@pytest.fixture()
def two_track_gp5(tmp_path: Path) -> Path:
    song = gp.Song()
    song.title, song.artist, song.tempo = "Two", "Tracks", 120
    lead = song.tracks[0]
    lead.name = "Lead Gtr"
    v = lead.measures[0].voices[0]
    for fret in [5, 7, 8]:
        b = gp.Beat(v)
        b.status = gp.BeatStatus.normal
        b.duration = gp.Duration(value=4)
        n = gp.Note(b)
        n.string, n.value, n.type = 1, fret, gp.NoteType.normal
        b.notes.append(n)
        v.beats.append(b)

    rhythm = gp.Track(song)
    rhythm.name = "Rhythm Gtr"
    rhythm.number = 2
    song.tracks.append(rhythm)
    v2 = rhythm.measures[0].voices[0]
    b = gp.Beat(v2)
    b.status = gp.BeatStatus.normal
    b.duration = gp.Duration(value=1)
    for string, fret in [(6, 0), (5, 2), (4, 2)]:
        n = gp.Note(b)
        n.string, n.value, n.type = string, fret, gp.NoteType.normal
        b.notes.append(n)
    v2.beats.append(b)

    path = tmp_path / "two.gp5"
    gp.write(song, str(path))
    return path


def make_use_case() -> GenerateFromGpUseCase:
    return GenerateFromGpUseCase(
        ingestor=FakeIngestor(),
        normalizer=FakeNormalizer(),
        packager=DlcBuilderPackager(),
    )


def test_gp_pipeline_full_bundle(two_track_gp5: Path, tmp_path: Path) -> None:
    spec = GpJobSpec(
        gp_path=two_track_gp5,
        audio_source="x.wav",
        lead_track=0,
        rhythm_track=1,
        offset_s=0.5,
        lrc_text="[00:01.00]hello\n[00:02.00]world\n",
        tone_base="clean",
        tone_names=["dist"],
        tone_changes=[ToneChange(time=1.0, name="dist")],
    )
    stages: list[str] = []
    result = make_use_case().run(
        spec, SongMetadata(title="Two", artist="Tracks"), tmp_path / "w", on_stage=stages.append
    )
    assert stages == ["ingest", "normalize", "parse_gp", "build_arrangements", "lyrics", "package"]
    assert result.note_counts == {"Lead": 3, "Rhythm": 3}

    names = {p.name for p in result.packaging.xml_paths}
    assert names == {"arrangement_lead.xml", "arrangement_rhythm.xml", "arrangement_vocals.xml"}

    lead_xml = next(p for p in result.packaging.xml_paths if p.name == "arrangement_lead.xml")
    root = ET.parse(lead_xml).getroot()
    assert root.findtext("tonebase") == "clean"
    assert root.findtext("tonea") == "dist"
    tone = root.find("tones/tone")
    assert tone is not None and tone.get("name") == "dist"
    # offset applied: first note at 0.5s
    first = root.find("levels/level/notes/note")
    assert first is not None and float(first.get("time", "0")) == pytest.approx(0.5)

    rhythm_xml = next(p for p in result.packaging.xml_paths if p.name == "arrangement_rhythm.xml")
    r = ET.parse(rhythm_xml).getroot()
    assert len(r.findall("levels/level/chords/chord")) == 1  # whole-note chord

    vocals_xml = next(p for p in result.packaging.xml_paths if p.name == "arrangement_vocals.xml")
    v = ET.parse(vocals_xml).getroot()
    # LRC offset applied (offset_s=0.5): 1.0 + 0.5
    assert float(v.findall("vocal")[0].get("time", "0")) == pytest.approx(1.5)


def test_gp_pipeline_auto_track_selection(two_track_gp5: Path, tmp_path: Path) -> None:
    spec = GpJobSpec(gp_path=two_track_gp5, audio_source="x.wav")
    result = make_use_case().run(spec, SongMetadata(title="T", artist="A"), tmp_path / "w")
    assert set(result.note_counts) == {"Lead", "Rhythm"}  # picked by name heuristic
    assert any("auto-selected" in w for w in result.warnings)


def test_gp_pipeline_same_track_rejected(two_track_gp5: Path, tmp_path: Path) -> None:
    from rockforge.domain.errors import IngestionError

    spec = GpJobSpec(gp_path=two_track_gp5, audio_source="x.wav", lead_track=0, rhythm_track=0)
    with pytest.raises(IngestionError, match="same GP track"):
        make_use_case().run(spec, SongMetadata(title="T", artist="A"), tmp_path / "w")


def test_gp_pipeline_zero_offset_warns(two_track_gp5: Path, tmp_path: Path) -> None:
    spec = GpJobSpec(gp_path=two_track_gp5, audio_source="x.wav", lead_track=0)
    result = make_use_case().run(spec, SongMetadata(title="T", artist="A"), tmp_path / "w")
    assert any("offset is 0.0" in w for w in result.warnings)
    assert result.note_counts == {"Combined": 3}  # single track => combined arrangement
