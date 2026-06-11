"""API tests. The Celery enqueue is stubbed; DB is per-test SQLite."""

from __future__ import annotations

import importlib
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch) -> Iterator[TestClient]:
    monkeypatch.setenv("ROCKFORGE_DATABASE_URL", f"sqlite:///{tmp_path}/test.db")
    monkeypatch.setenv("ROCKFORGE_WORK_DIR", str(tmp_path / "work"))
    monkeypatch.setenv("ROCKFORGE_ENABLE_YOUTUBE", "false")
    import rockforge.config as config
    importlib.reload(config)
    import rockforge.interfaces.api.app as app_module
    importlib.reload(app_module)
    monkeypatch.setattr(app_module, "_enqueue", lambda job: None)
    with TestClient(app_module.app) as c:
        yield c


def test_upload_rejects_unknown_format(client: TestClient) -> None:
    r = client.post(
        "/jobs/upload",
        files={"file": ("song.txt", b"not audio", "text/plain")},
        data={"title": "T", "artist": "A"},
    )
    assert r.status_code == 415


def test_upload_creates_pending_job(client: TestClient) -> None:
    r = client.post(
        "/jobs/upload",
        files={"file": ("song.wav", b"RIFF0000WAVE", "audio/wav")},
        data={"title": "Song", "artist": "Artist"},
    )
    assert r.status_code == 202
    body = r.json()
    assert body["status"] == "pending"

    r2 = client.get(f"/jobs/{body['id']}")
    assert r2.status_code == 200
    assert r2.json()["title"] == "Song"


def test_youtube_disabled_by_default_returns_403(client: TestClient) -> None:
    r = client.post(
        "/jobs/youtube",
        json={"url": "https://www.youtube.com/watch?v=x", "title": "T", "artist": "A"},
    )
    assert r.status_code == 403
    assert "ToS" in r.json()["detail"]


def test_unknown_job_404(client: TestClient) -> None:
    assert client.get("/jobs/nope").status_code == 404
    assert client.get("/jobs/nope/psarc").status_code == 404
