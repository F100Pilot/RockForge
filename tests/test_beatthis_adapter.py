"""Unit tests for the Beat This! checkpoint resolver — the network download is
faked, so no torch / beat_this / internet is needed (the neural model itself is
monkeypatched at the port boundary in test_api.py)."""

from __future__ import annotations

import io
import urllib.request

import pytest

from rockforge.infrastructure.rhythm import beatthis_adapter as bt


class _FakeResp:
    def __init__(self, data: bytes) -> None:
        self._b = io.BytesIO(data)

    def read(self, n: int = -1) -> bytes:
        return self._b.read(n)

    def __enter__(self) -> _FakeResp:
        return self

    def __exit__(self, *a: object) -> bool:
        return False


def test_resolve_checkpoint_returns_an_existing_local_file_as_is(tmp_path, monkeypatch) -> None:
    ckpt = tmp_path / "my.ckpt"
    ckpt.write_bytes(b"PK\x03\x04local")
    monkeypatch.setattr(
        urllib.request, "urlopen", lambda *a, **k: pytest.fail("must not download")
    )
    assert bt._resolve_checkpoint(str(ckpt)) == str(ckpt)


def test_resolve_checkpoint_reuses_the_cache_without_downloading(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ROCKFORGE_BEATTHIS_CACHE", str(tmp_path))
    (tmp_path / "final0.ckpt").write_bytes(b"PK\x03\x04cached")
    monkeypatch.setattr(
        urllib.request, "urlopen", lambda *a, **k: pytest.fail("must not download")
    )
    assert bt._resolve_checkpoint("final0") == str(tmp_path / "final0.ckpt")


def test_resolve_checkpoint_downloads_a_shortname_to_the_cache(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ROCKFORGE_BEATTHIS_CACHE", str(tmp_path))
    payload = b"PK\x03\x04" + b"fake checkpoint bytes" * 4
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: _FakeResp(payload))

    path = bt._resolve_checkpoint("final0")
    assert path == str(tmp_path / "final0.ckpt")
    assert (tmp_path / "final0.ckpt").read_bytes() == payload
    # No leftover partial file.
    assert not (tmp_path / "final0.ckpt.part").exists()


def test_resolve_checkpoint_rejects_an_html_error_page(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ROCKFORGE_BEATTHIS_CACHE", str(tmp_path))
    monkeypatch.setattr(
        urllib.request, "urlopen", lambda *a, **k: _FakeResp(b"<!DOCTYPE html><html>nope")
    )
    with pytest.raises(RuntimeError, match="non-file response"):
        bt._resolve_checkpoint("final0")
    assert not (tmp_path / "final0.ckpt").exists()
