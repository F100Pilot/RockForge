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
        data={"title": "Song", "artist": "Artist", "year": "1986"},
    )
    assert r.status_code == 202
    body = r.json()
    assert body["status"] == "pending"
    assert body["year"] == 1986

    r2 = client.get(f"/jobs/{body['id']}")
    assert r2.status_code == 200
    assert r2.json()["title"] == "Song"


def test_upload_without_metadata_and_untagged_file_returns_422(client: TestClient) -> None:
    r = client.post(
        "/jobs/upload",
        files={"file": ("song.wav", b"RIFF0000WAVE", "audio/wav")},
        data={},
    )
    assert r.status_code == 422
    assert "title" in r.json()["detail"] and "artist" in r.json()["detail"]


def test_upload_falls_back_to_file_tags(client: TestClient, monkeypatch) -> None:
    from rockforge.infrastructure.ingestion import tags as tags_mod

    monkeypatch.setattr(
        tags_mod, "read_tags",
        lambda path: tags_mod.AudioTags(
            title="Tagged", artist="TagBand", album="TagAlbum", year=1999
        ),
    )
    r = client.post(
        "/jobs/upload",
        files={"file": ("song.wav", b"RIFF0000WAVE", "audio/wav")},
        data={"artist": "FormBand"},  # form value must win over the tag
    )
    assert r.status_code == 202
    body = r.json()
    assert body["title"] == "Tagged"
    assert body["artist"] == "FormBand"
    assert body["album"] == "TagAlbum"
    assert body["year"] == 1999


def test_youtube_disabled_by_default_returns_403(client: TestClient) -> None:
    r = client.post(
        "/jobs/youtube",
        json={"url": "https://www.youtube.com/watch?v=x", "title": "T", "artist": "A"},
    )
    assert r.status_code == 403
    assert "ToS" in r.json()["detail"]


def _create_job(client: TestClient) -> dict:
    r = client.post(
        "/jobs/upload",
        files={"file": ("song.wav", b"RIFF0000WAVE", "audio/wav")},
        data={"title": "Song", "artist": "Artist"},
    )
    assert r.status_code == 202
    return r.json()


def test_list_jobs_newest_first(client: TestClient) -> None:
    a = _create_job(client)
    b = _create_job(client)
    jobs = client.get("/jobs").json()
    ids = [j["id"] for j in jobs]
    assert ids.index(b["id"]) <= ids.index(a["id"])
    assert all("stage" in j and "stages" in j for j in jobs)


def test_rebuild_creates_new_job_with_overrides(client: TestClient) -> None:
    original = _create_job(client)
    r = client.post(
        f"/jobs/{original['id']}/rebuild",
        json={"tuning_midi": [38, 45, 50, 55, 59, 64], "split_lead_rhythm": False},
    )
    assert r.status_code == 202
    assert r.json()["id"] != original["id"]


def test_rebuild_validates_tuning_length(client: TestClient) -> None:
    original = _create_job(client)
    r = client.post(f"/jobs/{original['id']}/rebuild", json={"tuning_midi": [40, 45]})
    assert r.status_code == 422


def test_arrangements_404_until_completed(client: TestClient) -> None:
    job = _create_job(client)
    assert client.get(f"/jobs/{job['id']}/arrangements").status_code == 404


def test_unknown_job_404(client: TestClient) -> None:
    assert client.get("/jobs/nope").status_code == 404
    assert client.get("/jobs/nope/psarc").status_code == 404
