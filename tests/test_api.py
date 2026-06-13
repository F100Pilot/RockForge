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


def test_delete_job_removes_job_workdir_and_upload(client: TestClient) -> None:
    import rockforge.config as config

    job = _create_job(client)
    source = next((config.settings.work_dir / "uploads").glob("*.wav"))
    workdir = config.settings.work_dir / job["id"]
    workdir.mkdir(parents=True)
    (workdir / "bundle").mkdir()

    r = client.delete(f"/jobs/{job['id']}")
    assert r.status_code == 204
    assert client.get(f"/jobs/{job['id']}").status_code == 404
    assert not workdir.exists()
    assert not source.exists()


def test_delete_job_keeps_upload_shared_with_rebuild(client: TestClient) -> None:
    import rockforge.config as config

    original = _create_job(client)
    rebuilt = client.post(f"/jobs/{original['id']}/rebuild", json={}).json()
    source = next((config.settings.work_dir / "uploads").glob("*.wav"))

    assert client.delete(f"/jobs/{original['id']}").status_code == 204
    assert source.exists()  # the rebuild job still references it
    assert client.delete(f"/jobs/{rebuilt['id']}").status_code == 204
    assert not source.exists()


def test_delete_running_job_409(client: TestClient) -> None:
    import rockforge.interfaces.api.app as app_module
    from rockforge.infrastructure.db.models import JobStatus

    job = _create_job(client)
    with app_module._session_factory() as session:
        db_job = session.get(app_module.Job, job["id"])
        db_job.status = JobStatus.RUNNING
        session.commit()
    assert client.delete(f"/jobs/{job['id']}").status_code == 409


def test_delete_unknown_job_404(client: TestClient) -> None:
    assert client.delete("/jobs/nope").status_code == 404


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


def test_rebuild_applies_offset_for_visual_sync(client: TestClient) -> None:
    # The visual sync tool rebuilds with the chosen offset_s; it must land in the
    # new job's params and be reflected in offset_s on the job output.
    original = _create_job(client)
    rebuilt = client.post(
        f"/jobs/{original['id']}/rebuild", json={"offset_s": 3.25}
    ).json()
    assert client.get(f"/jobs/{rebuilt['id']}").json()["offset_s"] == pytest.approx(3.25)


def test_rebuild_rejects_negative_offset(client: TestClient) -> None:
    original = _create_job(client)
    r = client.post(f"/jobs/{original['id']}/rebuild", json={"offset_s": -1.0})
    assert r.status_code == 422


def test_source_audio_served_for_upload(client: TestClient) -> None:
    job = _create_job(client)
    r = client.get(f"/jobs/{job['id']}/source-audio")
    assert r.status_code == 200
    assert r.content == b"RIFF0000WAVE"


def test_source_audio_404_for_unknown_job(client: TestClient) -> None:
    assert client.get("/jobs/nope/source-audio").status_code == 404


def test_arrangements_404_until_completed(client: TestClient) -> None:
    job = _create_job(client)
    assert client.get(f"/jobs/{job['id']}/arrangements").status_code == 404


def _make_gp5_bytes(tmp_path) -> bytes:
    import guitarpro as gp

    song = gp.Song()
    song.title, song.artist, song.tempo = "GpT", "GpA", 100
    song.tracks[0].name = "Lead"
    v = song.tracks[0].measures[0].voices[0]
    b = gp.Beat(v)
    b.status = gp.BeatStatus.normal
    b.duration = gp.Duration(value=4)
    n = gp.Note(b)
    n.string, n.value, n.type = 6, 3, gp.NoteType.normal
    b.notes.append(n)
    v.beats.append(b)
    p = tmp_path / "api.gp5"
    gp.write(song, str(p))
    return p.read_bytes()


def test_gp_inspect_rejects_gpx(client: TestClient) -> None:
    r = client.post(
        "/gp/inspect", files={"file": ("song.gpx", b"BCFS", "application/octet-stream")}
    )
    assert r.status_code == 415
    assert "GP5" in r.json()["detail"]


def test_gp_inspect_and_job_flow(client: TestClient, tmp_path) -> None:
    data = _make_gp5_bytes(tmp_path)
    r = client.post("/gp/inspect", files={"file": ("song.gp5", data, "application/octet-stream")})
    assert r.status_code == 200
    body = r.json()
    assert body["title"] == "GpT"
    assert body["tracks"][0]["name"] == "Lead"
    assert body["tracks"][0]["tuning_midi"] == [40, 45, 50, 55, 59, 64]

    r2 = client.post(
        "/jobs/gp",
        data={
            "gp_token": body["gp_token"],
            "lead_track": "0",
            "offset_s": "1.5",
            "tone_base": "clean",
            "tone_names": "dist,solo",
        },
        files={"audio": ("song.wav", b"RIFF0000WAVE", "audio/wav")},
    )
    assert r2.status_code == 202
    job = r2.json()
    assert job["title"] == "GpT" and job["artist"] == "GpA"  # metadata from the GP file


def test_gp_job_unknown_token_404(client: TestClient) -> None:
    r = client.post(
        "/jobs/gp",
        data={"gp_token": "nope.gp5"},
        files={"audio": ("song.wav", b"RIFF", "audio/wav")},
    )
    assert r.status_code == 404


def test_gp_job_too_many_tones(client: TestClient, tmp_path) -> None:
    data = _make_gp5_bytes(tmp_path)
    r = client.post("/gp/inspect", files={"file": ("song.gp5", data, "application/octet-stream")})
    r2 = client.post(
        "/jobs/gp",
        data={"gp_token": r.json()["gp_token"], "tone_names": "a,b,c,d,e"},
        files={"audio": ("song.wav", b"RIFF0000WAVE", "audio/wav")},
    )
    assert r2.status_code == 422


def test_unknown_job_404(client: TestClient) -> None:
    assert client.get("/jobs/nope").status_code == 404
    assert client.get("/jobs/nope/psarc").status_code == 404
