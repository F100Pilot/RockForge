"""The DLC Builder bundle must be produced even when the native .psarc build
fails (missing crypto extra, Wwise/ffmpeg, or a packing bug). No cryptography is
needed here — the .psarc step is forced to fail before it touches crypto."""

from __future__ import annotations

import json
from pathlib import Path

from rockforge.domain.arrangement import Arrangement, ArrangementKind, SongMetadata
from rockforge.domain.music import Beat, TabNote, TempoMap, Tuning
from rockforge.infrastructure.packaging.psarc.packer import NativePsarcPacker


def _arrangement() -> Arrangement:
    return Arrangement(
        kind=ArrangementKind.COMBINED,
        metadata=SongMetadata(title="Song", artist="Artist", song_length=10.0),
        tuning=Tuning(),
        tempo_map=TempoMap(
            beats=(Beat(time=0.0, measure=1), Beat(time=0.5, measure=-1)), average_bpm=120.0
        ),
        notes=[TabNote(string=0, fret=2, time=0.0, sustain=0.5)],
    )


def test_bundle_is_produced_even_if_psarc_build_raises(tmp_path: Path, monkeypatch) -> None:
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"RIFF....WAVEfmt ")
    out = tmp_path / "bundle"

    packer = NativePsarcPacker(wem_converter=None)

    def boom(*_args: object, **_kwargs: object) -> Path:
        raise RuntimeError("psarc kaboom")

    monkeypatch.setattr(packer, "_build_psarc", boom)

    result = packer.package([_arrangement()], audio, out)

    # No .psarc, but the DLC Builder-importable bundle is fully intact.
    assert result.psarc_path is None
    assert (out / "rockforge.rs2dlc").exists()
    assert (out / "arrangement_combined.xml").exists()
    project = json.loads((out / "rockforge_project.json").read_text())
    assert "psarc kaboom" in project["native_psarc_note"]
