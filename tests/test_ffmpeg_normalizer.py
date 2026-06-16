"""FfmpegNormalizer command-construction + hang-hardening tests (no ffmpeg run).

The real binary never runs in CI; these assert that ffmpeg is invoked in a way
that cannot hang on an inherited stdin (the "stuck at normalizing" bug) and that
a stalled ffmpeg surfaces as a NormalizationError instead of blocking forever.
"""

from __future__ import annotations

import subprocess

import pytest

from rockforge.domain.errors import NormalizationError
from rockforge.infrastructure.normalize import ffmpeg
from rockforge.infrastructure.normalize.ffmpeg import FfmpegNormalizer


def _fake_run(captured: dict[str, object]):
    def runner(cmd, **kwargs):  # noqa: ANN001, ANN202
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs

        class _Done:
            stderr = ""

        return _Done()

    return runner


def test_normalize_never_reads_stdin(monkeypatch, tmp_path) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setattr(ffmpeg.subprocess, "run", _fake_run(captured))

    audio = tmp_path / "song.wav"
    audio.write_bytes(b"")
    FfmpegNormalizer().normalize(audio, tmp_path)

    cmd = captured["cmd"]
    assert "-nostdin" in cmd
    # And the pipe itself is closed, so even without -nostdin there's nothing to read.
    assert captured["kwargs"]["stdin"] is subprocess.DEVNULL
    # A finite timeout means a stalled ffmpeg fails instead of hanging the stage.
    assert captured["kwargs"]["timeout"] == ffmpeg.FFMPEG_TIMEOUT_S


def test_normalize_timeout_raises(monkeypatch, tmp_path) -> None:
    def runner(cmd, **kwargs):  # noqa: ANN001, ANN202
        raise subprocess.TimeoutExpired(cmd, ffmpeg.FFMPEG_TIMEOUT_S)

    monkeypatch.setattr(ffmpeg.subprocess, "run", runner)

    audio = tmp_path / "song.wav"
    audio.write_bytes(b"")
    with pytest.raises(NormalizationError, match="timed out"):
        FfmpegNormalizer().normalize(audio, tmp_path)


def test_normalize_missing_ffmpeg_raises(monkeypatch, tmp_path) -> None:
    def runner(cmd, **kwargs):  # noqa: ANN001, ANN202
        raise FileNotFoundError

    monkeypatch.setattr(ffmpeg.subprocess, "run", runner)

    audio = tmp_path / "song.wav"
    audio.write_bytes(b"")
    with pytest.raises(NormalizationError, match="not installed"):
        FfmpegNormalizer().normalize(audio, tmp_path)
