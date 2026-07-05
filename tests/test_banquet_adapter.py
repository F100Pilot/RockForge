"""BanquetSeparator command-construction tests — no query-bandit/torch needed.

The model never runs in CI; these assert the adapter builds the right
`inference_byoq` command per query clip, returns one stem per clip, forwards the
device, and fails clearly when the (repo / checkpoint / queries) setup is absent.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from rockforge.domain.errors import SeparationError
from rockforge.infrastructure.separation import banquet_adapter
from rockforge.infrastructure.separation.banquet_adapter import BanquetSeparator


def _setup(tmp_path: Path, queries: list[str]) -> tuple[Path, Path, Path]:
    repo = tmp_path / "query-bandit"
    repo.mkdir()
    (repo / "train.py").write_text("# fake")
    ckpt = tmp_path / "ev-pre-aug.ckpt"
    ckpt.write_bytes(b"")
    qdir = tmp_path / "queries"
    qdir.mkdir()
    for q in queries:
        (qdir / q).write_bytes(b"")
    return repo, ckpt, qdir


def _fake_run(captured: list[list[str]], make_output: bool):
    def runner(cmd, **kwargs):  # noqa: ANN001, ANN202
        captured.append(cmd)
        if make_output:
            arg = next(c for c in cmd if c.startswith("--output_path="))
            out = Path(arg.split("=", 1)[1])
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(b"")

        class _Done:
            stderr = ""

        return _Done()

    return runner


def test_separate_stems_one_pass_per_query(monkeypatch, tmp_path) -> None:
    repo, ckpt, qdir = _setup(tmp_path, ["electric_guitar.wav", "acoustic_guitar.wav", "bass.wav"])
    captured: list[list[str]] = []
    monkeypatch.setattr(banquet_adapter.subprocess, "run", _fake_run(captured, True))

    audio = tmp_path / "song.wav"
    audio.write_bytes(b"")
    sep = BanquetSeparator(repo, ckpt, qdir, device="cuda", batch_size=4)
    stems = sep.separate_stems(audio, tmp_path / "work")

    assert set(stems) == {"electric_guitar", "acoustic_guitar", "bass"}
    assert all(p.exists() for p in stems.values())
    assert len(captured) == 3
    cmd = captured[0]
    assert "inference_byoq" in cmd
    assert any(c.startswith(f"--ckpt_path={ckpt}") for c in cmd)
    assert any(c.startswith("--input_path=") for c in cmd)
    assert any(c.startswith("--query_path=") for c in cmd)
    assert "--use_cuda=true" in cmd
    assert "--batch_size=4" in cmd


def test_device_cpu_sets_use_cuda_false(monkeypatch, tmp_path) -> None:
    repo, ckpt, qdir = _setup(tmp_path, ["bass.wav"])
    captured: list[list[str]] = []
    monkeypatch.setattr(banquet_adapter.subprocess, "run", _fake_run(captured, True))

    audio = tmp_path / "song.wav"
    audio.write_bytes(b"")
    BanquetSeparator(repo, ckpt, qdir, device="cpu").separate_stems(audio, tmp_path / "work")
    assert "--use_cuda=false" in captured[0]


def test_separate_guitar_picks_a_guitar_query(monkeypatch, tmp_path) -> None:
    repo, ckpt, qdir = _setup(tmp_path, ["bass.wav", "electric_guitar.wav"])
    captured: list[list[str]] = []
    monkeypatch.setattr(banquet_adapter.subprocess, "run", _fake_run(captured, True))

    audio = tmp_path / "song.wav"
    audio.write_bytes(b"")
    out = BanquetSeparator(repo, ckpt, qdir).separate_guitar(audio, tmp_path / "work")
    assert out.name == "guitar.wav"
    assert len(captured) == 1
    assert any("electric_guitar.wav" in c for c in captured[0])


def test_missing_setup_raises(tmp_path) -> None:
    audio = tmp_path / "song.wav"
    audio.write_bytes(b"")
    # no repo/ckpt/queries configured
    with pytest.raises(SeparationError):
        BanquetSeparator(None, None, None).separate_stems(audio, tmp_path / "work")


def test_no_query_clips_raises(monkeypatch, tmp_path) -> None:
    repo, ckpt, qdir = _setup(tmp_path, [])  # empty queries dir
    audio = tmp_path / "song.wav"
    audio.write_bytes(b"")
    with pytest.raises(SeparationError):
        BanquetSeparator(repo, ckpt, qdir).separate_stems(audio, tmp_path / "work")
