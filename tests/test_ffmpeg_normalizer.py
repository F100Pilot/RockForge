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


def _stub_levels(monkeypatch, loudness, true_peak) -> None:  # noqa: ANN001
    monkeypatch.setattr(ffmpeg, "measure_levels", lambda *a, **k: (loudness, true_peak))


def test_the_recording_gets_a_linear_gain_not_loudnorm(monkeypatch, tmp_path) -> None:
    """A single-pass ``loudnorm`` (moving gain + true-peak limiter) reshaped
    every song — "os PSARC têm algum ruído e não têm uma tonalidade limpa". The
    recording now gets one fixed gain toward the target, as DLC Builder leaves
    the audio alone, and the pad still goes before it."""
    from rockforge import runtime_settings

    monkeypatch.setattr(runtime_settings, "loudness_target", lambda: -12.0)
    _stub_levels(monkeypatch, -16.0, -6.0)
    captured: dict[str, object] = {}
    monkeypatch.setattr(ffmpeg.subprocess, "run", _fake_run(captured))
    audio = tmp_path / "song.wav"
    audio.write_bytes(b"")
    FfmpegNormalizer().normalize(audio, tmp_path, pad_start_s=1.5)
    cmd = captured["cmd"]
    af = cmd[cmd.index("-af") + 1]
    assert "loudnorm" not in af
    assert af == "adelay=1500:all=1,volume=4.00dB"


def test_the_gain_never_pushes_a_peak_over_the_ceiling(monkeypatch, tmp_path) -> None:
    """A master already over 0 dBFS is brought under it (it would be cut off in
    the 16-bit file), even when that leaves it under the loudness target."""
    from rockforge import runtime_settings

    monkeypatch.setattr(runtime_settings, "loudness_target", lambda: -12.0)
    _stub_levels(monkeypatch, -9.5, 0.5)
    captured: dict[str, object] = {}
    monkeypatch.setattr(ffmpeg.subprocess, "run", _fake_run(captured))
    audio = tmp_path / "song.wav"
    audio.write_bytes(b"")
    FfmpegNormalizer().normalize(audio, tmp_path)
    cmd = captured["cmd"]
    assert cmd[cmd.index("-af") + 1] == "volume=-2.50dB"


def test_an_unmeasurable_recording_is_passed_through_untouched(monkeypatch, tmp_path) -> None:
    _stub_levels(monkeypatch, None, None)
    captured: dict[str, object] = {}
    monkeypatch.setattr(ffmpeg.subprocess, "run", _fake_run(captured))
    audio = tmp_path / "song.wav"
    audio.write_bytes(b"")
    FfmpegNormalizer().normalize(audio, tmp_path)
    assert "-af" not in captured["cmd"]


def test_external_tools_output_is_read_as_utf8_on_every_system() -> None:
    """text=True alone decodes with the locale codec — cp1252 on Windows, which
    raised on a Japanese or Cyrillic tag in ffmpeg's output."""
    import inspect

    from rockforge.infrastructure import _subprocess
    from rockforge.infrastructure.normalize import loudness
    from rockforge.infrastructure.packaging import wwise

    assert _subprocess.HARDENED_RUN_KWARGS["encoding"] == "utf-8"
    for module in (loudness, wwise):
        src = inspect.getsource(module)
        assert src.count('encoding="utf-8"') >= src.count("subprocess.run(")
    assert "stdin=subprocess.DEVNULL" in inspect.getsource(wwise)
