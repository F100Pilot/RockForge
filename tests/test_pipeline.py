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
    def normalize(self, audio: Path, workdir: Path) -> Path:
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
