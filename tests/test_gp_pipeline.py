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
    def normalize(
        self, audio: Path, workdir: Path, offset_s: float = 0.0, pad_start_s: float = 0.0
    ) -> Path:
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


@pytest.fixture()
def palm_muted_gp5(tmp_path: Path) -> Path:
    song = gp.Song()
    song.title, song.artist, song.tempo = "PM", "Band", 120
    lead = song.tracks[0]
    lead.name = "Lead Gtr"
    v = lead.measures[0].voices[0]
    for fret in [5, 7, 8]:
        b = gp.Beat(v)
        b.status = gp.BeatStatus.normal
        b.duration = gp.Duration(value=4)
        n = gp.Note(b)
        n.string, n.value, n.type = 1, fret, gp.NoteType.normal
        n.effect.palmMute = True
        b.notes.append(n)
        v.beats.append(b)
    path = tmp_path / "pm.gp5"
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
    # sync: first note placed at max(offset_s, MIN_LEAD_S) = 2.0 (offset_s=0.5
    # is below the 2.0s minimum lead-in, so content is pushed to 2.0)
    first = root.find("levels/level/notes/note")
    assert first is not None and float(first.get("time", "0")) == pytest.approx(2.0)

    rhythm_xml = next(p for p in result.packaging.xml_paths if p.name == "arrangement_rhythm.xml")
    r = ET.parse(rhythm_xml).getroot()
    assert len(r.findall("levels/level/chords/chord")) == 1  # whole-note chord

    vocals_xml = next(p for p in result.packaging.xml_paths if p.name == "arrangement_vocals.xml")
    v = ET.parse(vocals_xml).getroot()
    # LRC shifts only by the prepended silence (pad = 2.0 - 0.5 = 1.5): 1.0 + 1.5
    assert float(v.findall("vocal")[0].get("time", "0")) == pytest.approx(2.5)


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


def test_gp_pipeline_sync_anchors_shift_notes(two_track_gp5: Path, tmp_path: Path) -> None:
    # offset_s=0 -> score_shift=2.0 (MIN_LEAD_S); notes land at 2.0, 2.5, 3.0.
    # A single anchor (2.5 -> 3.0) is a uniform +0.5s shift applied everywhere.
    spec = GpJobSpec(
        gp_path=two_track_gp5, audio_source="x.wav", lead_track=0,
        sync_anchor_stages=[[(2.5, 3.0)]],
    )
    result = make_use_case().run(spec, SongMetadata(title="T", artist="A"), tmp_path / "w")
    assert any("1 manual drift-correction point(s) across 1 round(s)" in w for w in result.warnings)

    lead_xml = next(p for p in result.packaging.xml_paths if p.name == "arrangement_combined.xml")
    times = [float(n.get("time", "0")) for n in ET.parse(lead_xml).getroot().findall(".//note")]
    assert times == pytest.approx([2.5, 3.0, 3.5])


def test_build_time_warp_leaves_notes_outside_excerpt_untouched() -> None:
    # Two-anchor (excerpt) correction: notes between the anchors are rigidly
    # shifted/stretched, but notes before/after the excerpt must NOT move at
    # all — dragging an excerpt corrects only that excerpt.
    from rockforge.application.gp_pipeline import _build_time_warp

    warp = _build_time_warp([(10.0, 11.0), (12.0, 12.5)])
    assert warp(10.0) == pytest.approx(11.0)
    assert warp(12.0) == pytest.approx(12.5)
    assert warp(11.0) == pytest.approx(11.75)  # midpoint, interpolated
    assert warp(5.0) == pytest.approx(5.0)  # before: untouched
    assert warp(20.0) == pytest.approx(20.0)  # after: untouched


def test_build_time_warp_single_anchor_shifts_everything() -> None:
    # A single anchor remains a uniform shift applied everywhere (e.g. "the
    # whole song's lead-in is off by X"), unlike the two-anchor excerpt case.
    from rockforge.application.gp_pipeline import _build_time_warp

    warp = _build_time_warp([(10.0, 11.0)])
    assert warp(5.0) == pytest.approx(6.0)
    assert warp(10.0) == pytest.approx(11.0)
    assert warp(20.0) == pytest.approx(21.0)


def test_gp_pipeline_sync_anchor_stages_compose(two_track_gp5: Path, tmp_path: Path) -> None:
    # Two successive correction rounds (as would happen across separate
    # sessions) must compose: round 1 shifts everything by +0.5s, round 2
    # (applied to that already-shifted timeline) shifts by another +0.5s.
    spec = GpJobSpec(
        gp_path=two_track_gp5, audio_source="x.wav", lead_track=0,
        sync_anchor_stages=[[(2.5, 3.0)], [(3.0, 3.5)]],
    )
    result = make_use_case().run(spec, SongMetadata(title="T", artist="A"), tmp_path / "w")
    assert any("2 manual drift-correction point(s) across 2 round(s)" in w for w in result.warnings)

    lead_xml = next(p for p in result.packaging.xml_paths if p.name == "arrangement_combined.xml")
    times = [float(n.get("time", "0")) for n in ET.parse(lead_xml).getroot().findall(".//note")]
    assert times == pytest.approx([3.0, 3.5, 4.0])


def test_gp_pipeline_strips_mute_techniques_when_disabled(
    palm_muted_gp5: Path, tmp_path: Path
) -> None:
    spec = GpJobSpec(
        gp_path=palm_muted_gp5, audio_source="x.wav", lead_track=0,
        import_mute_techniques=False,
    )
    result = make_use_case().run(spec, SongMetadata(title="T", artist="A"), tmp_path / "w")
    assert any("palm mute" in w and "removed" in w for w in result.warnings)
    lead_xml = next(p for p in result.packaging.xml_paths if p.name == "arrangement_combined.xml")
    notes = ET.parse(lead_xml).getroot().findall(".//note")
    # stripped notes carry no palmMute flag at all (default-valued attributes
    # are omitted, matching Editor on Fire's minimal note output)
    assert notes and all(n.get("palmMute") is None for n in notes)


def test_gp_pipeline_keeps_mute_techniques_by_default(
    palm_muted_gp5: Path, tmp_path: Path
) -> None:
    spec = GpJobSpec(gp_path=palm_muted_gp5, audio_source="x.wav", lead_track=0)
    result = make_use_case().run(spec, SongMetadata(title="T", artist="A"), tmp_path / "w")
    lead_xml = next(p for p in result.packaging.xml_paths if p.name == "arrangement_combined.xml")
    notes = ET.parse(lead_xml).getroot().findall(".//note")
    assert any(n.get("palmMute") == "1" for n in notes)


def test_gp_pipeline_zero_offset_warns(two_track_gp5: Path, tmp_path: Path) -> None:
    spec = GpJobSpec(gp_path=two_track_gp5, audio_source="x.wav", lead_track=0)
    result = make_use_case().run(spec, SongMetadata(title="T", artist="A"), tmp_path / "w")
    # offset 0 => silence prepended up to the minimum lead-in (avoids the
    # DLC Builder "no room for an empty phrase" crash at content time 0)
    assert any("minimum" in w and "lead-in" in w and "2.00s" in w for w in result.warnings)
    assert result.note_counts == {"Combined": 3}  # single track => combined arrangement
