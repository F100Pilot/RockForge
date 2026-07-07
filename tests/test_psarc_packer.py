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


class _FakeWemConverter:
    """Stand-in for Wwise: emits a fixed .wem so the bnk path is exercised."""

    def __init__(self, wem_bytes: bytes) -> None:
        self._wem = wem_bytes

    def available(self) -> bool:
        return True

    def convert(self, wav: Path, workdir: Path) -> Path:
        workdir.mkdir(parents=True, exist_ok=True)
        out = workdir / "Audio.wem"
        out.write_bytes(self._wem)
        return out


def test_wem_available_packs_soundbank_and_stream(tmp_path: Path) -> None:
    """With Wwise, the PSARC carries a song .bnk plus the full .wem named by the
    file id the bank cross-references (so the game can fire Play_<key>)."""
    from rockforge.infrastructure.packaging.psarc import soundbank

    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"RIFF....WAVEfmt ")
    wem_bytes = b"WEMDATA\x00" * 4000

    packer = NativePsarcPacker(wem_converter=_FakeWemConverter(wem_bytes))
    result = packer.package([_arrangement(ArrangementKind.COMBINED)], audio, tmp_path / "bundle")

    assert result.wem_path is not None
    entries = container.unpack(result.psarc_path.read_bytes())
    bnk_name = next(n for n in entries if n.endswith(".bnk"))
    assert bnk_name == "audio/windows/song_artistsong.bnk"
    file_id = soundbank.read_wem_file_id(entries[bnk_name])
    assert f"audio/windows/{file_id}.wem" in entries
    assert entries[f"audio/windows/{file_id}.wem"] == wem_bytes


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


def test_vocals_get_a_separate_sng_and_manifest(tmp_path: Path) -> None:
    """Vocals must ship as their own <key>_vocals.sng + manifest, not embedded
    in an instrument SNG (real Rocksmith convention)."""
    import json

    from rockforge.infrastructure.packaging.psarc import sng
    from rockforge.infrastructure.packaging.psarc.crypto import decrypt_sng

    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"RIFF....WAVEfmt ")

    packer = NativePsarcPacker(wem_converter=None)
    result = packer.package(
        [_arrangement(ArrangementKind.COMBINED)],
        audio,
        tmp_path / "bundle",
        vocals=[VocalEvent(time=1.0, length=0.5, lyric="hi+")],
    )
    entries = container.unpack(result.psarc_path.read_bytes())

    # A dedicated vocals SNG exists and carries the vocal, while the instrument
    # SNG carries none.
    vocals_sng = next(k for k in entries if k.endswith("_vocals.sng"))
    instr_sng = next(
        k for k in entries if k.endswith(".sng") and not k.endswith("_vocals.sng")
    )
    assert sng.read_sng(decrypt_sng(entries[vocals_sng])).vocals[0].lyric == "hi+"
    assert sng.read_sng(decrypt_sng(entries[instr_sng])).vocals == []

    # A vocals manifest entry is present in the aggregated hsan.
    hsan_key = next(k for k in entries if k.endswith(".hsan"))
    hsan = json.loads(entries[hsan_key])
    types = {e["Attributes"]["ArrangementType"] for e in hsan["Entries"].values()}
    assert "Vocals" in types


def test_no_vocals_means_no_vocals_sng(tmp_path: Path) -> None:
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"RIFF....WAVEfmt ")

    packer = NativePsarcPacker(wem_converter=None)
    result = packer.package(
        [_arrangement(ArrangementKind.COMBINED)], audio, tmp_path / "bundle"
    )
    entries = container.unpack(result.psarc_path.read_bytes())
    assert not any(name.endswith("_vocals.sng") for name in entries)


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


def test_package_writes_rs2dlc_project(tmp_path: Path) -> None:
    import json

    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"RIFF....WAVEfmt ")

    packer = NativePsarcPacker(wem_converter=None)
    result = packer.package(
        [_arrangement(ArrangementKind.COMBINED)],
        audio,
        tmp_path / "bundle",
        vocals=[VocalEvent(time=1.0, length=0.5, lyric="hi+")],
    )

    rs2dlc = result.bundle_dir / "rockforge.rs2dlc"
    assert rs2dlc.exists()
    project = json.loads(rs2dlc.read_text())
    assert project["DLCKey"]
    cases = [a["Case"] for a in project["Arrangements"]]
    assert cases == ["Instrumental", "Vocals"]
    assert project["Arrangements"][0]["Fields"][0]["XML"] == "arrangement_combined.xml"


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


def test_package_degrades_without_psarc_extra(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
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
    result = packer.package([_arrangement(ArrangementKind.COMBINED)], audio, tmp_path / "bundle")
    assert result.psarc_path is None
    assert result.bundle_dir.exists()
