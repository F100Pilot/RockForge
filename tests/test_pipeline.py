"""Pipeline orchestration test with fake adapters (no ML dependencies)."""

from __future__ import annotations

from pathlib import Path

from rockforge.application.pipeline import GenerateCdlcUseCase
from rockforge.domain.arrangement import SongMetadata
from rockforge.domain.music import Beat, NoteEvent, TempoMap, Tuning
from rockforge.infrastructure.packaging.dlcbuilder import DlcBuilderPackager
from rockforge.infrastructure.rolesplit.heuristic import HeuristicRoleSplitter


class FakeIngestor:
    def fetch(self, source: str, workdir: Path) -> Path:
        workdir.mkdir(parents=True, exist_ok=True)
        p = workdir / "input.wav"
        p.write_bytes(b"RIFF")
        return p


class FakePassthrough:
    def normalize(self, audio: Path, workdir: Path, offset_s: float = 0.0) -> Path:
        return audio

    def separate_guitar(self, audio: Path, workdir: Path) -> Path:
        return audio


class FakeTranscriber:
    def transcribe(self, audio: Path) -> list[NoteEvent]:
        # bar 1: chords (rhythm-like); bar 2: single-note run (lead-like)
        chords = [
            NoteEvent(pitch=p, start=t, duration=0.4)
            for t in (0.0, 0.5)
            for p in (40, 47, 52)
        ]
        run = [
            NoteEvent(pitch=p, start=2.0 + i * 0.2, duration=0.15)
            for i, p in enumerate([64, 67, 69, 71])
        ]
        return chords + run


class FakeBeatTracker:
    def track(self, audio: Path) -> TempoMap:
        beats = tuple(
            Beat(time=0.5 * i, measure=(i // 4 + 1) if i % 4 == 0 else -1) for i in range(8)
        )
        return TempoMap(beats=beats, average_bpm=120.0)


class FakeTuningEstimator:
    def estimate(self, audio: Path, notes: list[NoteEvent]) -> Tuning:
        return Tuning()


def make_use_case() -> GenerateCdlcUseCase:
    fake = FakePassthrough()
    return GenerateCdlcUseCase(
        ingestor=FakeIngestor(),
        normalizer=fake,
        separator=fake,
        transcriber=FakeTranscriber(),
        beat_tracker=FakeBeatTracker(),
        tuning_estimator=FakeTuningEstimator(),
        role_splitter=HeuristicRoleSplitter(),
        packager=DlcBuilderPackager(psarc_packer_cmd=None),
    )


def test_pipeline_produces_bundle_with_all_arrangements(tmp_path: Path) -> None:
    result = make_use_case().run(
        source="whatever.wav",
        metadata=SongMetadata(title="T", artist="A"),
        workdir=tmp_path,
    )
    assert set(result.note_counts) == {"Combined", "Lead", "Rhythm"}
    assert result.note_counts["Combined"] == 10
    assert result.note_counts["Lead"] + result.note_counts["Rhythm"] == 10
    names = {p.name for p in result.packaging.xml_paths}
    assert names == {
        "arrangement_combined.xml", "arrangement_lead.xml", "arrangement_rhythm.xml"
    }
    assert (result.packaging.bundle_dir / "rockforge_project.json").exists()


def test_pipeline_writes_rs2dlc_with_all_arrangements(tmp_path: Path) -> None:
    import json

    result = make_use_case().run(
        source="whatever.wav",
        metadata=SongMetadata(title="T", artist="A"),
        workdir=tmp_path,
    )
    rs2dlc = result.packaging.bundle_dir / "rockforge.rs2dlc"
    assert rs2dlc.exists()
    project = json.loads(rs2dlc.read_text())
    xmls = {a["Fields"][0]["XML"] for a in project["Arrangements"]}
    assert xmls == {
        "arrangement_combined.xml", "arrangement_lead.xml", "arrangement_rhythm.xml"
    }


def test_pipeline_copies_cover_art_into_bundle(tmp_path: Path) -> None:
    import json

    cover = tmp_path / "cover.jpg"
    cover.write_bytes(b"\xff\xd8\xff\xe0fake")

    result = make_use_case().run(
        source="whatever.wav",
        metadata=SongMetadata(title="T", artist="A"),
        workdir=tmp_path,
        cover_art=cover,
    )
    assert (result.packaging.bundle_dir / "cover.jpg").read_bytes() == cover.read_bytes()
    project = json.loads((result.packaging.bundle_dir / "rockforge_project.json").read_text())
    assert project["cover_art"] == "cover.jpg"


def test_per_role_sources_build_lead_and_rhythm_without_split(tmp_path: Path) -> None:
    """Separate Lead/Rhythm recordings each become their own arrangement, and the
    experimental split is NOT used (no COMBINED)."""
    result = make_use_case().run(
        source="mix.wav",
        metadata=SongMetadata(title="T", artist="A"),
        workdir=tmp_path,
        lead_source="lead.wav",
        rhythm_source="rhythm.wav",
    )
    assert set(result.note_counts) == {"Lead", "Rhythm"}
    names = {p.name for p in result.packaging.xml_paths}
    assert names == {"arrangement_lead.xml", "arrangement_rhythm.xml"}
    joined = " ".join(result.warnings)
    assert "per-role transcription" in joined
    assert "EXPERIMENTAL" not in joined  # no lead/rhythm split warning


def test_per_role_skips_demucs_on_stems_by_default(tmp_path: Path) -> None:
    """Per-role stems are already isolated guitars, so separate_guitar is NOT run
    on them by default (Demucs is slow and would degrade an isolated stem)."""

    class CountingSeparator(FakePassthrough):
        calls = 0

        def separate_guitar(self, audio: Path, workdir: Path) -> Path:
            CountingSeparator.calls += 1
            return audio

    uc = make_use_case()
    uc.separator = CountingSeparator()
    result = uc.run(
        source="mix.wav",
        metadata=SongMetadata(title="T", artist="A"),
        workdir=tmp_path,
        lead_source="lead.wav",
        rhythm_source="rhythm.wav",
    )
    assert CountingSeparator.calls == 0  # no separation on the stems
    assert set(result.note_counts) == {"Lead", "Rhythm"}
    assert any("Demucs skipped" in w for w in result.warnings)


def test_per_role_single_stem_builds_only_that_arrangement(tmp_path: Path) -> None:
    result = make_use_case().run(
        source="lead.wav",
        metadata=SongMetadata(title="T", artist="A"),
        workdir=tmp_path,
        lead_source="lead.wav",
    )
    assert set(result.note_counts) == {"Lead"}


def test_pipeline_flags_experimental_split_and_missing_psarc(tmp_path: Path) -> None:
    result = make_use_case().run(
        source="x.wav", metadata=SongMetadata(title="T", artist="A"), workdir=tmp_path
    )
    assert result.packaging.psarc_path is None
    joined = " ".join(result.warnings)
    assert "EXPERIMENTAL" in joined
    assert "PSARC" in joined


def test_stage_callback_reports_all_stages(tmp_path: Path) -> None:
    seen: list[str] = []
    make_use_case().run(
        source="x.wav",
        metadata=SongMetadata(title="T", artist="A"),
        workdir=tmp_path,
        on_stage=seen.append,
    )
    assert seen == [
        "ingest", "normalize", "separate", "transcribe",
        "beat_track", "tuning", "fret_mapping", "package",
    ]


def test_tuning_override_skips_estimator(tmp_path: Path) -> None:
    drop_d = Tuning(midi=(38, 45, 50, 55, 59, 64))
    result = make_use_case().run(
        source="x.wav",
        metadata=SongMetadata(title="T", artist="A"),
        workdir=tmp_path,
        tuning_override=drop_d,
    )
    assert any("override" in w for w in result.warnings)
    import xml.etree.ElementTree as ET

    xml = next(p for p in result.packaging.xml_paths if "combined" in p.name)
    tuning_el = ET.parse(xml).getroot().find("tuning")
    assert tuning_el is not None and tuning_el.get("string0") == "-2"


def test_transcribe_lyrics_without_transcriber_warns(tmp_path: Path) -> None:
    result = make_use_case().run(
        source="x.wav",
        metadata=SongMetadata(title="T", artist="A"),
        workdir=tmp_path,
        transcribe_lyrics=True,
    )
    assert any("whisperx is not installed" in w for w in result.warnings)


def test_transcribe_lyrics_emits_vocals_xml(tmp_path: Path) -> None:
    from rockforge.infrastructure.rsxml.vocals import VocalEvent

    class FakeLyrics:
        def transcribe(self, vocals_stem: Path) -> list[VocalEvent]:
            return [VocalEvent(time=1.0, length=0.4, lyric="hello+")]

    class VocalsAwarePassthrough(FakePassthrough):
        def separate_guitar(self, audio: Path, workdir: Path) -> Path:
            stems = workdir / "stems"
            stems.mkdir(parents=True, exist_ok=True)
            (stems / "vocals.wav").write_bytes(b"RIFF")
            guitar = stems / "guitar.wav"
            guitar.write_bytes(b"RIFF")
            return guitar

    use_case = make_use_case()
    use_case.separator = VocalsAwarePassthrough()
    use_case.lyric_transcriber = FakeLyrics()
    result = use_case.run(
        source="x.wav",
        metadata=SongMetadata(title="T", artist="A"),
        workdir=tmp_path,
        transcribe_lyrics=True,
    )
    assert (result.packaging.bundle_dir / "arrangement_vocals.xml").exists()
    assert any("EXPERIMENTAL" in w and "WhisperX" in w for w in result.warnings)


def test_supplied_lyrics_events_emits_vocals_xml(tmp_path: Path) -> None:
    from rockforge.infrastructure.rsxml.vocals import VocalEvent

    use_case = make_use_case()
    result = use_case.run(
        source="x.wav",
        metadata=SongMetadata(title="T", artist="A"),
        workdir=tmp_path,
        lyrics_events=[VocalEvent(time=1.0, length=0.4, lyric="hi+")],
    )
    vocals_xml = result.packaging.bundle_dir / "arrangement_vocals.xml"
    assert vocals_xml.exists()
    import xml.etree.ElementTree as ET

    root = ET.parse(vocals_xml).getroot()
    assert root.find("vocal").get("lyric") == "hi+"  # type: ignore[union-attr]
    assert any("in-app editor" in w for w in result.warnings)


def test_ebeat_grid_covers_song_end(tmp_path: Path) -> None:
    result = make_use_case().run(
        source="x.wav", metadata=SongMetadata(title="T", artist="A"), workdir=tmp_path
    )
    import xml.etree.ElementTree as ET

    xml = next(p for p in result.packaging.xml_paths if p.name == "arrangement_combined.xml")
    root = ET.parse(xml).getroot()
    last_ebeat = float(root.findall("ebeats/ebeat")[-1].get("time", "0"))
    song_length = float(root.findtext("songLength", "0"))
    last_note = max(float(n.get("time", "0")) for n in root.findall("levels/level/notes/note"))
    assert last_ebeat >= last_note
    assert song_length >= last_note
