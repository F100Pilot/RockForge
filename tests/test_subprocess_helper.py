"""The shared external-tool subprocess hardening (MIN-8 / IMP-3): the security
default and the failure→typed-error mapping live in infrastructure/_subprocess.py
so the three adapters (ffmpeg, Demucs, Banquet) don't each re-implement them."""

from __future__ import annotations

import subprocess

import pytest

from rockforge.infrastructure._subprocess import HARDENED_RUN_KWARGS, map_external_errors


class _MyError(Exception):
    pass


def test_hardened_kwargs_close_stdin() -> None:
    """The anti-hang guard: every external tool runs with stdin=DEVNULL so a CLI
    launched from a console can't block on an inherited stdin."""
    assert HARDENED_RUN_KWARGS["stdin"] is subprocess.DEVNULL
    assert HARDENED_RUN_KWARGS["check"] is True
    assert HARDENED_RUN_KWARGS["capture_output"] is True
    assert HARDENED_RUN_KWARGS["text"] is True


def test_map_external_errors_passes_through_on_success() -> None:
    with map_external_errors(
        error_cls=_MyError, not_installed_msg="x", timeout_msg="y", fail_msg_prefix="z: "
    ):
        result = 1 + 1
    assert result == 2


def test_map_external_errors_maps_missing_binary() -> None:
    with pytest.raises(_MyError, match="not installed"), map_external_errors(
        error_cls=_MyError,
        not_installed_msg="tool is not installed",
        timeout_msg="timeout",
        fail_msg_prefix="failed: ",
    ):
        raise FileNotFoundError


def test_map_external_errors_maps_timeout() -> None:
    with pytest.raises(_MyError, match="timed out"), map_external_errors(
        error_cls=_MyError,
        not_installed_msg="not installed",
        timeout_msg="timed out after 5s",
        fail_msg_prefix="failed: ",
    ):
        raise subprocess.TimeoutExpired(cmd=["tool"], timeout=5)


def test_map_external_errors_maps_nonzero_exit_with_stderr_tail() -> None:
    with pytest.raises(_MyError, match="failed: boom"), map_external_errors(
        error_cls=_MyError,
        not_installed_msg="not installed",
        timeout_msg="timeout",
        fail_msg_prefix="failed: ",
    ):
        raise subprocess.CalledProcessError(returncode=1, cmd=["tool"], stderr="boom")


def test_map_external_errors_truncates_stderr_to_the_tail() -> None:
    long_stderr = "A" + "B" * 5000
    with pytest.raises(_MyError) as excinfo, map_external_errors(
        error_cls=_MyError,
        not_installed_msg="x",
        timeout_msg="y",
        fail_msg_prefix="failed: ",
        stderr_tail=2000,
    ):
        raise subprocess.CalledProcessError(returncode=1, cmd=["t"], stderr=long_stderr)
    msg = str(excinfo.value)
    assert msg.startswith("failed: ")
    assert len(msg) - len("failed: ") == 2000  # only the last 2000 chars kept
    assert "A" not in msg  # the leading char (past the tail) is dropped
