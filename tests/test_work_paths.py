"""Paths stored in the database that point into an earlier work dir (issue #6)."""

from __future__ import annotations

from pathlib import Path

from rockforge.infrastructure.work_paths import rebase


def _make(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x")
    return path


def test_a_path_into_the_old_work_dir_is_found_under_the_new_one(tmp_path: Path) -> None:
    work = tmp_path / "usb" / "RockForge"
    bundle = work / "abc123" / "bundle"
    bundle.mkdir(parents=True)
    _make(work / "gp" / "song.gp5")
    old = "/home/someone/Downloads/RockForge"
    assert rebase(f"{old}/abc123/bundle", work) == str(bundle)
    assert rebase(f"{old}/gp/song.gp5", work) == str(work / "gp" / "song.gp5")
    # a backup made on Windows, restored on another system
    assert rebase(r"C:\Users\someone\RockForge\gp\song.gp5", work) == str(work / "gp" / "song.gp5")


def test_a_path_that_exists_or_matches_nothing_is_left_alone(tmp_path: Path) -> None:
    work = tmp_path / "work"
    here = _make(tmp_path / "elsewhere" / "recording.wav")
    _make(work / "recording.wav")  # a file at the root must not catch a bare tail
    assert rebase(str(here), work) is None
    assert rebase("/old/RockForge/zzz/bundle", work) is None
    assert rebase("/old/place/recording.wav", work) is None
    assert rebase("", work) is None


def test_the_most_specific_place_wins(tmp_path: Path) -> None:
    work = tmp_path / "work"
    deep = _make(work / "job1" / "demucs_stems" / "stems" / "guitar.wav")
    _make(work / "stems" / "guitar.wav")
    assert rebase("/old/RockForge/job1/demucs_stems/stems/guitar.wav", work) == str(deep)
