"""DemucsSeparator command-construction tests — no Demucs install needed.

The actual model never runs in CI; these assert that the lyric-detection path
asks for the lighter 2-stem vocals model rather than the heavy 6-source one.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from rockforge.infrastructure.separation import demucs_adapter
from rockforge.infrastructure.separation.demucs_adapter import (
    MODEL,
    VOCAL_MODEL,
    DemucsSeparator,
)


def _fake_run(captured: list[list[str]], make_output: bool):
    def runner(cmd, **kwargs):  # noqa: ANN001, ANN202
        captured.append(cmd)
        if make_output:
            # cmd is [py, patcher, -n, model, -d, dev, ..., -o, out_dir, audio]
            out_dir = Path(cmd[cmd.index("-o") + 1])
            model = cmd[cmd.index("-n") + 1]
            stem = Path(cmd[-1]).stem
            target = out_dir / model / stem
            target.mkdir(parents=True, exist_ok=True)
            (target / "vocals.wav").write_bytes(b"")
            (target / "guitar.wav").write_bytes(b"")

        class _Done:
            stderr = ""

        return _Done()

    return runner


def test_separate_vocals_uses_two_stem_light_model(monkeypatch, tmp_path) -> None:
    captured: list[list[str]] = []
    monkeypatch.setattr(demucs_adapter.subprocess, "run", _fake_run(captured, True))

    audio = tmp_path / "song.wav"
    audio.write_bytes(b"")
    out = DemucsSeparator().separate_vocals(audio, tmp_path)

    assert out.name == "vocals.wav"
    cmd = captured[0]
    # Lighter 4-source model, not the slow 6-source htdemucs_6s.
    assert cmd[cmd.index("-n") + 1] == VOCAL_MODEL
    assert VOCAL_MODEL != MODEL
    assert "--two-stems" in cmd
    assert cmd[cmd.index("--two-stems") + 1] == "vocals"


def test_separate_guitar_still_uses_six_source_model(monkeypatch, tmp_path) -> None:
    captured: list[list[str]] = []
    monkeypatch.setattr(demucs_adapter.subprocess, "run", _fake_run(captured, True))

    audio = tmp_path / "song.wav"
    audio.write_bytes(b"")
    out = DemucsSeparator().separate_guitar(audio, tmp_path)

    assert out.name == "guitar.wav"
    cmd = captured[0]
    assert cmd[cmd.index("-n") + 1] == MODEL
    assert "--two-stems" not in cmd


def test_device_is_forwarded(monkeypatch, tmp_path) -> None:
    captured: list[list[str]] = []
    monkeypatch.setattr(demucs_adapter.subprocess, "run", _fake_run(captured, True))

    audio = tmp_path / "song.wav"
    audio.write_bytes(b"")
    DemucsSeparator(device="cuda").separate_vocals(audio, tmp_path)
    assert captured[0][captured[0].index("-d") + 1] == "cuda"


def test_missing_vocals_output_raises(monkeypatch, tmp_path) -> None:
    from rockforge.domain.errors import SeparationError

    captured: list[list[str]] = []
    monkeypatch.setattr(demucs_adapter.subprocess, "run", _fake_run(captured, False))

    audio = tmp_path / "song.wav"
    audio.write_bytes(b"")
    with pytest.raises(SeparationError):
        DemucsSeparator().separate_vocals(audio, tmp_path)
