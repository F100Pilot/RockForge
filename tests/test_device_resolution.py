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
def _clear_cache(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # The torch detection is @cache'd per-process; clear between tests so each
    # test starts fresh regardless of run order.
    from rockforge.interfaces.worker import celery_app as ca

    ca._detect_device.cache_clear()
    # Point the GPU-broken marker at a fresh tmp dir so no real/leftover marker
    # leaks into a test (each test opts in by creating it).
    monkeypatch.setattr(ca, "_cuda_broken_marker", lambda: tmp_path / ".gpu_ml_broken")
    # Also isolate the legacy-marker fallback check (reads settings.work_dir).
    monkeypatch.setattr(ca.settings, "work_dir", tmp_path)


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


def test_cuda_broken_marker_round_trips() -> None:
    """After a native GPU crash the marker persists, so later runs can skip the
    doomed CUDA attempt and run on CPU directly."""
    from rockforge.interfaces.worker import celery_app as ca

    assert ca._cuda_known_broken() is False
    ca._mark_cuda_broken()
    assert ca._cuda_known_broken() is True
    # Idempotent — marking again does not raise or change the result.
    ca._mark_cuda_broken()
    assert ca._cuda_known_broken() is True


def test_broken_marker_downgrades_cuda_to_cpu(monkeypatch: pytest.MonkeyPatch) -> None:
    """Once the GPU is marked broken, even an available CUDA GPU resolves to CPU
    — so the whole ML stack (Demucs + WhisperX) stops retrying the flaky GPU."""
    from rockforge.interfaces.worker import celery_app as ca

    fake = types.ModuleType("torch")
    fake.cuda = types.SimpleNamespace(is_available=lambda: True)  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "torch", fake)
    assert _resolve_device("auto") == "cuda"  # healthy GPU
    ca._mark_cuda_broken()
    assert _resolve_device("auto") == "cpu"   # broken → CPU
    assert _resolve_device("cuda") == "cpu"   # even an explicit request degrades


def test_legacy_marker_still_honoured(tmp_path: Path) -> None:
    """A pre-generalisation `.whisperx_cuda_broken` marker keeps degrading the
    GPU, so an existing install isn't silently re-enabled after the rename."""
    from rockforge.interfaces.worker import celery_app as ca

    (tmp_path / ".whisperx_cuda_broken").touch()  # work_dir is tmp_path (fixture)
    assert ca._cuda_known_broken() is True
