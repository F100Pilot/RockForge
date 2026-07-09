"""Device auto-detection for the ML adapters (celery_app._resolve_device).

torch is not installed in CI, so "auto" must degrade to "cpu" cleanly; the
CUDA branch is exercised by injecting a fake torch module.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

from rockforge.interfaces.worker.celery_app import _resolve_device


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    # _resolve_device is @cache'd per-process; clear between tests so each
    # test starts fresh regardless of run order.
    _resolve_device.cache_clear()


def test_explicit_devices_pass_through() -> None:
    assert _resolve_device("cpu") == "cpu"
    assert _resolve_device("cuda") == "cuda"
    # An unrecognised explicit value is the user's choice — left untouched.
    assert _resolve_device("mps") == "mps"


def test_auto_without_torch_falls_back_to_cpu(monkeypatch: pytest.MonkeyPatch) -> None:
    # Ensure importing torch fails (as in CI, where it isn't installed).
    monkeypatch.setitem(sys.modules, "torch", None)
    assert _resolve_device("auto") == "cpu"


def test_auto_picks_cuda_when_gpu_available(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = types.ModuleType("torch")
    fake.cuda = types.SimpleNamespace(is_available=lambda: True)  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "torch", fake)
    assert _resolve_device("auto") == "cuda"


def test_auto_picks_cpu_when_gpu_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = types.ModuleType("torch")
    fake.cuda = types.SimpleNamespace(is_available=lambda: False)  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "torch", fake)
    assert _resolve_device("auto") == "cpu"


def test_whisperx_cuda_broken_marker_round_trips(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """After a native GPU crash the marker persists, so a later detection can
    skip the doomed CUDA attempt and run on CPU directly."""
    from rockforge.config import settings
    from rockforge.interfaces.worker import celery_app as ca

    monkeypatch.setattr(settings, "work_dir", tmp_path)
    assert ca._whisperx_cuda_known_broken() is False
    ca._mark_whisperx_cuda_broken()
    assert ca._whisperx_cuda_known_broken() is True
    # Idempotent — marking again does not raise or change the result.
    ca._mark_whisperx_cuda_broken()
    assert ca._whisperx_cuda_known_broken() is True
