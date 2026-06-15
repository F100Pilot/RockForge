import pytest

pytest.importorskip("cryptography")

from pathlib import Path

from rockforge.domain.arrangement import Arrangement, ArrangementKind, SongMetadata
from rockforge.domain.music import Beat, TabNote, TempoMap, Tuning
from rockforge.infrastructure.packaging.psarc import container
from rockforge.infrastructure.packaging.psarc.packer import NativePsarcPacker
from rockforge.infrastructure.rsxml.vocals import VocalEvent


def _arrangement(kind: ArrangementKind) -> Arrangement:
    return Arrangement(
        kind=kind,
        metadata=SongMetadata(title="Song", artist="Artist", song_length=10.0),
        tuning=Tuning(),
        tempo_map=TempoMap(
            beats=(Beat(time=0.0, measure=1), Beat(time=0.5, measure=-1)), average_bpm=120.0
        ),
        notes=[TabNote(string=0, fret=2, time=0.0, sustain=0.5)],
    )


def test_package_produces_valid_psarc(tmp_path: Path) -> None:
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"RIFF....WAVEfmt ")

    packer = NativePsarcPacker(wem_converter=None)
    result = packer.package(
        [_arrangement(ArrangementKind.COMBINED)],
        audio,
        tmp_path / "bundle",
        vocals=[VocalEvent(time=1.0, length=0.5, lyric="hi+")],
    )

    assert result.psarc_path is not None
    assert result.psarc_path.exists()
    assert result.wem_path is None
    assert len(result.xml_paths) == 2  # arrangement + vocals

    entries = container.unpack(result.psarc_path.read_bytes())
    assert any(name.endswith(".sng") for name in entries)
    assert any(name.startswith("audio/") for name in entries)
    assert any(name.endswith(".hsan") for name in entries)


def test_package_keeps_dlc_builder_importable_project(tmp_path: Path) -> None:
    """Native mode must still emit the DLC Builder-importable bundle (the zip)."""
    import json

    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"RIFF....WAVEfmt ")

    packer = NativePsarcPacker(wem_converter=None)
    result = packer.package(
        [_arrangement(ArrangementKind.COMBINED)], audio, tmp_path / "bundle"
    )

    project = json.loads((result.bundle_dir / "rockforge_project.json").read_text())
    # DLC Builder import fields preserved...
    assert project["audio"] == "audio.wav"
    assert project["arrangements"] == ["arrangement_combined.xml"]
    assert "stage_confidence" in project
    assert "DLC Builder" in project["note"]
    # ...plus the native PSARC reference.
    assert project["psarc"] == result.psarc_path.name
    assert project["song_key"]


def test_package_copies_cover_art(tmp_path: Path) -> None:
    import json

    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"RIFF....WAVEfmt ")
    cover = tmp_path / "cover.png"
    cover.write_bytes(b"\x89PNG\r\n\x1a\n")

    packer = NativePsarcPacker(wem_converter=None)
    result = packer.package(
        [_arrangement(ArrangementKind.COMBINED)],
        audio,
        tmp_path / "bundle",
        cover_art=cover,
    )

    assert (result.bundle_dir / "cover.png").read_bytes() == cover.read_bytes()
    project = json.loads((result.bundle_dir / "rockforge_project.json").read_text())
    assert project["cover_art"] == "cover.png"
    assert "cover_art_note" in project


def test_package_requires_psarc_extra(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import builtins

    real_import = builtins.__import__

    def fake_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "rockforge.infrastructure.packaging.psarc.crypto":
            raise ImportError("no cryptography")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"RIFF....WAVEfmt ")

    packer = NativePsarcPacker(wem_converter=None)
    from rockforge.domain.errors import PackagingError

    with pytest.raises(PackagingError, match="psarc"):
        packer.package([_arrangement(ArrangementKind.COMBINED)], audio, tmp_path / "bundle")
