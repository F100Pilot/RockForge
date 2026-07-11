"""Runtime settings (the in-app "Definições") — persisted to work_dir/settings.json,
shared by the API and worker. Uses the same per-test SQLite/work-dir fixture as
the API tests via a fresh env + reload."""

from __future__ import annotations

import importlib
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch) -> Iterator[TestClient]:
    monkeypatch.setenv("ROCKFORGE_DATABASE_URL", f"sqlite:///{tmp_path}/test.db")
    monkeypatch.setenv("ROCKFORGE_WORK_DIR", str(tmp_path / "work"))
    import rockforge.config as config
    importlib.reload(config)
    import rockforge.runtime_settings as rs
    importlib.reload(rs)
    import rockforge.interfaces.api.app as app_module
    importlib.reload(app_module)
    with TestClient(app_module.app) as c:
        yield c


def test_settings_default_is_demucs(client: TestClient) -> None:
    body = client.get("/settings").json()
    assert body["stem_separator"] == "demucs"
    assert body["banquet"]["ready"] is False


def test_update_persists_and_reads_back(client: TestClient) -> None:
    r = client.post("/settings", json={"stem_separator": "banquet"})
    assert r.status_code == 200
    assert r.json()["stem_separator"] == "banquet"
    # a fresh GET (re-reads the JSON file) still sees it
    assert client.get("/settings").json()["stem_separator"] == "banquet"


def test_loudness_target_default_and_override(client: TestClient) -> None:
    # Default is the louder music-game level.
    assert client.get("/settings").json()["loudness_target"] == -12.0
    r = client.post("/settings", json={"loudness_target": -10.0})
    assert r.status_code == 200
    assert r.json()["loudness_target"] == -10.0
    assert client.get("/settings").json()["loudness_target"] == -10.0


def test_loudness_target_is_clamped(client: TestClient) -> None:
    import rockforge.runtime_settings as rs

    client.post("/settings", json={"loudness_target": 5.0})   # absurdly hot
    assert rs.loudness_target() == -6.0   # clamped to the max
    client.post("/settings", json={"loudness_target": -50.0})  # absurdly quiet
    assert rs.loudness_target() == -20.0  # clamped to the min


def test_gpu_reset_clears_marker(client: TestClient, tmp_path, monkeypatch) -> None:
    """The GPU-broken marker is reported in /settings and cleared by /gpu-reset,
    so the user reactivates the GPU from the UI without hunting for the file."""
    from rockforge.interfaces.worker import celery_app as ca

    monkeypatch.setattr(ca.settings, "work_dir", tmp_path)  # isolate the marker

    assert client.get("/settings").json()["gpu_broken"] is False
    ca._mark_cuda_broken()
    assert client.get("/settings").json()["gpu_broken"] is True
    body = client.post("/gpu-reset").json()
    assert body["gpu_broken"] is False
    assert client.get("/settings").json()["gpu_broken"] is False


def test_invalid_separator_rejected(client: TestClient) -> None:
    assert client.post("/settings", json={"stem_separator": "nope"}).status_code == 422


def test_banquet_paths_validate(client: TestClient, tmp_path) -> None:
    repo = tmp_path / "query-bandit"
    repo.mkdir()
    (repo / "train.py").write_text("# fake")
    ckpt = tmp_path / "ev.ckpt"
    ckpt.write_bytes(b"")
    qdir = tmp_path / "queries"
    qdir.mkdir()
    (qdir / "electric_guitar.wav").write_bytes(b"")

    body = client.post(
        "/settings",
        json={
            "stem_separator": "banquet",
            "banquet_repo": str(repo),
            "banquet_ckpt": str(ckpt),
            "banquet_queries": str(qdir),
        },
    ).json()
    assert body["banquet"]["ready"] is True
    assert body["banquet"]["query_names"] == ["electric_guitar"]


def test_empty_string_clears_override(client: TestClient) -> None:
    client.post("/settings", json={"stem_separator": "banquet"})
    # clearing falls back to the env default (demucs)
    body = client.post("/settings", json={"stem_separator": ""}).json()
    assert body["stem_separator"] == "demucs"
