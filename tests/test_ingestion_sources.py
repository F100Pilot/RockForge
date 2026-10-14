"""LocalFileIngestor (the GP pipeline's recording resolver) — MIN-10.

Exercised only indirectly before; these cover the copy, the workdir creation,
and both rejection paths directly."""

from __future__ import annotations

from pathlib import Path

import pytest

from rockforge.domain.errors import IngestionError
from rockforge.infrastructure.ingestion.sources import ALLOWED_SUFFIXES, LocalFileIngestor


def test_fetch_copies_the_file_into_the_workdir(tmp_path: Path) -> None:
    src = tmp_path / "song.wav"
    src.write_bytes(b"RIFFdata")
    workdir = tmp_path / "work"  # does not exist yet

    dest = LocalFileIngestor().fetch(str(src), workdir)

    assert dest == workdir / "input.wav"
    assert dest.exists()
    assert dest.read_bytes() == b"RIFFdata"
    # The original is left in place (a copy, not a move).
    assert src.exists()


def test_fetch_creates_the_workdir_if_missing(tmp_path: Path) -> None:
    src = tmp_path / "song.mp3"
    src.write_bytes(b"ID3")
    workdir = tmp_path / "nested" / "work"

    dest = LocalFileIngestor().fetch(str(src), workdir)

    assert workdir.is_dir()
    assert dest.exists()


def test_fetch_normalises_the_suffix_to_lowercase(tmp_path: Path) -> None:
    src = tmp_path / "song.WAV"
    src.write_bytes(b"RIFF")
    dest = LocalFileIngestor().fetch(str(src), tmp_path / "work")
    assert dest.name == "input.wav"


def test_fetch_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(IngestionError, match="file not found"):
        LocalFileIngestor().fetch(str(tmp_path / "nope.wav"), tmp_path / "work")


def test_fetch_unsupported_format_raises(tmp_path: Path) -> None:
    bad = tmp_path / "song.txt"
    bad.write_bytes(b"not audio")
    with pytest.raises(IngestionError, match="unsupported format"):
        LocalFileIngestor().fetch(str(bad), tmp_path / "work")


def test_every_allowed_suffix_is_accepted(tmp_path: Path) -> None:
    for i, suffix in enumerate(sorted(ALLOWED_SUFFIXES)):
        src = tmp_path / f"song{i}{suffix}"
        src.write_bytes(b"x")
        dest = LocalFileIngestor().fetch(str(src), tmp_path / f"work{i}")
        assert dest.name == f"input{suffix}"


def test_every_recording_the_gp8_detection_finds_can_be_built() -> None:
    """The GP8 embedded-audio detection, the upload and the build read ONE list:
    an embedded .opus used to be found, then refused by the build."""
    from rockforge.infrastructure.gpimport import gpif_parser

    assert gpif_parser._EMBEDDED_AUDIO_SUFFIXES <= ALLOWED_SUFFIXES
    for sniffed in (b"OggS", b"\x1aE\xdf\xa3", b"ID3", b"fLaC", b"RIFF\0\0\0\0WAVE"):
        suffix = gpif_parser.audio_suffix_from_bytes(sniffed + b"\0" * 12)
        assert suffix is None or suffix in ALLOWED_SUFFIXES, suffix
    assert {".opus", ".webm", ".aac"} <= ALLOWED_SUFFIXES
