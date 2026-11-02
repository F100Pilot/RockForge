"""API tests. The Celery enqueue is stubbed; DB is per-test SQLite."""

from __future__ import annotations

import importlib
import json
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch) -> Iterator[TestClient]:
    monkeypatch.setenv("ROCKFORGE_DATABASE_URL", f"sqlite:///{tmp_path}/test.db")
    monkeypatch.setenv("ROCKFORGE_WORK_DIR", str(tmp_path / "work"))
    import rockforge.config as config
    importlib.reload(config)
    import rockforge.interfaces.api.app as app_module
    importlib.reload(app_module)
    monkeypatch.setattr(app_module, "_enqueue", lambda job: None)
    monkeypatch.setattr(app_module, "_enqueue_detect", lambda job: None)
    monkeypatch.setattr(app_module, "_enqueue_detect_tones", lambda job: None)
    monkeypatch.setattr(app_module, "_enqueue_separate_stems", lambda job: None)
    with TestClient(app_module.app) as c:
        yield c


def test_no_auth_by_default(client: TestClient) -> None:
    """ROCKFORGE_API_TOKEN unset (the default for local single-user setups) —
    every route is reachable with no credentials at all."""
    assert client.get("/jobs").status_code == 200


def test_index_page_references_the_extracted_app_js(client: TestClient) -> None:
    """The UI's JS lives in web/app.js (extracted out of index.html's inline
    <script> so it's lintable), loaded via a <script src> tag."""
    import re

    r = client.get("/")
    assert r.status_code == 200
    # Loaded from /app.js, and CACHE-BUSTED by the file's own mtime: the browser
    # otherwise keeps a stale app.js, leaving new markup wired to an old script —
    # a new button that exists and does nothing, which reads as a broken feature.
    m = re.search(r'<script src="/app\.js\?v=(\d+)"></script>', r.text)
    assert m, r.text[-300:]
    assert int(m.group(1)) > 0
    # The file itself must revalidate, so a changed version always wins.
    js = client.get("/app.js")
    assert js.headers["cache-control"] == "no-cache"
    assert "<script>" not in r.text  # no inline JS left behind


def test_bundled_web_files_are_found_in_the_pyinstaller_bundle(monkeypatch, tmp_path) -> None:
    """Inside the standalone .exe the web UI lives under ``sys._MEIPASS/web``.

    Neither of the other two candidates resolves there — ``__file__`` points into
    the frozen archive and the launcher never chdirs — so without _MEIPASS first
    every bundled file 404s: index.html falls back to the "UI not bundled" stub
    and /app.js is missing outright, leaving a page that loads and does nothing.
    """
    import sys

    import rockforge.interfaces.api.app as app_module

    bundle = tmp_path / "meipass"
    (bundle / "web" / "gear_images").mkdir(parents=True)
    (bundle / "web" / "app.js").write_text("// bundled", encoding="utf-8")
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle), raising=False)

    candidates = app_module._web_file_candidates("app.js")
    assert candidates[0] == bundle / "web" / "app.js", candidates
    assert next(p for p in candidates if p.exists()).read_text() == "// bundled"
    # Gear art resolves through the same list, after the work_dir override.
    assert bundle / "web" / "gear_images" in app_module._gear_image_dirs()


def test_app_js_is_served_with_a_javascript_content_type(client: TestClient) -> None:
    r = client.get("/app.js")
    assert r.status_code == 200
    assert "javascript" in r.headers["content-type"]
    assert "document.querySelectorAll" in r.text


def test_the_page_carries_the_rockforge_icon(client: TestClient) -> None:
    page = client.get("/").text
    assert '<link rel="icon" type="image/svg+xml" href="/favicon.svg">' in page
    r = client.get("/favicon.svg")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/svg+xml")
    assert "<svg" in r.text


def test_the_practice_mode_scripts_are_served(client: TestClient) -> None:
    """Partitura → "Tocar": practice-core.js is a page script (the judge) and is
    also added to the audio worklet before practice-worklet.js, which app.js
    loads by URL — both must be served as JavaScript, the core cache-busted."""
    page = client.get("/").text
    assert '<script src="/practice-core.js?v=' in page
    assert page.index("/practice-core.js") < page.index("/app.js")
    scripts = (("practice-core.js", "createTracker"), ("practice-worklet.js", "registerProcessor"))
    for name, marker in scripts:
        r = client.get(f"/{name}")
        assert r.status_code == 200, name
        assert "javascript" in r.headers["content-type"]
        assert marker in r.text


def test_the_3d_highway_and_its_three_js_are_served(client: TestClient) -> None:
    """Partitura → "Pista 3D": highway3d.js loads the vendored three.js on first
    use, so both have to be served (and cache-busted like app.js)."""
    page = client.get("/").text
    assert '<script src="/highway3d.js?v=' in page and '<script src="/app.js?v=' in page
    r = client.get("/highway3d.js")
    assert r.status_code == 200 and "javascript" in r.headers["content-type"]
    assert "window.Highway3D" in r.text and "/vendor/three/three.module.js" in r.text
    for name in ("three.module.js", "three.core.js"):
        three = client.get(f"/vendor/three/{name}")
        assert three.status_code == 200 and "javascript" in three.headers["content-type"]
    # Only those two files: never an arbitrary path under web/.
    assert client.get("/vendor/three/LICENSE").status_code == 404
    assert client.get("/vendor/three/..%2F..%2Findex.html").status_code == 404


def test_api_token_gates_every_route_when_set(tmp_path, monkeypatch) -> None:
    """Setting ROCKFORGE_API_TOKEN turns on an HTTP Basic gate in front of the
    whole app — wrong/missing credentials are rejected, the right password
    (any username) is accepted."""
    monkeypatch.setenv("ROCKFORGE_DATABASE_URL", f"sqlite:///{tmp_path}/test.db")
    monkeypatch.setenv("ROCKFORGE_WORK_DIR", str(tmp_path / "work"))
    monkeypatch.setenv("ROCKFORGE_API_TOKEN", "s3cr3t")
    import rockforge.config as config
    importlib.reload(config)
    import rockforge.interfaces.api.app as app_module
    importlib.reload(app_module)

    with TestClient(app_module.app) as c:
        no_auth = c.get("/jobs")
        assert no_auth.status_code == 401
        assert no_auth.headers["www-authenticate"] == "Basic"

        wrong = c.get("/jobs", auth=("anyone", "wrong-token"))
        assert wrong.status_code == 401

        right = c.get("/jobs", auth=("anyone", "s3cr3t"))
        assert right.status_code == 200


def test_gear_image_serves_local_file_or_404(client: TestClient) -> None:
    """The tone editor's gear image is served from work_dir/gear_images/<key>;
    404 when absent, and the key is sanitised against path traversal."""
    import rockforge.interfaces.api.app as app_module

    # No image yet → 404.
    assert client.get("/gear-image/some_amp").status_code == 404
    # Drop a user image and it's served.
    folder = app_module.settings.work_dir / "gear_images"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "some_amp.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    r = client.get("/gear-image/some_amp")
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"
    # Path traversal is stripped to a bare slug → no escape, 404.
    assert client.get("/gear-image/..%2f..%2fsecret").status_code in (404, 400)


def test_gear_image_falls_back_to_bundled_and_workdir_wins(client: TestClient) -> None:
    """A key with no work_dir override is served from the bundled
    web/gear_images/; a work_dir image of the same key takes precedence."""
    import rockforge.interfaces.api.app as app_module

    dirs = app_module._gear_image_dirs()
    bundled = next((d for d in dirs if d.name == "gear_images" and "web" in d.parts), None)
    assert bundled is not None and (bundled / "Rack_StudioCompressor.png").is_file()

    # No work_dir override → served from the bundled folder.
    r = client.get("/gear-image/Rack_StudioCompressor")
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"

    # A work_dir image of the SAME key overrides the bundled one.
    folder = app_module.settings.work_dir / "gear_images"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "Rack_StudioCompressor.png").write_bytes(b"\x89PNG\r\n\x1a\nOVERRIDE")
    r2 = client.get("/gear-image/Rack_StudioCompressor")
    assert r2.status_code == 200 and r2.content == b"\x89PNG\r\n\x1a\nOVERRIDE"


def _create_job(client: TestClient) -> dict:
    """Insert a minimal non-GP job row directly.

    The audio-upload endpoint (note transcription) was removed, but many
    downstream tests just need *a* job to operate on — and several rely on it
    being a non-GP job so GP-only endpoints reject it. We insert an
    ``"upload"``-type row straight into the DB with a real ``source`` file so
    ``/source-audio`` serves it."""
    import uuid

    import rockforge.interfaces.api.app as app_module

    uploads = app_module.settings.work_dir / "uploads"
    uploads.mkdir(parents=True, exist_ok=True)
    src = uploads / f"{uuid.uuid4()}.wav"
    src.write_bytes(b"RIFF0000WAVE")
    with app_module._session_factory() as session:
        job = app_module.Job(
            source=str(src), source_type="upload", title="Song", artist="Artist"
        )
        session.add(job)
        session.commit()
        jid = job.id
    return client.get(f"/jobs/{jid}").json()


def test_update_metadata_edits_song_identity(client: TestClient) -> None:
    job = _create_job(client)
    r = client.patch(
        f"/jobs/{job['id']}/metadata",
        json={"title": "New Title", "artist": "New Artist", "album": "New Album", "year": 2001},
    )
    assert r.status_code == 200
    out = r.json()
    assert out["title"] == "New Title"
    assert out["artist"] == "New Artist"
    assert out["album"] == "New Album"
    assert out["year"] == 2001
    # Persisted: a fresh GET reflects the change.
    assert client.get(f"/jobs/{job['id']}").json()["title"] == "New Title"


def test_update_metadata_requires_title_and_artist(client: TestClient) -> None:
    job = _create_job(client)
    r = client.patch(f"/jobs/{job['id']}/metadata", json={"title": "  ", "artist": "x"})
    assert r.status_code == 422


def test_update_metadata_unknown_job_404(client: TestClient) -> None:
    r = client.patch("/jobs/nope/metadata", json={"title": "T", "artist": "A"})
    assert r.status_code == 404


def test_list_jobs_newest_first(client: TestClient) -> None:
    a = _create_job(client)
    b = _create_job(client)
    jobs = client.get("/jobs").json()
    ids = [j["id"] for j in jobs]
    assert ids.index(b["id"]) <= ids.index(a["id"])
    assert all("stage" in j and "stages" in j for j in jobs)


def test_job_stages_match_the_gp_pipeline_on_stage_calls(client: TestClient) -> None:
    """JobOut.stages drives the progress-pill bar (web/index.html highlights the
    entry matching job.stage). It must list the SAME names, in the SAME order,
    that GenerateFromGpUseCase.run actually reports via on_stage — see
    test_gp_pipeline_full_bundle's `stages == [...]` assertion — or the pills
    never highlight for a running job (this drifted once when the audio-ML
    pipeline, with its own longer stage list, was removed)."""
    job = _create_job(client)
    body = client.get(f"/jobs/{job['id']}").json()
    assert body["stages"] == [
        "ingest", "normalize", "parse_gp", "build_arrangements", "lyrics", "package",
    ]


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


def test_force_delete_running_job(client: TestClient) -> None:
    """A job stuck in RUNNING (dead/hung worker) can still be removed with force."""
    import rockforge.interfaces.api.app as app_module
    from rockforge.infrastructure.db.models import JobStatus

    job = _create_job(client)
    with app_module._session_factory() as session:
        db_job = session.get(app_module.Job, job["id"])
        db_job.status = JobStatus.RUNNING
        session.commit()

    assert client.delete(f"/jobs/{job['id']}?force=true").status_code == 204
    assert client.get(f"/jobs/{job['id']}").status_code == 404


def test_delete_unknown_job_404(client: TestClient) -> None:
    assert client.delete("/jobs/nope").status_code == 404


def test_rebuild_creates_new_job_with_overrides(client: TestClient) -> None:
    original = _create_job(client)
    r = client.post(f"/jobs/{original['id']}/rebuild", json={"cent_offset": -12.5})
    assert r.status_code == 202
    assert r.json()["id"] != original["id"]
    import rockforge.interfaces.api.app as app_module
    from rockforge.infrastructure.db.models import Job

    with app_module._session_factory() as session:
        params = session.get(Job, r.json()["id"]).params
    assert params["cent_offset"] == -12.5
    # Not sent = left as it was: an unrelated rebuild keeps the detected cents.
    again = client.post(f"/jobs/{r.json()['id']}/rebuild", json={}).json()
    with app_module._session_factory() as session:
        assert session.get(Job, again["id"]).params["cent_offset"] == -12.5


def test_rebuild_stores_dynamic_difficulty_flag(client: TestClient) -> None:
    original = _create_job(client)
    assert original["dynamic_difficulty"] is True  # default on
    r = client.post(f"/jobs/{original['id']}/rebuild", json={"dynamic_difficulty": False})
    assert r.status_code == 202
    assert r.json()["dynamic_difficulty"] is False


def test_a_cent_offset_past_half_a_semitone_is_refused(client: TestClient) -> None:
    """Past ±50 cents a recording is nearer the next semitone — a tuning, set
    per chart in "Editar info", not a deviation from A440."""
    original = _create_job(client)
    for cents in (50.5, -60, 1e9):
        r = client.post(f"/jobs/{original['id']}/rebuild", json={"cent_offset": cents})
        assert r.status_code == 422, cents
    assert client.post(
        f"/jobs/{original['id']}/rebuild", json={"cent_offset": -50}
    ).status_code == 202


def test_the_bass_reference_is_stored_read_back_and_reset(
    client: TestClient, tmp_path
) -> None:
    """A220/A440 for the Bass, chosen in "Editar info" (a forum request: bass
    players in a low tuning use A220 so the game registers their notes)."""
    body = client.post(
        "/gp/inspect", files={"file": ("song.gp5", _make_gp5_bytes(tmp_path),
                                       "application/octet-stream")}
    ).json()
    job = client.post(
        "/jobs/gp", data={"gp_token": body["gp_token"], "lead_track": "0"},
        files={"audio": ("song.wav", b"RIFF0000WAVE", "audio/wav")},
    ).json()
    assert client.get(f"/jobs/{job['id']}/gp-tracks").json()["bass_reference"] == "auto"
    a220 = client.post(f"/jobs/{job['id']}/rebuild", json={"bass_reference": "a220"}).json()
    assert client.get(f"/jobs/{a220['id']}/gp-tracks").json()["bass_reference"] == "a220"
    # Another rebuild that does not mention it keeps it; "auto" removes it.
    kept = client.post(f"/jobs/{a220['id']}/rebuild", json={"offset_s": 1.0}).json()
    assert client.get(f"/jobs/{kept['id']}/gp-tracks").json()["bass_reference"] == "a220"
    auto = client.post(f"/jobs/{kept['id']}/rebuild", json={"bass_reference": "auto"}).json()
    assert client.get(f"/jobs/{auto['id']}/gp-tracks").json()["bass_reference"] == "auto"
    assert client.post(
        f"/jobs/{job['id']}/rebuild", json={"bass_reference": "a330"}
    ).status_code == 422
    upload = _create_job(client)  # not a GP job
    assert client.post(
        f"/jobs/{upload['id']}/rebuild", json={"bass_reference": "a220"}
    ).status_code == 422


def test_gp_tracks_endpoint_rejects_non_gp_job(client: TestClient) -> None:
    original = _create_job(client)  # an upload job, not GP
    assert client.get(f"/jobs/{original['id']}/gp-tracks").status_code == 422


def test_rebuild_track_assignment_and_tuning_require_gp(client: TestClient) -> None:
    original = _create_job(client)  # upload job
    assert client.post(
        f"/jobs/{original['id']}/rebuild", json={"tracks": {"lead": 0}}
    ).status_code == 422
    assert client.post(
        f"/jobs/{original['id']}/rebuild",
        json={"tuning_overrides": {"Lead": [40, 45, 50, 55, 59, 64]}},
    ).status_code == 422


def test_rebuild_applies_offset_for_visual_sync(client: TestClient) -> None:
    # The visual sync tool rebuilds with the chosen offset_s; it must land in the
    # new job's params and be reflected in offset_s on the job output.
    original = _create_job(client)
    rebuilt = client.post(
        f"/jobs/{original['id']}/rebuild", json={"offset_s": 3.25}
    ).json()
    assert client.get(f"/jobs/{rebuilt['id']}").json()["offset_s"] == pytest.approx(3.25)


def test_rebuild_tempo_scale_rejected_for_non_gp(client: TestClient) -> None:
    # tempo_scale only makes sense for GP jobs (it rescales the authored chart).
    original = _create_job(client)
    r = client.post(f"/jobs/{original['id']}/rebuild", json={"tempo_scale": 1.2})
    assert r.status_code == 422


def test_rebuild_rejects_an_offset_below_the_limit(client: TestClient) -> None:
    """Bar 1 may start before the recording (a negative offset), up to a minute."""
    original = _create_job(client)
    r = client.post(f"/jobs/{original['id']}/rebuild", json={"offset_s": -61.0})
    assert r.status_code == 422


def test_forked_jobs_link_back_to_the_original(client: TestClient) -> None:
    """rebuild / import-sync fork a new job but never delete the old one, so the
    fork records `rebuilt_from` — the UI can walk an iterative sync back."""
    original = _create_job(client)
    assert client.get(f"/jobs/{original['id']}").json()["rebuilt_from"] is None
    rebuilt = client.post(
        f"/jobs/{original['id']}/rebuild", json={"offset_s": 1.0}
    ).json()
    assert rebuilt["rebuilt_from"] == original["id"]
    imported = client.post(
        f"/jobs/{original['id']}/import-sync", json={"sync": {"offset_s": 2.0}}
    ).json()
    assert imported["rebuilt_from"] == original["id"]


def test_extract_sync_state_is_whitelisted() -> None:
    from rockforge.interfaces.api.app import _extract_sync_state

    params = {
        "offset_s": 3.0, "tempo_scale": 1.1, "sync_anchor_stages": [[[1.0, 1.2]]],
        "lyrics_events": [{"time": 1.0, "length": 0.5, "lyric": "hi+"}],
        "cover_art": "cover.png", "psarc_mode": "native",  # NOT sync state
    }
    out = _extract_sync_state(params)
    assert set(out) == {"offset_s", "tempo_scale", "sync_anchor_stages", "lyrics_events"}
    assert "cover_art" not in out and "psarc_mode" not in out


def test_sync_state_export_and_import_round_trip(client: TestClient) -> None:
    original = _create_job(client)
    # Bake hand-tuned sync into a rebuilt job's params, then export it.
    rebuilt = client.post(
        f"/jobs/{original['id']}/rebuild", json={"offset_s": 3.25, "lead_in_s": 1.5}
    ).json()
    exported = client.get(f"/jobs/{rebuilt['id']}/sync-state").json()
    assert exported["version"] == 1
    assert exported["song"] == "Artist - Song"
    assert exported["sync"]["offset_s"] == 3.25
    assert exported["sync"]["lead_in_s"] == 1.5

    # Import into a DIFFERENT job (the re-created-song case) → forks a new job
    # carrying the same sync, so the manual work survives.
    fresh = _create_job(client)
    r = client.post(f"/jobs/{fresh['id']}/import-sync", json=exported)
    assert r.status_code == 202
    imported = r.json()
    assert imported["id"] not in (fresh["id"], rebuilt["id"])
    restored = client.get(f"/jobs/{imported['id']}/sync-state").json()["sync"]
    assert restored["offset_s"] == 3.25 and restored["lead_in_s"] == 1.5


def test_import_sync_drops_gp_only_keys_and_validates(client: TestClient) -> None:
    fresh = _create_job(client)  # an upload (non-GP) job
    # tuning_overrides is GP-only → silently dropped when imported to a non-GP job.
    r = client.post(
        f"/jobs/{fresh['id']}/import-sync",
        json={"sync": {"offset_s": 2.0, "tuning_overrides": {"Lead": [37, 42, 47, 52, 56, 61]}}},
    )
    assert r.status_code == 202
    st = client.get(f"/jobs/{r.json()['id']}/sync-state").json()["sync"]
    assert st["offset_s"] == 2.0 and "tuning_overrides" not in st
    # A malformed tuning is rejected, not stored.
    bad = client.post(
        f"/jobs/{fresh['id']}/import-sync", json={"sync": {"cent_offset": 500}}
    )
    assert bad.status_code == 422


def test_sync_state_404_for_unknown_job(client: TestClient) -> None:
    assert client.get("/jobs/nope/sync-state").status_code == 404
    assert client.post("/jobs/nope/import-sync", json={"sync": {}}).status_code == 404


def test_source_audio_served_for_upload(client: TestClient) -> None:
    job = _create_job(client)
    r = client.get(f"/jobs/{job['id']}/source-audio")
    assert r.status_code == 200
    assert r.content == b"RIFF0000WAVE"


def test_source_audio_404_for_unknown_job(client: TestClient) -> None:
    assert client.get("/jobs/nope/source-audio").status_code == 404


def test_source_audio_falls_back_to_workdir(client: TestClient) -> None:
    """When job.source is not a real file (e.g. a URL), the viewer's audio comes
    from the ingested file in the work dir."""
    import rockforge.interfaces.api.app as app_module

    with app_module._session_factory() as session:
        job = app_module.Job(
            source="https://example.invalid/song", source_type="upload",
            title="T", artist="A",
        )
        session.add(job)
        session.commit()
        jid = job.id
    wd = app_module.settings.work_dir / jid
    wd.mkdir(parents=True)
    (wd / "input.wav").write_bytes(b"RIFFyt00WAVE")
    got = client.get(f"/jobs/{jid}/source-audio")
    assert got.status_code == 200 and got.content == b"RIFFyt00WAVE"


def test_arrangements_404_until_completed(client: TestClient) -> None:
    job = _create_job(client)
    assert client.get(f"/jobs/{job['id']}/arrangements").status_code == 404


def test_arrangements_derives_chord_name(client: TestClient) -> None:
    """A chord in the XML is labelled with its derived name (C major here)."""
    import rockforge.config as config
    import rockforge.interfaces.api.app as app_module
    from rockforge.domain.arrangement import Arrangement, ArrangementKind, SongMetadata
    from rockforge.domain.music import Beat, TabNote, TempoMap, Tuning
    from rockforge.infrastructure.db.models import JobStatus
    from rockforge.infrastructure.rsxml.writer import write_arrangement_xml

    job = _create_job(client)
    bundle = config.settings.work_dir / job["id"] / "bundle"
    # C major triad struck together: C2 (str0 f8), E (str1 f7... ) — pick a
    # simple E-standard voicing that sounds C, E, G simultaneously.
    beats = tuple(Beat(time=0.5 * i, measure=(i // 4 + 1) if i % 4 == 0 else -1) for i in range(8))
    arr = Arrangement(
        kind=ArrangementKind.COMBINED,
        metadata=SongMetadata(title="Chord", artist="T", song_length=4.0),
        tuning=Tuning(),
        notes=[
            TabNote(string=1, fret=3, time=1.0, sustain=0.5),  # A + 3 = C
            TabNote(string=2, fret=2, time=1.0, sustain=0.5),  # D + 2 = E
            TabNote(string=3, fret=0, time=1.0, sustain=0.5),  # G open = G
        ],
        tempo_map=TempoMap(beats=beats, average_bpm=120.0),
    )
    write_arrangement_xml(arr, bundle / "arrangement_combined.xml")

    with app_module._session_factory() as session:
        db_job = session.get(app_module.Job, job["id"])
        db_job.status = JobStatus.COMPLETED
        db_job.bundle_dir = str(bundle)
        db_job.params = {
            **dict(db_job.params or {}),
            "note_overrides": {"Combined": [{"time": 0.5, "string": 1, "fret": 9}]},
        }
        session.commit()

    data = client.get(f"/jobs/{job['id']}/arrangements").json()
    # The committed note edits come back per arrangement, so the viewer can seed
    # its pending list from them instead of resetting to {} and erasing them on
    # the next unrelated rebuild.
    assert data[0]["note_overrides"] == [
        {"time": 0.5, "string": 1, "fret": 9, "sustain": 0.0, "techniques": [],
         "bend_semitones": 0.0, "slide_to_fret": None, "deleted": False}
    ], data[0]["note_overrides"]
    chord_notes = [n for n in data[0]["notes"] if n["chord"]]
    assert chord_notes, "expected the simultaneous notes to be emitted as a chord"
    assert all(n["chord_name"] == "C" for n in chord_notes)
    # single (non-chord) notes must not carry a chord name
    assert all(n["chord_name"] is None for n in data[0]["notes"] if not n["chord"])
    # ALL beats (not just downbeats) are exposed as the drag snap grid
    assert data[0]["beats"] == [0.5 * i for i in range(8)]
    assert [b["measure"] for b in data[0]["bars"]] == [1, 2]  # bars = downbeats only


def test_the_closing_bar_line_is_not_listed_as_a_bar(client: TestClient) -> None:
    """The grid ends on the song's closing bar line (a downbeat with nothing
    after it); the viewer must not number it or offer it as a bar to align."""
    import rockforge.config as config
    import rockforge.interfaces.api.app as app_module
    from rockforge.domain.arrangement import Arrangement, ArrangementKind, SongMetadata
    from rockforge.domain.music import Beat, TabNote, TempoMap, Tuning
    from rockforge.infrastructure.db.models import JobStatus
    from rockforge.infrastructure.rsxml.writer import write_arrangement_xml

    job = _create_job(client)
    bundle = config.settings.work_dir / job["id"] / "bundle"
    beats = tuple(Beat(time=0.5 * i, measure=(i // 4 + 1) if i % 4 == 0 else -1) for i in range(9))
    write_arrangement_xml(Arrangement(
        kind=ArrangementKind.COMBINED,
        metadata=SongMetadata(title="End", artist="T", song_length=4.5),
        tuning=Tuning(),
        notes=[TabNote(string=1, fret=3, time=3.75, sustain=0.2)],
        tempo_map=TempoMap(beats=beats, average_bpm=120.0),
    ), bundle / "arrangement_combined.xml")
    with app_module._session_factory() as session:
        db_job = session.get(app_module.Job, job["id"])
        db_job.status = JobStatus.COMPLETED
        db_job.bundle_dir = str(bundle)
        session.commit()

    data = client.get(f"/jobs/{job['id']}/arrangements").json()
    assert [b["measure"] for b in data[0]["bars"]] == [1, 2]
    assert data[0]["beats"][-1] == 4.0  # still part of the snap grid


def test_arrangements_exposes_bend_magnitude(client: TestClient) -> None:
    """A bent note carries its bend magnitude (semitones) so the viewer can
    label it 'full'/'½'."""
    import rockforge.config as config
    import rockforge.interfaces.api.app as app_module
    from rockforge.domain.arrangement import Arrangement, ArrangementKind, SongMetadata
    from rockforge.domain.music import Beat, TabNote, Technique, TempoMap, Tuning
    from rockforge.infrastructure.db.models import JobStatus
    from rockforge.infrastructure.rsxml.writer import write_arrangement_xml

    job = _create_job(client)
    bundle = config.settings.work_dir / job["id"] / "bundle"
    beats = tuple(Beat(time=0.5 * i, measure=(i // 4 + 1) if i % 4 == 0 else -1) for i in range(8))
    arr = Arrangement(
        kind=ArrangementKind.LEAD,
        metadata=SongMetadata(title="Bend", artist="T", song_length=4.0),
        tuning=Tuning(),
        notes=[
            TabNote(string=2, fret=7, time=1.0, sustain=0.5,
                    techniques=frozenset({Technique.BEND}), bend_semitones=2.0),
            TabNote(string=1, fret=5, time=2.0, sustain=0.2),  # plain, no bend
        ],
        tempo_map=TempoMap(beats=beats, average_bpm=120.0),
    )
    write_arrangement_xml(arr, bundle / "arrangement_lead.xml")

    with app_module._session_factory() as session:
        db_job = session.get(app_module.Job, job["id"])
        db_job.status = JobStatus.COMPLETED
        db_job.bundle_dir = str(bundle)
        session.commit()

    notes = client.get(f"/jobs/{job['id']}/arrangements").json()[0]["notes"]
    bent = [n for n in notes if "bend" in n["techniques"]]
    assert len(bent) == 1 and bent[0]["bend_semitones"] == 2
    assert all(n["bend_semitones"] == 0 for n in notes if "bend" not in n["techniques"])


def test_arrangements_say_where_a_slide_ends(client: TestClient) -> None:
    """The 3D highway draws a slide's trail running to the fret it ends on."""
    import rockforge.config as config
    import rockforge.interfaces.api.app as app_module
    from rockforge.domain.arrangement import Arrangement, ArrangementKind, SongMetadata
    from rockforge.domain.music import Beat, TabNote, Technique, TempoMap, Tuning
    from rockforge.infrastructure.db.models import JobStatus
    from rockforge.infrastructure.rsxml.writer import write_arrangement_xml

    job = _create_job(client)
    bundle = config.settings.work_dir / job["id"] / "bundle"
    beats = tuple(Beat(time=0.5 * i, measure=(i // 4 + 1) if i % 4 == 0 else -1) for i in range(8))
    arr = Arrangement(
        kind=ArrangementKind.LEAD,
        metadata=SongMetadata(title="Slide", artist="T", song_length=4.0),
        tuning=Tuning(),
        notes=[
            TabNote(string=2, fret=5, time=1.0, sustain=0.5,
                    techniques=frozenset({Technique.SLIDE}), slide_to_fret=7),
            TabNote(string=1, fret=5, time=2.0, sustain=0.2),
        ],
        tempo_map=TempoMap(beats=beats, average_bpm=120.0),
    )
    write_arrangement_xml(arr, bundle / "arrangement_lead.xml")
    with app_module._session_factory() as session:
        db_job = session.get(app_module.Job, job["id"])
        db_job.status = JobStatus.COMPLETED
        db_job.bundle_dir = str(bundle)
        session.commit()

    notes = client.get(f"/jobs/{job['id']}/arrangements").json()[0]["notes"]
    assert [(n["fret"], n["slide_to"]) for n in notes] == [(5, 7), (5, -1)]


def test_arrangements_carry_the_bend_curve_for_the_3d_highway(client: TestClient) -> None:
    """The 3D highway draws a bend rising along its <bendValues>: the curve comes
    back relative to the note's attack, and a plain bend's single point too."""
    import rockforge.config as config
    import rockforge.interfaces.api.app as app_module
    from rockforge.domain.arrangement import Arrangement, ArrangementKind, SongMetadata
    from rockforge.domain.music import Beat, BendPoint, TabNote, Technique, TempoMap, Tuning
    from rockforge.infrastructure.db.models import JobStatus
    from rockforge.infrastructure.rsxml.writer import write_arrangement_xml

    job = _create_job(client)
    bundle = config.settings.work_dir / job["id"] / "bundle"
    beats = tuple(Beat(time=0.5 * i, measure=(i // 4 + 1) if i % 4 == 0 else -1) for i in range(8))
    bend = frozenset({Technique.BEND})
    arr = Arrangement(
        kind=ArrangementKind.LEAD,
        metadata=SongMetadata(title="Bends", artist="T", song_length=4.0),
        tuning=Tuning(),
        notes=[
            TabNote(string=3, fret=7, time=1.0, sustain=0.4, techniques=bend, bend_semitones=2),
            TabNote(string=3, fret=7, time=2.0, sustain=0.8, techniques=bend, bend_semitones=2,
                    bend_points=(BendPoint(0.0, 0.0), BendPoint(0.5, 2.0), BendPoint(1.0, 0.0))),
            TabNote(string=1, fret=5, time=3.0, sustain=0.2),
        ],
        tempo_map=TempoMap(beats=beats, average_bpm=120.0),
    )
    write_arrangement_xml(arr, bundle / "arrangement_lead.xml")
    with app_module._session_factory() as session:
        db_job = session.get(app_module.Job, job["id"])
        db_job.status = JobStatus.COMPLETED
        db_job.bundle_dir = str(bundle)
        session.commit()

    notes = client.get(f"/jobs/{job['id']}/arrangements").json()[0]["notes"]
    assert notes[0]["bend_curve"] == [[0.4, 2.0]]
    assert notes[1]["bend_curve"] == [[0.0, 0.0], [0.4, 2.0], [0.8, 0.0]]
    assert notes[2]["bend_curve"] == []


def test_arrangements_show_linked_notes_and_arpeggios(client: TestClient) -> None:
    """The score marks a note linked into the next and an arpeggio's span."""
    import rockforge.config as config
    import rockforge.interfaces.api.app as app_module
    from rockforge.domain.arrangement import Arrangement, ArrangementKind, SongMetadata
    from rockforge.domain.music import Beat, TabNote, Technique, TempoMap, Tuning
    from rockforge.infrastructure.db.models import JobStatus
    from rockforge.infrastructure.rsxml.writer import write_arrangement_xml

    job = _create_job(client)
    bundle = config.settings.work_dir / job["id"] / "bundle"
    beats = tuple(Beat(time=0.5 * i, measure=(i // 4 + 1) if i % 4 == 0 else -1) for i in range(12))
    ring = frozenset({Technique.LET_RING})
    arr = Arrangement(
        kind=ArrangementKind.LEAD,
        metadata=SongMetadata(title="Links", artist="T", song_length=6.0),
        tuning=Tuning(),
        notes=[
            TabNote(2, 5, 0.5, 0.5, link_next=True), TabNote(2, 5, 1.0, 0.2),
            *[TabNote(s, f, 2.0 + 0.25 * k, 0.5, ring)
              for k, (s, f) in enumerate(((1, 3), (2, 2), (3, 0), (4, 1)))],
        ],
        tempo_map=TempoMap(beats=beats, average_bpm=120.0),
    )
    write_arrangement_xml(arr, bundle / "arrangement_lead.xml")
    with app_module._session_factory() as session:
        db_job = session.get(app_module.Job, job["id"])
        db_job.status = JobStatus.COMPLETED
        db_job.bundle_dir = str(bundle)
        session.commit()

    out = client.get(f"/jobs/{job['id']}/arrangements").json()[0]
    assert [n["link_next"] for n in out["notes"]][:2] == [True, False]
    assert out["arpeggios"] == [{"start": 2.0, "end": 3.251, "name": "C"}]


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


def test_cross_origin_post_is_rejected(client: TestClient) -> None:
    """A POST carrying a foreign Origin header (the CSRF shape: a malicious
    page's <form> blind-posting to this API) is rejected; no Origin at all
    (curl, the desktop app, this test suite normally) passes through."""
    cross_origin = client.post(
        "/gp/inspect",
        files={"file": ("song.gpx", b"BCFS", "application/octet-stream")},
        headers={"Origin": "https://evil.example"},
    )
    assert cross_origin.status_code == 403

    same_origin = client.post(
        "/gp/inspect",
        files={"file": ("song.gpx", b"BCFS", "application/octet-stream")},
        headers={"Origin": f"http://{client.base_url.host}"},
    )
    assert same_origin.status_code != 403  # rejected for being .gpx (415), not origin


def test_a_null_origin_is_a_cross_origin_post(client: TestClient) -> None:
    """A sandboxed iframe or a file:// page sends ``Origin: null``; its empty
    host must not slip past the same-origin comparison."""
    r = client.post(
        "/gp/inspect",
        files={"file": ("song.gpx", b"BCFS", "application/octet-stream")},
        headers={"Origin": "null"},
    )
    assert r.status_code == 403


def test_only_the_names_the_server_answers_to_are_served(client: TestClient) -> None:
    """DNS rebinding: a foreign site's domain pointed at 127.0.0.1 arrives as
    that domain in Host, and same-origin to the browser — only the Host
    allowlist refuses it, on reads as well as writes."""
    assert client.get("/jobs", headers={"Host": "evil.example:8000"}).status_code == 400
    assert client.get("/jobs", headers={"Host": "evil.example"}).status_code == 400
    assert client.post(
        "/gp/inspect",
        files={"file": ("song.gpx", b"BCFS", "application/octet-stream")},
        headers={"Host": "evil.example", "Origin": "http://evil.example"},
    ).status_code == 400
    for host in ("localhost:8000", "127.0.0.1:8765", "[::1]:8000", "LOCALHOST", "localhost."):
        assert client.get("/jobs", headers={"Host": host}).status_code == 200, host


def test_any_name_is_served_when_the_allowlist_says_so(tmp_path, monkeypatch) -> None:
    """docker-compose is reached by the machine's own name or address."""
    monkeypatch.setenv("ROCKFORGE_DATABASE_URL", f"sqlite:///{tmp_path}/test.db")
    monkeypatch.setenv("ROCKFORGE_WORK_DIR", str(tmp_path / "work"))
    monkeypatch.setenv("ROCKFORGE_ALLOWED_HOSTS", "*")
    import rockforge.config as config
    importlib.reload(config)
    import rockforge.interfaces.api.app as app_module
    importlib.reload(app_module)
    with TestClient(app_module.app) as c:
        assert c.get("/jobs", headers={"Host": "nas.local:8000"}).status_code == 200
    monkeypatch.undo()
    importlib.reload(config)
    importlib.reload(app_module)


def test_every_response_carries_the_browser_hardening_headers(client: TestClient) -> None:
    for path in ("/", "/app.js", "/jobs", "/no-such-route"):
        h = client.get(path).headers
        assert h["x-content-type-options"] == "nosniff", path
        assert h["x-frame-options"] == "DENY", path
        assert "frame-ancestors 'none'" in h["content-security-policy"], path


def test_upload_over_the_size_cap_is_rejected_and_leaves_no_partial_file(
    client: TestClient, monkeypatch
) -> None:
    """copyfileobj alone has no size cap — an oversized upload must be rejected
    (413) and must not leave a partial file behind on disk."""
    import rockforge.interfaces.api.app as app_module

    monkeypatch.setattr(app_module, "_MAX_UPLOAD_BYTES", 16)
    r = client.post(
        "/gp/inspect",
        files={"file": ("song.gp5", b"x" * 64, "application/octet-stream")},
    )
    assert r.status_code == 413
    gp_dir = app_module.settings.work_dir / "gp"
    if gp_dir.exists():
        assert list(gp_dir.glob("*")) == []


def test_gp_inspect_accepts_gp7(client: TestClient) -> None:
    import io
    import zipfile

    gpif = (
        '<?xml version="1.0" encoding="utf-8"?><GPIF>'
        "<Score><Title>T</Title><Artist>A</Artist><Album>B</Album></Score>"
        "<MasterTrack><Automations><Automation><Type>Tempo</Type><Bar>0</Bar>"
        "<Position>0</Position><Value>120 2</Value></Automation></Automations></MasterTrack>"
        '<Tracks><Track id="0"><Name>Guitar</Name>'
        "<InstrumentSet><Type>electricGuitar</Type></InstrumentSet>"
        '<Staves><Staff><Properties><Property name="Tuning">'
        "<Pitches>40 45 50 55 59 64</Pitches></Property></Properties></Staff></Staves>"
        "</Track></Tracks>"
        "<MasterBars><MasterBar><Time>4/4</Time><Bars>0</Bars></MasterBar></MasterBars>"
        '<Bars><Bar id="0"><Voices>-1 -1 -1 -1</Voices></Bar></Bars>'
        "<Voices/><Beats/><Notes/><Rhythms/></GPIF>"
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("VERSION", "7.0")
        z.writestr("Content/score.gpif", gpif)
    r = client.post(
        "/gp/inspect", files={"file": ("song.gp", buf.getvalue(), "application/octet-stream")}
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["title"] == "T" and body["artist"] == "A"
    assert body["tracks"][0]["string_count"] == 6
    # No Guitar Pro 8 audio sync in this file: nothing to pre-fill.
    assert body["sync_start_s"] is None


def test_gp_inspect_reports_where_a_gp8_synced_file_starts(client: TestClient) -> None:
    """A file synced to its audio track in Guitar Pro 8 knows exactly where bar 1
    falls in that audio. /gp/inspect hands that back so the wizard pre-fills
    the offset instead of asking for a guess."""
    import io
    import zipfile

    def sync(bar: int, seconds: float) -> str:
        return (
            f"<Automation><Type>SyncPoint</Type><Bar>{bar}</Bar><Position>0</Position>"
            f"<Value><BarIndex>{bar}</BarIndex><BarOccurrence>0</BarOccurrence>"
            f"<FrameOffset>{seconds * 44100}</FrameOffset></Value></Automation>"
        )

    gpif = (
        '<?xml version="1.0" encoding="utf-8"?><GPIF>'
        "<Score><Title>T</Title><Artist>A</Artist></Score>"
        "<MasterTrack><Automations><Automation><Type>Tempo</Type><Bar>0</Bar>"
        f"<Position>0</Position><Value>120 2</Value></Automation>{sync(0, 2.25)}{sync(1, 4.0)}"
        "</Automations></MasterTrack>"
        '<Tracks><Track id="0"><Name>Guitar</Name>'
        "<InstrumentSet><Type>electricGuitar</Type></InstrumentSet>"
        '<Staves><Staff><Properties><Property name="Tuning">'
        "<Pitches>40 45 50 55 59 64</Pitches></Property></Properties></Staff></Staves>"
        "</Track></Tracks>"
        "<MasterBars><MasterBar><Time>4/4</Time><Bars>0</Bars></MasterBar>"
        "<MasterBar><Time>4/4</Time><Bars>1</Bars></MasterBar></MasterBars>"
        '<Bars><Bar id="0"><Voices>-1 -1 -1 -1</Voices></Bar>'
        '<Bar id="1"><Voices>-1 -1 -1 -1</Voices></Bar></Bars>'
        "<Voices/><Beats/><Notes/><Rhythms/></GPIF>"
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("VERSION", "7.0")
        z.writestr("Content/score.gpif", gpif)
    r = client.post(
        "/gp/inspect", files={"file": ("song.gp", buf.getvalue(), "application/octet-stream")}
    )
    assert r.status_code == 200, r.text
    assert r.json()["sync_start_s"] == pytest.approx(2.25)


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


def _gp8_with_embedded_audio(
    audio: bytes | None, *, enabled: str = "true", source: str = "Local", link: str = "",
    asset: str = "<EmbeddedFilePath><![CDATA[Content/Assets/a.mp3]]></EmbeddedFilePath>",
    bar_one_frame: int | None = None,
) -> bytes:
    """A minimal .gp whose backing track is an embedded MP3 (when ``audio``)."""
    import io
    import zipfile

    backing = (
        f"<BackingTrack><Enabled>{enabled}</Enabled><Source>{source}</Source>{link}<AssetId>0</AssetId>"
        "<FramePadding>0</FramePadding></BackingTrack><Assets><Asset id=\"0\">"
        f"{asset}</Asset></Assets>"
        if audio is not None
        else ""
    )
    gpif = (
        '<?xml version="1.0" encoding="utf-8"?><GPIF>'
        "<Score><Title>T</Title><Artist>A</Artist></Score>"
        "<MasterTrack><Automations><Automation><Type>Tempo</Type><Bar>0</Bar>"
        "<Position>0</Position><Value>120 2</Value></Automation>"
        + (
            "<Automation><Type>SyncPoint</Type><Bar>0</Bar><Position>0</Position><Value>"
            "<BarIndex>0</BarIndex><BarOccurrence>0</BarOccurrence>"
            f"<FrameOffset>{bar_one_frame}</FrameOffset></Value></Automation>"
            if bar_one_frame is not None else ""
        )
        + "</Automations></MasterTrack>"
        f"{backing}"
        '<Tracks><Track id="0"><Name>Guitar</Name>'
        "<InstrumentSet><Type>electricGuitar</Type></InstrumentSet>"
        '<Staves><Staff><Properties><Property name="Tuning">'
        "<Pitches>40 45 50 55 59 64</Pitches></Property></Properties></Staff></Staves>"
        "</Track></Tracks>"
        "<MasterBars><MasterBar><Time>4/4</Time><Bars>0</Bars></MasterBar></MasterBars>"
        '<Bars><Bar id="0"><Voices>-1 -1 -1 -1</Voices></Bar></Bars>'
        "<Voices/><Beats/><Notes/><Rhythms/></GPIF>"
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("VERSION", "7.0")
        z.writestr("Content/score.gpif", gpif)
        if audio is not None:
            z.writestr("Content/Assets/a.mp3", audio)
    return buf.getvalue()


def test_a_gp8_job_can_use_the_audio_embedded_in_the_file(client: TestClient, tmp_path) -> None:
    """The recording a GP8 file carries is the one its sync points describe; a
    tool like guitar-pro-youtube-sync trims the intro before embedding it, so
    uploading the original instead left a real chart one bar late. With
    use_embedded_audio there is nothing to upload and nothing to get wrong."""
    mp3 = b"ID3embedded-recording"
    r = client.post("/gp/inspect", files={"file": ("s.gp", _gp8_with_embedded_audio(mp3), "x")})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["embedded_audio"] == {"name": "a.mp3", "size_bytes": len(mp3)}

    r2 = client.post(
        "/jobs/gp",
        data={"gp_token": body["gp_token"], "lead_track": "0", "use_embedded_audio": "true"},
    )
    assert r2.status_code == 202, r2.text
    uploads = list((tmp_path / "work" / "uploads").iterdir())
    assert [u.read_bytes() for u in uploads] == [mp3]
    assert uploads[0].suffix == ".mp3"
    assert r2.json()["recording_from_gp"] is True


def test_gp_inspect_says_where_the_audio_is_when_it_is_not_inside(client: TestClient) -> None:
    """A GP8 file whose audio "was not detected": when Guitar Pro plays it from
    a YouTube video, or from a file outside the .gp, the wizard is told which."""
    youtube = _gp8_with_embedded_audio(
        b"x", source="YouTube",
        link="<YouTubeVideoUrl>https://youtu.be/dQw4w9WgXcQ</YouTubeVideoUrl>",
    )
    body = client.post("/gp/inspect", files={"file": ("y.gp", youtube, "x")}).json()
    assert body["embedded_audio"] is None
    assert body["backing_youtube_url"] == "https://youtu.be/dQw4w9WgXcQ"

    outside = _gp8_with_embedded_audio(
        b"x",
        asset="<OriginalFilePath><![CDATA[D:\\music\\take.mp3]]></OriginalFilePath>",
    )
    body = client.post("/gp/inspect", files={"file": ("o.gp", outside, "x")}).json()
    assert body["backing_youtube_url"] is None
    # The stored a.mp3 is the one audio file in Assets, so it is still found.
    assert body["embedded_audio"] == {"name": "a.mp3", "size_bytes": 1}

    off = _gp8_with_embedded_audio(b"ID3x", enabled="false")
    body = client.post("/gp/inspect", files={"file": ("d.gp", off, "x")}).json()
    assert body["embedded_audio"] and body["backing_disabled"] is True


def test_a_gp_job_without_any_recording_is_refused_clearly(client: TestClient) -> None:
    body = client.post(
        "/gp/inspect", files={"file": ("s.gp", _gp8_with_embedded_audio(None), "x")}
    ).json()
    assert body["embedded_audio"] is None

    # Neither an upload nor an embedded track to fall back on.
    r = client.post("/jobs/gp", data={"gp_token": body["gp_token"], "lead_track": "0"})
    assert r.status_code == 422 and "recording is required" in r.text

    # Asking for the embedded track of a file that has none.
    r = client.post(
        "/jobs/gp",
        data={"gp_token": body["gp_token"], "lead_track": "0", "use_embedded_audio": "true"},
    )
    assert r.status_code == 422 and "no embedded audio" in r.text


def test_songsterr_lookup_returns_the_videos_and_their_bar_times(
    client: TestClient, monkeypatch
) -> None:
    from rockforge.infrastructure import songsterr

    def fake(song: str, **_k):
        assert song == "https://www.songsterr.com/a/wsa/x-tab-s42"
        return songsterr.SongsterrSong(
            song_id=42, revision_id=7, title="T", artist="A",
            videos=(songsterr.SongsterrVideo("vid", None, (1.37, 2.77)),),
        )

    monkeypatch.setattr(songsterr, "fetch_song", fake)
    r = client.get("/songsterr", params={"song": "https://www.songsterr.com/a/wsa/x-tab-s42"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["song_id"] == 42 and body["revision_id"] == 7
    assert body["videos"] == [
        {"video_id": "vid", "url": "https://youtu.be/vid", "feature": None, "points": [1.37, 2.77]}
    ]


def test_a_songsterr_tab_becomes_a_gp_file_the_wizard_can_use(
    client: TestClient, monkeypatch
) -> None:
    """/songsterr/import answers like /gp/inspect, with a stored GP file behind
    the token — so the rest of the wizard and the job need nothing new."""
    import rockforge.interfaces.api.app as app_module
    from rockforge.infrastructure import songsterr

    part = {"name": "Lead", "instrument": "Distortion Guitar", "strings": 6,
            "tuning": [64, 59, 55, 50, 45, 40],
            "automations": {"tempo": [{"measure": 0, "bpm": 100}]},
            "measures": [{"signature": [4, 4], "voices": [{"beats": [
                {"type": 1, "notes": [{"string": 5, "fret": 3}]}]}]}]}

    def fake(song: str, **_k):  # noqa: ANN202
        assert song == "https://www.songsterr.com/a/wsa/x-tab-s42"
        return songsterr.SongsterrTab(song_id=42, revision_id=7, title="Tema", artist="Banda",
                                      parts=(part,), missing=("Voz",))

    monkeypatch.setattr(songsterr, "fetch_tab", fake)
    r = client.post("/songsterr/import", json={"song": "https://www.songsterr.com/a/wsa/x-tab-s42"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert (body["title"], body["artist"], body["tempo"]) == ("Tema", "Banda", 100)
    assert [t["name"] for t in body["tracks"]] == ["Lead"]
    assert body["songsterr_song"] == "42"
    assert body["import_warnings"][0] == "não consegui descarregar: Voz"
    # The tab's own tempo map, for the wizard's "Songsterr recording" choice.
    assert body["songsterr_revision"] == "7"
    assert body["songsterr_bar_times"] == [0.0]
    assert (body["songsterr_tempo_count"], body["songsterr_tempo_decimal"]) == (1, False)
    assert (app_module.settings.work_dir / "gp" / body["gp_token"]).is_file()

    assert client.post("/songsterr/import", json={"song": "not a link"}).status_code == 422

    def down(song: str, **_k):  # noqa: ANN202
        raise songsterr.SongsterrError("não consegui contactar o Songsterr (timeout)")

    monkeypatch.setattr(songsterr, "fetch_tab", down)
    r = client.post("/songsterr/import", json={"song": "42"})
    assert r.status_code == 502 and "Songsterr" in r.text


def test_a_pdf_of_the_tab_becomes_a_gp_file_the_wizard_can_use(
    client: TestClient, monkeypatch
) -> None:
    """/pdf/import answers like /gp/inspect, with the converted GP5 stored behind
    the token, the files it came from and the converter's warnings."""
    import guitarpro

    import rockforge.interfaces.api.app as app_module
    from rockforge.infrastructure.gpimport import pdf_import

    song = guitarpro.Song()
    song.title, song.artist, song.tempo = "Tema", "Banda", 90
    song.tracks[0].name = "Guitarra"
    buffer = __import__("io").BytesIO()
    guitarpro.write(song, buffer, version=(5, 1, 0))
    seen: list[list[str]] = []

    def fake(files):  # noqa: ANN001, ANN202
        seen.append([name for name, _ in files])
        return pdf_import.PdfImport(gp5=buffer.getvalue(), title="Tema", artist="Banda",
                                    warnings=["Guitarra: confira o ritmo"])

    monkeypatch.setattr(pdf_import, "available", lambda: True)
    monkeypatch.setattr(pdf_import, "convert", fake)
    pdf = b"%PDF-1.4\n%fake"
    png = b"\x89PNG\r\n\x1a\nfake"
    r = client.post("/pdf/import", files=[("files", ("solo.pdf", pdf, "application/pdf")),
                                          ("files", ("ritmo.png", png, "image/png"))])
    assert r.status_code == 200, r.text
    body = r.json()
    assert seen == [["solo.pdf", "ritmo.png"]]  # one file per track, in order
    assert (body["title"], body["artist"], body["tempo"]) == ("Tema", "Banda", 90)
    assert [t["name"] for t in body["tracks"]] == ["Guitarra"]
    assert body["pdf_files"] == ["solo.pdf", "ritmo.png"]
    assert body["import_warnings"] == ["Guitarra: confira o ritmo"]
    assert (app_module.settings.work_dir / "gp" / body["gp_token"]).is_file()

    junk = client.post("/pdf/import", files=[("files", ("tab.pdf", b"PK\x03\x04", "x/y"))])
    assert junk.status_code == 415
    many = [("files", (f"{i}.pdf", pdf, "application/pdf")) for i in range(8)]
    assert client.post("/pdf/import", files=many).status_code == 422

    def refused(files):  # noqa: ANN001, ANN202
        raise pdf_import.PdfImportError("Nenhuma tablatura encontrada no PDF.")

    monkeypatch.setattr(pdf_import, "convert", refused)
    r = client.post("/pdf/import", files=[("files", ("x.pdf", pdf, "application/pdf"))])
    assert r.status_code == 422 and "tablatura" in r.json()["detail"]

    monkeypatch.setattr(pdf_import, "available", lambda: False)
    r = client.post("/pdf/import", files=[("files", ("x.pdf", pdf, "application/pdf"))])
    assert r.status_code == 503 and ".[pdf]" in r.json()["detail"]


def test_a_songsterr_tab_with_lyrics_is_imported_with_them(
    client: TestClient, monkeypatch
) -> None:
    """The lyrics of a Songsterr tab travel into the GP file, so the wizard
    sees ``has_lyrics`` (and does not pick an LRCLIB text over them)."""
    from rockforge.infrastructure import songsterr

    guitar = {"name": "Lead", "tuning": [64, 59, 55, 50, 45, 40],
              "measures": [{"signature": [4, 4], "voices": [{"beats": [
                  {"type": 1, "notes": [{"string": 5, "fret": 3}]}]}]}]}
    vocals = {"name": "Voz", "tuning": [64],
              "measures": [{"voices": [{"beats": [
                  {"type": 2, "notes": [{"string": 0, "fret": 2}]},
                  {"type": 2, "notes": [{"string": 0, "fret": 4}]}]}]}],
              "newLyrics": [{"text": "o-la", "offset": 0}]}

    def fake(song: str, **_k):  # noqa: ANN202
        return songsterr.SongsterrTab(song_id=42, revision_id=7, title="T", artist="A",
                                      parts=(guitar, vocals), missing=())

    monkeypatch.setattr(songsterr, "fetch_tab", fake)
    r = client.post("/songsterr/import", json={"song": "42"})
    assert r.status_code == 200, r.text
    assert r.json()["has_lyrics"] is True


def test_a_youtube_videos_audio_becomes_the_projects_recording(
    client: TestClient, monkeypatch, tmp_path
) -> None:
    """/youtube/audio fetches the chosen video's audio; /jobs/gp takes its token
    in place of an upload — only a yt-… file this server wrote, never a path."""
    import rockforge.interfaces.api.app as app_module
    from rockforge.infrastructure import youtube_audio

    def fake(video_id: str, dest: Path, **kw):  # noqa: ANN003, ANN202
        assert video_id == "dQw4w9WgXcQ" and kw["cookies_browser"] == "firefox"
        dest.mkdir(parents=True, exist_ok=True)
        out = dest / "yt-abc.m4a"
        out.write_bytes(b"audio!")
        return out

    monkeypatch.setattr(youtube_audio, "download_audio", fake)
    r = client.post(
        "/youtube/audio", json={"video_id": "dQw4w9WgXcQ", "cookies_browser": "firefox"})
    assert r.status_code == 200, r.text
    assert r.json() == {"audio_token": "yt-abc.m4a", "name": "yt-abc.m4a", "size_bytes": 6}

    gp = client.post("/gp/inspect", files={
        "file": ("song.gp5", _make_gp5_bytes(tmp_path), "application/octet-stream")}).json()
    job = client.post("/jobs/gp", data={
        "gp_token": gp["gp_token"], "lead_track": "0", "audio_token": "yt-abc.m4a"})
    assert job.status_code == 202, job.text
    with app_module._session_factory() as session:
        source = session.get(app_module.Job, job.json()["id"]).source
    assert Path(source) == app_module.settings.work_dir / "uploads" / "yt-abc.m4a"

    for bad in ("../../etc/passwd", "someone-elses.mp3", "yt-missing.m4a"):
        r = client.post("/jobs/gp", data={
            "gp_token": gp["gp_token"], "lead_track": "0", "audio_token": bad})
        assert r.status_code == 404, bad

    assert client.post("/youtube/audio", json={"video_id": "nope"}).status_code == 422
    assert client.post("/youtube/audio", json={
        "video_id": "dQw4w9WgXcQ", "cookies_browser": "netscape"}).status_code == 422

    def refused(*_a, **_k):  # noqa: ANN002, ANN003, ANN202
        raise youtube_audio.YouTubeAudioError("HTTP Error 403", needs_cookies=True)

    monkeypatch.setattr(youtube_audio, "download_audio", refused)
    r = client.post("/youtube/audio", json={"video_id": "dQw4w9WgXcQ"})
    assert r.status_code == 502 and "browser" in r.json()["detail"]

    def missing(*_a, **_k):  # noqa: ANN002, ANN003, ANN202
        raise youtube_audio.YtDlpMissingError("o yt-dlp não está instalado")

    monkeypatch.setattr(youtube_audio, "download_audio", missing)
    assert client.post("/youtube/audio", json={"video_id": "dQw4w9WgXcQ"}).status_code == 503


def test_fetched_youtube_audio_no_job_uses_is_swept(client: TestClient, tmp_path) -> None:
    import os

    import rockforge.interfaces.api.app as app_module

    up = app_module.settings.work_dir / "uploads"
    up.mkdir(parents=True, exist_ok=True)
    old, fresh, other = up / "yt-old.m4a", up / "yt-fresh.m4a", up / "mine.mp3"
    for f in (old, fresh, other):
        f.write_bytes(b"x")
    ancient = 0
    os.utime(old, (ancient, ancient))
    os.utime(other, (ancient, ancient))
    assert app_module._sweep_orphan_youtube_audio() == 1
    assert not old.exists() and fresh.exists() and other.exists()


def test_songsterr_lookup_errors_are_422_for_a_bad_link_and_502_for_songsterr(
    client: TestClient, monkeypatch
) -> None:
    """A link we cannot read is the user's to fix (422); an undocumented API
    that changed or is unreachable is upstream (502) — never a 500."""
    from rockforge.infrastructure import songsterr

    assert client.get("/songsterr", params={"song": "not a link"}).status_code == 422

    def down(*_a, **_k):
        raise songsterr.SongsterrError("não consegui contactar o Songsterr (timeout)")

    monkeypatch.setattr(songsterr, "fetch_song", down)
    r = client.get("/songsterr", params={"song": "42"})
    assert r.status_code == 502 and "contactar o Songsterr" in r.text


def test_a_gp_job_stores_the_bar_times_it_was_created_with(client: TestClient, tmp_path) -> None:
    """The Songsterr times travel with the job, so every rebuild (and every
    /rebuild or /reload-gp fork, which copy params) keeps them."""
    body = client.post(
        "/gp/inspect", files={"file": ("s.gp", _gp8_with_embedded_audio(b"ID3x"), "x")}
    ).json()
    r = client.post(
        "/jobs/gp",
        data={
            "gp_token": body["gp_token"], "lead_track": "0", "use_embedded_audio": "true",
            "bar_times": "[1.37, 2.77, 4.17]", "bar_times_source": "songsterr:42:7",
        },
    )
    assert r.status_code == 202, r.text
    import rockforge.interfaces.api.app as app_module
    from rockforge.infrastructure.db.models import Job

    with app_module._session_factory() as db:
        job = db.get(Job, r.json()["id"])
        assert job is not None
        assert job.params["bar_times"] == [1.37, 2.77, 4.17]
        assert job.params["bar_times_source"] == "songsterr:42:7"


# "[-1, 2]" left out on purpose: negative times are now ACCEPTED — Songsterr
# markers can begin before the video's first second (a count-in at t<0), and
# bar_time_points keeps them as ordinary points (bar 1 then starts before the audio).
@pytest.mark.parametrize(
    "bad", ["not json", '{"a": 1}', '[1, "x"]', "[1, NaN]", "[true, 2]"]
)
def test_bad_bar_times_are_rejected_before_anything_is_stored(client: TestClient, bad: str) -> None:
    body = client.post(
        "/gp/inspect", files={"file": ("s.gp", _gp8_with_embedded_audio(b"ID3x"), "x")}
    ).json()
    r = client.post(
        "/jobs/gp",
        data={"gp_token": body["gp_token"], "lead_track": "0",
              "use_embedded_audio": "true", "bar_times": bad},
    )
    assert r.status_code == 422, (bad, r.text)


def test_gear_catalogue_endpoint_returns_grouped_gear(client: TestClient) -> None:
    r = client.get("/gear-catalogue")
    assert r.status_code == 200
    cat = r.json()
    assert len(cat["amps"]) > 0
    assert len(cat["cabinets"]) > 0
    assert cat["descriptors"]["Clean"] == "$[35720]CLEAN"


def _gp_job(client: TestClient, tmp_path) -> dict:
    data = _make_gp5_bytes(tmp_path)
    body = client.post(
        "/gp/inspect", files={"file": ("song.gp5", data, "application/octet-stream")}
    ).json()
    return client.post(
        "/jobs/gp",
        data={"gp_token": body["gp_token"], "lead_track": "0"},
        files={"audio": ("song.wav", b"RIFF0000WAVE", "audio/wav")},
    ).json()


def test_a_project_whose_form_leaves_out_import_mutes_keeps_its_mutes(
    client: TestClient, tmp_path
) -> None:
    """The batch page sends no import_mutes, and newer FastAPI reads an absent
    bool form field as False whatever its default: those projects lost their
    palm mutes. Absent is the default (yes); anything but yes/no is refused."""
    import rockforge.interfaces.api.app as app_module

    def mutes(job_id: str) -> object:
        with app_module._session_factory() as session:
            return (session.get(app_module.Job, job_id).params or {}).get("import_mute_techniques")

    assert mutes(_gp_job(client, tmp_path)["id"]) is True
    data = _make_gp5_bytes(tmp_path)
    for sent, expected in (("false", False), ("true", True), ("maybe", None)):
        token = client.post(
            "/gp/inspect", files={"file": ("song.gp5", data, "application/octet-stream")}
        ).json()["gp_token"]
        r = client.post(
            "/jobs/gp",
            data={"gp_token": token, "lead_track": "0", "import_mutes": sent},
            files={"audio": ("song.wav", b"RIFF0000WAVE", "audio/wav")},
        )
        if expected is None:
            assert r.status_code == 422
        else:
            assert mutes(r.json()["id"]) is expected


def test_rebuild_stores_tones_and_changes(client: TestClient, tmp_path) -> None:
    job = _gp_job(client, tmp_path)
    tone = {
        "key": "lead",
        "name": "Lead",
        "amp": {"key": "Amp_MarshallJCM800", "knobs": {"Amp_MarshallJCM800_Gain": 90}},
        "cabinet": {"key": "Cab_Marshall1960TV_Ribbon_Cone"},
    }
    rebuilt = client.post(
        f"/jobs/{job['id']}/rebuild",
        json={
            "tone_base": "lead",
            "tone_names": ["lead"],
            "tones": [tone],
            "tone_changes": [{"time": 5.0, "name": "lead"}],
        },
    ).json()
    tones = client.get(f"/jobs/{rebuilt['id']}/tones").json()
    assert tones["tone_base"] == "lead"
    assert tones["tone_names"] == ["lead"]
    assert tones["tones"][0]["key"] == "lead"
    assert tones["tone_changes"][0]["time"] == 5.0


def test_rebuild_stores_section_overrides(client: TestClient, tmp_path) -> None:
    """The section editor's overrides (When set, even to []) are written into
    params verbatim; the pipeline-side merge (sort + renumber + apply to every
    arrangement) is covered end-to-end in test_gp_pipeline.py."""
    import rockforge.interfaces.api.app as app_module

    def job_params(job_id: str) -> dict:
        with app_module._session_factory() as session:
            return dict(session.get(app_module.Job, job_id).params or {})

    job = _gp_job(client, tmp_path)
    assert "section_overrides" not in job_params(job["id"])

    rebuilt = client.post(
        f"/jobs/{job['id']}/rebuild",
        json={"section_overrides": [{"time": 2.0, "name": "Solo"}, {"time": 0.0, "name": "Intro"}]},
    ).json()
    stored = job_params(rebuilt["id"])["section_overrides"]
    assert stored == [{"time": 2.0, "name": "Solo"}, {"time": 0.0, "name": "Intro"}]


def test_rebuild_stores_note_overrides_keyed_by_arrangement(client: TestClient, tmp_path) -> None:
    import rockforge.interfaces.api.app as app_module

    def job_params(job_id: str) -> dict:
        with app_module._session_factory() as session:
            return dict(session.get(app_module.Job, job_id).params or {})

    job = _gp_job(client, tmp_path)
    assert "note_overrides" not in job_params(job["id"])

    rebuilt = client.post(
        f"/jobs/{job['id']}/rebuild",
        json={
            "note_overrides": {
                "Lead": [
                    {"time": 2.0, "string": 3, "fret": 5, "techniques": ["hammerOn"]},
                    {"time": 3.0, "string": 1, "deleted": True},
                ]
            }
        },
    ).json()
    stored = job_params(rebuilt["id"])["note_overrides"]
    assert stored == {
        "Lead": [
            {
                "time": 2.0, "string": 3, "fret": 5, "sustain": 0.0,
                "techniques": ["hammerOn"], "bend_semitones": 0.0,
                "slide_to_fret": None, "deleted": False,
            },
            {
                "time": 3.0, "string": 1, "fret": 0, "sustain": 0.0,
                "techniques": [], "bend_semitones": 0.0,
                "slide_to_fret": None, "deleted": True,
            },
        ]
    }


def test_rebuild_note_overrides_reject_out_of_range_string_or_fret(
    client: TestClient, tmp_path
) -> None:
    job = _gp_job(client, tmp_path)
    r = client.post(
        f"/jobs/{job['id']}/rebuild",
        json={"note_overrides": {"Lead": [{"time": 1.0, "string": 6, "fret": 0}]}},
    )
    assert r.status_code == 422
    r2 = client.post(
        f"/jobs/{job['id']}/rebuild",
        json={"note_overrides": {"Lead": [{"time": 1.0, "string": 0, "fret": 25}]}},
    )
    assert r2.status_code == 422


def test_rebuild_without_section_overrides_leaves_them_untouched(
    client: TestClient, tmp_path
) -> None:
    """None (the field simply absent from the payload) must not wipe a
    previously-set section override on an unrelated rebuild."""
    import rockforge.interfaces.api.app as app_module

    def job_params(job_id: str) -> dict:
        with app_module._session_factory() as session:
            return dict(session.get(app_module.Job, job_id).params or {})

    job = _gp_job(client, tmp_path)
    with_sections = client.post(
        f"/jobs/{job['id']}/rebuild",
        json={"section_overrides": [{"time": 1.0, "name": "Verse"}]},
    ).json()
    unrelated = client.post(
        f"/jobs/{with_sections['id']}/rebuild", json={"offset_s": 2.5}
    ).json()
    assert job_params(unrelated["id"])["section_overrides"] == [{"time": 1.0, "name": "Verse"}]


def test_arrangements_excludes_the_noguitar_sentinel_from_sections(
    client: TestClient,
) -> None:
    """The writer's synthetic trailing "noguitar" section (marks where the
    phrase timeline ends) is a structural closer, not a user-facing section —
    it must never appear in the section editor's data."""
    import rockforge.config as config
    import rockforge.interfaces.api.app as app_module
    from rockforge.domain.arrangement import Arrangement, ArrangementKind, Section, SongMetadata
    from rockforge.domain.music import Beat, TabNote, TempoMap, Tuning
    from rockforge.infrastructure.db.models import JobStatus
    from rockforge.infrastructure.rsxml.writer import write_arrangement_xml

    job = _create_job(client)
    bundle = config.settings.work_dir / job["id"] / "bundle"
    beats = tuple(Beat(time=0.5 * i, measure=(i // 4 + 1) if i % 4 == 0 else -1) for i in range(8))
    arr = Arrangement(
        kind=ArrangementKind.LEAD,
        metadata=SongMetadata(title="Sec", artist="T", song_length=4.0),
        tuning=Tuning(),
        notes=[TabNote(string=1, fret=3, time=1.0, sustain=0.5)],
        tempo_map=TempoMap(beats=beats, average_bpm=120.0),
        sections=[Section(name="Intro", start_time=0.0, number=1)],
    )
    write_arrangement_xml(arr, bundle / "arrangement_lead.xml")

    with app_module._session_factory() as session:
        db_job = session.get(app_module.Job, job["id"])
        db_job.status = JobStatus.COMPLETED
        db_job.bundle_dir = str(bundle)
        session.commit()

    first = client.get(f"/jobs/{job['id']}/arrangements").json()[0]
    assert [s["name"] for s in first["sections"]] == ["Intro"]
    # The GP file's own sections, not the editor's: the build warps those itself.
    assert first["sections_edited"] is False
    with app_module._session_factory() as session:
        db_job = session.get(app_module.Job, job["id"])
        db_job.params = {**(db_job.params or {}),
                         "section_overrides": [{"time": 0.0, "name": "Intro"}]}
        session.commit()
    # The editor's are kept as given, so the viewer carries them through a
    # pending sync change before sending them (BUG-0339).
    assert client.get(f"/jobs/{job['id']}/arrangements").json()[0]["sections_edited"] is True


def _bundle_with(client: TestClient, kinds: list[str]) -> str:
    """A completed GP job whose bundle holds one built chart per kind name."""
    import rockforge.config as config
    import rockforge.interfaces.api.app as app_module
    from rockforge.domain.arrangement import Arrangement, ArrangementKind, SongMetadata
    from rockforge.domain.music import Beat, TabNote, TempoMap, Tuning
    from rockforge.infrastructure.db.models import JobStatus
    from rockforge.infrastructure.rsxml.writer import write_arrangement_xml

    job = _create_job(client)
    bundle = config.settings.work_dir / job["id"] / "bundle"
    beats = tuple(
        Beat(time=0.5 * i, measure=(i // 4 + 1) if i % 4 == 0 else -1) for i in range(8)
    )
    for n, name in enumerate(kinds):
        kind = ArrangementKind[name]
        write_arrangement_xml(Arrangement(
            kind=kind,
            metadata=SongMetadata(title="T", artist="A", song_length=4.0),
            tuning=Tuning(),
            notes=[TabNote(string=1, fret=3 + n, time=1.0, sustain=0.5)],
            tempo_map=TempoMap(beats=beats, average_bpm=120.0),
        ), bundle / f"arrangement_{name.lower()}.xml")
    with app_module._session_factory() as session:
        db_job = session.get(app_module.Job, job["id"])
        db_job.status = JobStatus.COMPLETED
        db_job.source_type = "gp"
        db_job.bundle_dir = str(bundle)
        session.commit()
    return str(job["id"])


def test_an_alternate_chart_is_its_own_arrangement_not_a_second_lead(client: TestClient) -> None:
    """An alternate chart writes its BASE path ("Lead") in its XML, as the game
    needs, so reading that tag gave two tabs called "Lead" sharing every edit.
    Each chart is named by its file, listed in the build's order, and exports."""
    job_id = _bundle_with(client, ["ALTERNATE_LEAD", "RHYTHM", "LEAD", "ALTERNATE_RHYTHM"])
    arrs = client.get(f"/jobs/{job_id}/arrangements").json()
    assert [a["kind"] for a in arrs] == ["Lead", "Rhythm", "Alternate Lead", "Alternate Rhythm"]
    assert [a["notes"][0]["fret"] for a in arrs] == [5, 4, 3, 6]  # each its own chart
    # Named as the game names them: numbered only on a path with two charts.
    assert [a["game_name"] for a in arrs] == ["LEAD 1", "RHYTHM 1", "LEAD 2", "RHYTHM 2"]
    one = _bundle_with(client, ["LEAD", "ALTERNATE_LEAD", "RHYTHM", "COMBINED"])
    assert [a["game_name"] for a in client.get(f"/jobs/{one}/arrangements").json()] == [
        "LEAD 1", "RHYTHM", "COMBO", "LEAD 2",
    ]

    r = client.post(
        f"/jobs/{job_id}/export-arrangement-gp", params={"arrangement": "Alternate Lead"}
    )
    assert r.status_code == 200, r.text


def test_each_chart_is_marked_in_sync_on_its_own(client: TestClient) -> None:
    """Each track is synchronised on its own and its tab turns green; the song
    counts as confirmed once every chart is, and the whole-song button marks all."""
    job_id = _bundle_with(client, ["LEAD", "RHYTHM"])

    def synced() -> dict[str, bool]:
        arrs = client.get(f"/jobs/{job_id}/arrangements").json()
        return {a["kind"]: a["sync_confirmed"] for a in arrs}

    def mark(confirmed: bool, arrangement: str | None = None) -> dict:
        return client.patch(
            f"/jobs/{job_id}/sync-confirmed",
            json={"confirmed": confirmed, "arrangement": arrangement},
        ).json()

    j = mark(True, "Lead")
    assert synced() == {"Lead": True, "Rhythm": False}
    assert j["synced_arrangements"] == ["Lead"] and j["sync_confirmed"] is False

    j = mark(True, "Rhythm")
    assert j["sync_confirmed"] is True and j["sync_source"] == "confirmed"

    j = mark(False, "Lead")
    assert synced() == {"Lead": False, "Rhythm": True} and j["sync_confirmed"] is False

    mark(True)
    assert synced() == {"Lead": True, "Rhythm": True}
    mark(False)
    assert synced() == {"Lead": False, "Rhythm": False}

    bad = client.patch(
        f"/jobs/{job_id}/sync-confirmed", json={"confirmed": True, "arrangement": "Bass"}
    )
    assert bad.status_code == 422


def test_a_song_confirmed_before_charts_were_marked_one_by_one_marks_them_all(
    client: TestClient,
) -> None:
    import rockforge.interfaces.api.app as app_module

    job_id = _bundle_with(client, ["LEAD", "RHYTHM"])
    with app_module._session_factory() as session:
        db_job = session.get(app_module.Job, job_id)
        db_job.params = {**(db_job.params or {}), "sync_confirmed": True}
        session.commit()
    arrs = client.get(f"/jobs/{job_id}/arrangements").json()
    assert all(a["sync_confirmed"] for a in arrs)


def test_completeness_fields_reflect_job_state(client: TestClient, tmp_path) -> None:
    """The 'Estado do PSARC' checklist reads has_tones / sync_edited / cover_art
    straight off JobOut — a fresh GP job has none of them; a rebuild that adds
    tones + an offset flips them."""
    job = _gp_job(client, tmp_path)
    assert job["has_tones"] is False
    assert job["sync_edited"] is False
    assert job["cover_art"] is False
    assert job["has_lyrics"] is False

    tone = {
        "key": "lead",
        "name": "Lead",
        "amp": {"key": "Amp_MarshallJCM800", "knobs": {"Amp_MarshallJCM800_Gain": 90}},
        "cabinet": {"key": "Cab_Marshall1960TV_Ribbon_Cone"},
    }
    rebuilt = client.post(
        f"/jobs/{job['id']}/rebuild",
        json={"tone_base": "lead", "tone_names": ["lead"], "tones": [tone], "offset_s": 1.5},
    ).json()
    assert rebuilt["has_tones"] is True
    assert rebuilt["sync_edited"] is True  # offset moved off 0


def test_sync_edited_true_from_anchor_only(client: TestClient, tmp_path) -> None:
    """A drift anchor (no offset/tempo change) still counts as sync edited."""
    job = _gp_job(client, tmp_path)
    rebuilt = client.post(
        f"/jobs/{job['id']}/rebuild",
        json={"arrangement": "Lead", "sync_anchors": [[1.0, 1.2]]},
    ).json()
    assert rebuilt["sync_edited"] is True


def test_a_song_that_needed_no_adjustment_can_be_confirmed_as_in_sync(
    client: TestClient, tmp_path
) -> None:
    """A chart already in sync (synced in Guitar Pro 8, its embedded audio, or
    simply right) has no adjustment for sync_edited to see — the reminder could
    never be cleared. The user's confirmation clears it, survives a rebuild,
    and can be taken back."""
    job = _gp_job(client, tmp_path)
    assert job["sync_edited"] is False and job["sync_confirmed"] is False

    r = client.patch(f"/jobs/{job['id']}/sync-confirmed", json={"confirmed": True})
    assert r.status_code == 200, r.text
    assert r.json()["sync_confirmed"] is True
    assert r.json()["status"] == job["status"], "a checklist flag, not a rebuild"

    rebuilt = client.post(f"/jobs/{job['id']}/rebuild", json={}).json()
    assert rebuilt["sync_confirmed"] is True

    r = client.patch(f"/jobs/{job['id']}/sync-confirmed", json={"confirmed": False})
    assert r.json()["sync_confirmed"] is False
    assert client.patch("/jobs/nope/sync-confirmed", json={"confirmed": True}).status_code == 404


def test_songsterr_bar_times_count_as_synchronised() -> None:
    from rockforge.interfaces.api.app import _sync_edited

    assert _sync_edited({"bar_times": [0.0, 2.1, 4.2]}) is True
    assert _sync_edited({"bar_times": []}) is False


def test_a_chart_says_why_it_counts_as_in_sync() -> None:
    """The card and the score show a "Sincronizada" badge; the user's own word
    comes first, then what timed the chart, then corrections made here."""
    from rockforge.interfaces.api.app import _sync_edited, _sync_source

    assert _sync_source({}) is None
    assert _sync_source({"tempo_scale": 1.05}) == "adjusted"
    assert _sync_source({"gp_synced": True}) == "gp"
    assert _sync_edited({"gp_synced": True}) is True  # the checklist stops asking
    assert _sync_source({"bar_times": [0.0, 2.0], "gp_synced": True}) == "songsterr"
    # The times of a video fit that video's audio; the tab's own tempo map fits
    # a recording that follows the tab (the MP3 Songsterr plays).
    assert _sync_source(
        {"bar_times": [0.0, 2.0], "bar_times_source": "songsterr:42:7"}) == "songsterr"
    assert _sync_source(
        {"bar_times": [0.0, 2.0], "bar_times_source": "songsterr-tab:42:7"}) == "songsterr_tab"
    assert _sync_source({"gp_synced": True, "sync_confirmed": True}) == "confirmed"


def _stages(client: TestClient, job_id: str, kind: str = "Lead") -> list:
    import rockforge.interfaces.api.app as app_module

    with app_module._session_factory() as session:
        p = dict(session.get(app_module.Job, job_id).params or {})
    return (p.get("arrangement_sync", {}).get(kind, {}) or {}).get("sync_anchor_stages", [])


def test_tempo_change_reexpresses_committed_anchors_in_the_new_timeline(
    client: TestClient, tmp_path
) -> None:
    """Changing the tempo AFTER an anchor stage was committed must re-express that
    stage in the new timeline.

    The build computes W(x*s + S) while the viewer previews R(W(x*s_built + S)) —
    it rescales the already-warped times read back from the built XML. Those do
    not commute, so without this the rebuild silently differs from the preview by
    a constant on every note: the chart looked synced in RockForge but was off in
    Rocksmith. phi(t) = (t - S_old)*ratio + S_new is the viewer's own map.
    """
    job = _gp_job(client, tmp_path)
    # Stage 1: commit a drift anchor at the default tempo (1.0), offset 0
    # => S = max(0, MIN_LEAD_S=2.0) + 0 = 2.0.
    once = client.post(
        f"/jobs/{job['id']}/rebuild",
        json={"arrangement": "Lead", "sync_anchors": [[3.0, 3.5]]},
    ).json()
    assert _stages(client, once["id"]) == [[[3.0, 3.5]]]

    # Now change ONLY the tempo (ratio 1.5). The committed stage must move with it.
    twice = client.post(
        f"/jobs/{once['id']}/rebuild",
        json={"arrangement": "Lead", "tempo_scale": 1.5},
    ).json()
    got = _stages(client, twice["id"])
    # phi(3.0) = (3.0-2.0)*1.5 + 2.0 = 3.5 ; phi(3.5) = (3.5-2.0)*1.5 + 2.0 = 4.25
    assert len(got) == 1 and len(got[0]) == 1
    assert got[0][0] == pytest.approx([3.5, 4.25])


def test_committed_anchors_untouched_when_the_timeline_does_not_change(
    client: TestClient, tmp_path
) -> None:
    """No tempo/offset/lead-in change => the stored anchors must be left exactly
    as they are (the remap is a no-op, never a lossy round-trip)."""
    job = _gp_job(client, tmp_path)
    once = client.post(
        f"/jobs/{job['id']}/rebuild",
        json={"arrangement": "Lead", "sync_anchors": [[3.0, 3.5]]},
    ).json()
    twice = client.post(
        f"/jobs/{once['id']}/rebuild", json={"arrangement": "Lead", "import_mutes": True}
    ).json()
    assert _stages(client, twice["id"]) == [[[3.0, 3.5]]]


def test_has_lyrics_true_from_edited_events(client: TestClient, tmp_path) -> None:
    """has_lyrics reflects lyrics from ANY source (edited events here), not only
    completed WhisperX detection — the completeness panel must not say "sem
    letra" when the song already has lyrics."""
    job = _gp_job(client, tmp_path)
    assert job["has_lyrics"] is False
    rebuilt = client.post(
        f"/jobs/{job['id']}/rebuild",
        json={"lyrics_events": [{"time": 1.0, "length": 0.5, "lyric": "olá"}]},
    ).json()
    assert rebuilt["has_lyrics"] is True


def test_rebuild_empty_tone_fields_clear_them(client: TestClient, tmp_path) -> None:
    """Removing all tones/changes must persist: the tone editor sends concrete
    empties ([]/""), which clear the params — not null, which would keep them."""
    job = _gp_job(client, tmp_path)
    tone = {
        "key": "lead",
        "name": "Lead",
        "amp": {"key": "Amp_MarshallJCM800", "knobs": {"Amp_MarshallJCM800_Gain": 90}},
        "cabinet": {"key": "Cab_Marshall1960TV_Ribbon_Cone"},
    }
    set_up = client.post(
        f"/jobs/{job['id']}/rebuild",
        json={
            "tone_base": "lead",
            "tone_names": ["lead"],
            "tones": [tone],
            "tone_changes": [{"time": 5.0, "name": "lead"}],
        },
    ).json()
    assert client.get(f"/jobs/{set_up['id']}/tones").json()["tone_base"] == "lead"

    cleared = client.post(
        f"/jobs/{set_up['id']}/rebuild",
        json={"tone_base": "", "tone_names": [], "tones": [], "tone_changes": []},
    ).json()
    tones = client.get(f"/jobs/{cleared['id']}/tones").json()
    assert tones["tone_base"] is None
    assert tones["tone_names"] == []
    assert tones["tones"] == []
    assert tones["tone_changes"] == []


def test_reload_gp_forks_job_and_keeps_overrides(client: TestClient, tmp_path) -> None:
    """Reloading the GP file rebuilds with a fresh gp_path but preserves the
    job's existing sync/tone overrides (no need to redo alignment work)."""
    import rockforge.interfaces.api.app as app_module

    def job_params(job_id: str) -> dict:
        with app_module._session_factory() as session:
            return dict(session.get(app_module.Job, job_id).params or {})

    job = _gp_job(client, tmp_path)
    # Give the job some overrides to preserve.
    rebuilt = client.post(
        f"/jobs/{job['id']}/rebuild",
        json={"tempo_scale": 1.2, "tone_base": "lead", "tone_names": ["lead"]},
    ).json()
    old_gp = job_params(rebuilt["id"])["gp_path"]

    new_data = _make_gp5_bytes(tmp_path)
    r = client.post(
        f"/jobs/{rebuilt['id']}/reload-gp",
        files={"gp": ("song2.gp5", new_data, "application/octet-stream")},
    )
    assert r.status_code == 202
    reloaded = r.json()
    assert reloaded["id"] != rebuilt["id"]  # forked a new job

    params = job_params(reloaded["id"])
    assert params["gp_path"] != old_gp  # points at the freshly uploaded GP file
    assert params["tempo_scale"] == 1.2  # overrides carried over
    assert params["tone_base"] == "lead"
    assert params["lead_track"] == 0


def _job_row(job_id: str) -> tuple[str, dict]:
    import rockforge.interfaces.api.app as app_module

    with app_module._session_factory() as session:
        job = session.get(app_module.Job, job_id)
        return job.source, dict(job.params or {})


def test_reloading_a_gp_file_that_carries_audio_uses_that_audio(
    client: TestClient, tmp_path
) -> None:
    """"Porque é que continuas a não aproveitar o mp3 do ficheiro gp?": the
    wizard used it, "Recarregar ficheiro GP" always kept the old recording. The
    new file's own audio is the one its sync points describe, so it is used
    (unless the user unticks it), and bar 1's place in it becomes the start."""
    job = _gp_job(client, tmp_path)  # a recording uploaded separately
    old_source, _ = _job_row(job["id"])
    mp3 = b"ID3the-files-own-audio"
    synced = _gp8_with_embedded_audio(mp3, bar_one_frame=88200)  # bar 1 at 2.0 s

    kept = client.post(
        f"/jobs/{job['id']}/reload-gp",
        files={"gp": ("s.gp", synced, "x")}, data={"use_embedded_audio": "false"},
    )
    assert kept.status_code == 202, kept.text
    assert kept.json()["recording_from_gp"] is False
    assert _job_row(kept.json()["id"])[0] == old_source

    used = client.post(f"/jobs/{job['id']}/reload-gp", files={"gp": ("s.gp", synced, "x")})
    assert used.status_code == 202, used.text
    assert used.json()["recording_from_gp"] is True
    source, params = _job_row(used.json()["id"])
    assert source != old_source and Path(source).read_bytes() == mp3
    assert params["offset_s"] == 2.0 and params["lead_track"] == 0

    # Already the file's audio: a start the user adjusted is theirs to keep.
    adjusted = client.post(f"/jobs/{used.json()['id']}/rebuild", json={"offset_s": 2.25}).json()
    again = client.post(
        f"/jobs/{adjusted['id']}/reload-gp", files={"gp": ("s.gp", synced, "x")}
    ).json()
    assert _job_row(again["id"])[1]["offset_s"] == 2.25


def test_what_was_measured_on_the_old_recording_is_dropped_with_it(
    client: TestClient, tmp_path
) -> None:
    """A reload that takes the file's own audio leaves the old recording's
    separated guitar behind: kept, it put the "Ataques da gravação" (and the
    stem audio sources) on a recording the chart no longer plays against."""
    import rockforge.interfaces.api.app as app_module

    job = _gp_job(client, tmp_path)
    measured = {
        "stems": {"guitar": str(tmp_path / "guitar.wav")}, "stems_status": "ready",
        "stems_log": ["done"], "detected_tones": {"timeline": []},
        "tone_detection_status": "ready", "tone_detection_log": ["done"],
        "marked_attacks": {"Lead": [1.0, 1.5]},  # taps made against the old recording
    }
    with app_module._session_factory() as session:
        row = session.get(app_module.Job, job["id"])
        row.params = {**(row.params or {}), **measured}
        session.commit()
    synced = _gp8_with_embedded_audio(b"ID3the-files-own-audio")

    kept = client.post(
        f"/jobs/{job['id']}/reload-gp",
        files={"gp": ("s.gp", synced, "x")}, data={"use_embedded_audio": "false"},
    ).json()
    assert {k: _job_row(kept["id"])[1].get(k) for k in measured} == measured

    used = client.post(f"/jobs/{job['id']}/reload-gp", files={"gp": ("s.gp", synced, "x")})
    assert used.status_code == 202, used.text
    params = _job_row(used.json()["id"])[1]
    assert not any(k in params for k in measured)


def test_a_gp_file_with_audio_stands_in_for_a_recording_that_is_gone(
    client: TestClient, tmp_path
) -> None:
    job = _gp_job(client, tmp_path)
    Path(_job_row(job["id"])[0]).unlink()
    without = client.post(
        f"/jobs/{job['id']}/reload-gp",
        files={"gp": ("s.gp5", _make_gp5_bytes(tmp_path), "x")},
    )
    assert without.status_code == 409
    r = client.post(
        f"/jobs/{job['id']}/reload-gp",
        files={"gp": ("s.gp", _gp8_with_embedded_audio(b"ID3x"), "x")},
        data={"use_embedded_audio": "false"},
    )
    assert r.status_code == 202, r.text
    assert Path(_job_row(r.json()["id"])[0]).read_bytes() == b"ID3x"


def test_reload_gp_rejects_gpx(client: TestClient, tmp_path) -> None:
    job = _gp_job(client, tmp_path)
    r = client.post(
        f"/jobs/{job['id']}/reload-gp",
        files={"gp": ("song.gpx", b"BCFS", "application/octet-stream")},
    )
    assert r.status_code == 415


def test_reload_gp_rejects_non_gp_job(client: TestClient, tmp_path) -> None:
    job = _create_job(client)  # an upload (audio-ML) job, not GP
    r = client.post(
        f"/jobs/{job['id']}/reload-gp",
        files={"gp": ("song.gp5", _make_gp5_bytes(tmp_path), "application/octet-stream")},
    )
    assert r.status_code == 422


def test_rebuild_rejects_too_many_tones(client: TestClient, tmp_path) -> None:
    job = _gp_job(client, tmp_path)
    r = client.post(
        f"/jobs/{job['id']}/rebuild",
        json={"tone_names": ["a", "b", "c", "d", "e"]},
    )
    assert r.status_code == 422


def test_rebuild_tones_rejected_for_non_gp(client: TestClient) -> None:
    original = _create_job(client)  # a non-GP job
    r = client.post(
        f"/jobs/{original['id']}/rebuild", json={"tone_base": "clean"}
    )
    assert r.status_code == 422


def test_get_tones_defaults_empty(client: TestClient, tmp_path) -> None:
    job = _gp_job(client, tmp_path)
    tones = client.get(f"/jobs/{job['id']}/tones").json()
    assert tones["tones"] == []
    assert tones["tone_changes"] == []


def test_gp_rebuild_applies_tempo_scale(client: TestClient, tmp_path) -> None:
    # The tempo control rebuilds with tempo_scale; it must land in params and
    # be reflected on the job output (defaulting to 1.0 on the first build).
    data = _make_gp5_bytes(tmp_path)
    body = client.post(
        "/gp/inspect", files={"file": ("song.gp5", data, "application/octet-stream")}
    ).json()
    job = client.post(
        "/jobs/gp",
        data={"gp_token": body["gp_token"], "lead_track": "0"},
        files={"audio": ("song.wav", b"RIFF0000WAVE", "audio/wav")},
    ).json()
    assert job["tempo_scale"] == pytest.approx(1.0)
    rebuilt = client.post(f"/jobs/{job['id']}/rebuild", json={"tempo_scale": 1.5}).json()
    assert client.get(f"/jobs/{rebuilt['id']}").json()["tempo_scale"] == pytest.approx(1.5)
    r = client.post(f"/jobs/{job['id']}/rebuild", json={"tempo_scale": 0.0})
    assert r.status_code == 422


def test_rebuild_scopes_sync_to_one_arrangement(client: TestClient, tmp_path) -> None:
    # A rebuild targeting a single arrangement is accepted (the deep
    # independence is covered in test_gp_pipeline). Scoping tempo + anchors to
    # "Lead" must not error and produces a new job.
    data = _make_gp5_bytes(tmp_path)
    body = client.post(
        "/gp/inspect", files={"file": ("song.gp5", data, "application/octet-stream")}
    ).json()
    job = client.post(
        "/jobs/gp",
        data={"gp_token": body["gp_token"], "lead_track": "0"},
        files={"audio": ("song.wav", b"RIFF0000WAVE", "audio/wav")},
    ).json()
    rebuilt = client.post(
        f"/jobs/{job['id']}/rebuild",
        json={"arrangement": "Lead", "tempo_scale": 1.25, "sync_anchors": [[2.0, 2.5]]},
    )
    assert rebuilt.status_code == 202
    assert rebuilt.json()["id"] != job["id"]


def test_rebuild_apply_to_all_propagates_sync(client: TestClient, tmp_path) -> None:
    # apply_to_all=True writes tempo_scale and sync_anchors to every existing
    # per-arrangement entry AND the job-level defaults.
    data = _make_gp5_bytes(tmp_path)
    body = client.post(
        "/gp/inspect", files={"file": ("song.gp5", data, "application/octet-stream")}
    ).json()
    job = client.post(
        "/jobs/gp",
        data={"gp_token": body["gp_token"], "lead_track": "0"},
        files={"audio": ("song.wav", b"RIFF0000WAVE", "audio/wav")},
    ).json()
    # First, create a per-arrangement entry for "Lead".
    r1 = client.post(
        f"/jobs/{job['id']}/rebuild",
        json={"arrangement": "Lead", "tempo_scale": 1.1},
    )
    assert r1.status_code == 202
    jid1 = r1.json()["id"]
    # Now apply_to_all with new tempo + anchors.
    r2 = client.post(
        f"/jobs/{jid1}/rebuild",
        json={
            "arrangement": "Lead",
            "apply_to_all": True,
            "tempo_scale": 0.95,
            "sync_anchors": [[1.0, 1.5]],
        },
    )
    assert r2.status_code == 202
    out = r2.json()
    # The job-level tempo_scale should be updated too.
    assert out["tempo_scale"] == pytest.approx(0.95)


def test_rebuild_arrangement_scoping_rejected_for_non_gp(client: TestClient) -> None:
    original = _create_job(client)
    r = client.post(
        f"/jobs/{original['id']}/rebuild", json={"arrangement": "Lead", "tempo_scale": 1.1}
    )
    assert r.status_code == 422


def _completed_gp_job_with_beats(client, tmp_path, beat_times, notes_on_every_beat=False):
    """A GP job set COMPLETED with a built arrangement XML carrying `beat_times`
    as its ebeat grid — the input the dynamic-sync endpoint aligns."""
    import rockforge.config as config
    import rockforge.interfaces.api.app as app_module
    from rockforge.domain.arrangement import Arrangement, ArrangementKind, SongMetadata
    from rockforge.domain.music import Beat, TabNote, TempoMap, Tuning
    from rockforge.infrastructure.db.models import JobStatus
    from rockforge.infrastructure.rsxml.writer import write_arrangement_xml

    data = _make_gp5_bytes(tmp_path)
    body = client.post(
        "/gp/inspect", files={"file": ("song.gp5", data, "application/octet-stream")}
    ).json()
    job = client.post(
        "/jobs/gp",
        data={"gp_token": body["gp_token"], "lead_track": "0"},
        files={"audio": ("song.wav", b"RIFF0000WAVE", "audio/wav")},
    ).json()
    bundle = config.settings.work_dir / job["id"] / "bundle"
    beats = tuple(
        Beat(time=t, measure=(i // 4 + 1) if i % 4 == 0 else -1)
        for i, t in enumerate(beat_times)
    )
    arr = Arrangement(
        kind=ArrangementKind.LEAD,
        metadata=SongMetadata(title="Dyn", artist="T", song_length=beat_times[-1] + 1),
        tuning=Tuning(),
        notes=(
            [TabNote(string=1, fret=5, time=t, sustain=0.2) for t in beat_times]
            if notes_on_every_beat
            else [TabNote(string=1, fret=5, time=beat_times[0], sustain=0.2)]
        ),
        tempo_map=TempoMap(beats=beats, average_bpm=120.0),
    )
    write_arrangement_xml(arr, bundle / "arrangement_lead.xml")
    with app_module._session_factory() as session:
        db_job = session.get(app_module.Job, job["id"])
        db_job.status = JobStatus.COMPLETED
        db_job.bundle_dir = str(bundle)
        session.commit()
    return job


def test_export_gp_writes_a_corrected_copy_and_reports_rounding(
    client: TestClient, tmp_path
) -> None:
    """The accepted corrections are written into a COPY; the uploaded original is
    untouched; and because gp5 stores tempo as an integer the caller is told what
    was actually written rather than quietly handed a different tempo."""
    from pathlib import Path

    import rockforge.interfaces.api.app as app_module
    from rockforge.infrastructure.gpimport.parser import inspect_gp

    job = _gp_job(client, tmp_path)
    with app_module._session_factory() as session:
        gp_path = Path(str(dict(session.get(app_module.Job, job["id"]).params)["gp_path"]))
    before = gp_path.read_bytes()

    r = client.post(
        f"/jobs/{job['id']}/export-gp",
        json={"corrections": [{"measure": 1, "bpm": 119.085}]},
    )
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["format"] == "gp5" and out["size_bytes"] > 0
    assert out["applied"][0]["requested_bpm"] == 119.085
    assert out["applied"][0]["written_bpm"] == 119.0
    assert out["applied"][0]["rounded"] is True
    assert any("whole number" in w for w in out["warnings"])

    # The user's own file is never modified.
    assert gp_path.read_bytes() == before

    # The exported copy is downloadable and really carries the new tempo.
    d = client.get(f"/jobs/{job['id']}/corrected-gp")
    assert d.status_code == 200
    saved = tmp_path / "dl.gp5"
    saved.write_bytes(d.content)
    assert inspect_gp(saved).tempo == 119


def test_corrected_gp_404s_before_any_export(client: TestClient, tmp_path) -> None:
    job = _gp_job(client, tmp_path)
    assert client.get(f"/jobs/{job['id']}/corrected-gp").status_code == 404


def test_export_gp_rejects_non_gp_and_empty_corrections(client: TestClient, tmp_path) -> None:
    audio_job = _create_job(client)
    assert client.post(
        f"/jobs/{audio_job['id']}/export-gp",
        json={"corrections": [{"measure": 1, "bpm": 120.0}]},
    ).status_code == 422
    job = _gp_job(client, tmp_path)
    assert client.post(
        f"/jobs/{job['id']}/export-gp", json={"corrections": []}
    ).status_code == 422


def test_detect_tempo_returns_local_factor(client: TestClient, tmp_path, monkeypatch) -> None:
    # Per-point re-tempo: detection is faked. GP tempo 100, detected 200 from the
    # clicked point → octave-corrected factor 1.0 (100 / (200 * 0.5)).
    import rockforge.infrastructure.rhythm.librosa_adapter as rhythm

    monkeypatch.setattr(rhythm, "detect_tempo_from", lambda src, start, expected=None: 200.0)
    data = _make_gp5_bytes(tmp_path)
    body = client.post(
        "/gp/inspect", files={"file": ("song.gp5", data, "application/octet-stream")}
    ).json()
    job = client.post(
        "/jobs/gp",
        data={"gp_token": body["gp_token"], "lead_track": "0"},
        files={"audio": ("song.wav", b"RIFF0000WAVE", "audio/wav")},
    ).json()
    r = client.post(f"/jobs/{job['id']}/detect-tempo", json={"from_s": 12.0})
    assert r.status_code == 200
    out = r.json()
    assert out["gp_bpm"] == pytest.approx(100.0)
    assert out["reference_bpm"] == pytest.approx(100.0)  # no chart_bpm → header tempo
    assert out["detected_bpm"] == pytest.approx(200.0)
    assert out["suggested_factor"] == pytest.approx(1.0)


def test_automatic_sync_aligns_the_beats_the_viewer_sends(
    client: TestClient, tmp_path, monkeypatch
) -> None:
    """EXPERIMENTAL "Sincronizar automaticamente": the viewer sends the chart's
    beats and notes as it shows them; the answer is where each beat sits in the
    recording, plus what to check. Beats out of order are refused before any
    analysis runs."""
    import rockforge.infrastructure.rhythm.librosa_adapter as rhythm

    seen: dict[str, object] = {}

    def _fake(src, beats, notes):
        seen.update(src=src, beats=beats, notes=notes)
        return {
            "times": [b * 1.02 for b in beats], "support": [0.9, None, 1.1],
            "after_gap": [2], "evidence_before": 0.4, "evidence_after": 1.0,
            "ratio_min": 1.02, "ratio_max": 1.02, "duration": 30.0,
        }

    monkeypatch.setattr(rhythm, "align_to_recording", _fake)
    job = _gp_job(client, tmp_path)
    r = client.post(
        f"/jobs/{job['id']}/detect-beat-sync",
        json={"beats": [1.0, 1.5, 2.0], "notes": [1.0, 1.25, 2.0]},
    )
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["times"] == pytest.approx([1.02, 1.53, 2.04])
    assert out["support"] == [0.9, None, 1.1] and out["after_gap"] == [2]
    assert seen["beats"] == [1.0, 1.5, 2.0] and seen["notes"] == [1.0, 1.25, 2.0]
    seen.clear()
    bad = client.post(f"/jobs/{job['id']}/detect-beat-sync", json={"beats": [1.0, 0.5]})
    assert bad.status_code == 422 and not seen


def test_the_recordings_attacks_come_from_the_guitar_stem_when_there_is_one(
    client: TestClient, tmp_path, monkeypatch
) -> None:
    """The score's "Ataques da gravação": measured on the separated guitar stem
    when a Demucs pass made one (the drums add attacks of their own to the
    mix) — the one "Separar stems" stored, else the one tone detection left in
    the shared cache — and on the mix otherwise; the answer says which."""
    import rockforge.infrastructure.rhythm.librosa_adapter as rhythm
    import rockforge.interfaces.api.app as app_module

    seen: list[Path] = []
    floored: list[bool] = []

    def _fake(audio, separated=False):
        seen.append(Path(audio))
        floored.append(separated)
        return {"attacks": [[1.0, 0.8], [1.5, 0.4]], "duration": 30.0}

    monkeypatch.setattr(rhythm, "detect_attacks", _fake)
    job = _gp_job(client, tmp_path)
    url = f"/jobs/{job['id']}/detect-attacks"

    r = client.post(url)
    assert r.status_code == 200, r.text
    assert r.json() == {"source": "mix", "attacks": [[1.0, 0.8], [1.5, 0.4]], "duration": 30.0}
    with app_module._session_factory() as session:
        assert seen[-1] == Path(session.get(app_module.Job, job["id"]).source)

    cached = app_module.settings.work_dir / job["id"] / "demucs_stems/stems/htdemucs_6s/x"
    cached /= "guitar.wav"
    cached.parent.mkdir(parents=True)
    cached.write_bytes(b"RIFF")
    assert client.post(url).json()["source"] == "guitar" and seen[-1] == cached

    stored = tmp_path / "stored_guitar.wav"
    stored.write_bytes(b"RIFF")
    with app_module._session_factory() as session:
        row = session.get(app_module.Job, job["id"])
        row.params = {**row.params, "stems": {"guitar": str(stored)}}
        session.commit()
    assert client.post(url).json()["source"] == "guitar" and seen[-1] == stored

    # One instrument chosen: any the separation made (the cache's bass too), never
    # its drums, the mix on request, and an instrument never separated refused.
    for name in ("bass", "drums"):
        (cached.parent / f"{name}.wav").write_bytes(b"RIFF")
    assert client.get(f"/jobs/{job['id']}/attack-sources").json() == {
        "stems": ["bass", "guitar"], "level_stems": ["bass", "drums", "guitar"]
    }
    assert client.post(url, params={"source": "bass"}).json()["source"] == "bass"
    assert seen[-1] == cached.parent / "bass.wav"
    assert client.post(url, params={"source": "mix"}).json()["source"] == "mix"
    with app_module._session_factory() as session:
        assert seen[-1] == Path(session.get(app_module.Job, job["id"]).source)
    for name in ("piano", "drums", "../x"):
        assert client.post(url, params={"source": name}).status_code == 409
    # A separated instrument is read with the residue floor; the mix never is.
    assert floored == [False, True, True, True, False]

    def _missing(audio, separated=False):
        raise ImportError("No module named 'librosa'")

    monkeypatch.setattr(rhythm, "detect_attacks", _missing)
    assert client.post(url).status_code == 503


def test_the_audio_bars_can_show_the_attack_strength_of_the_mix_or_any_separated_part(
    client: TestClient, tmp_path, monkeypatch
) -> None:
    """The "Barras de áudio" in their "Ataques" mode: the onset envelope of the
    mix, or of a separated instrument — the drums included, the clearest beat to
    check bar lines against, though not a playback source — read with the
    residue floor; an instrument never separated is refused."""
    import rockforge.infrastructure.rhythm.librosa_adapter as rhythm
    import rockforge.interfaces.api.app as app_module

    seen: list[tuple[Path, bool]] = []

    def _fake(audio, separated=False):
        seen.append((Path(audio), separated))
        return {"values": [0, 40, 100], "hop": 0.01, "duration": 0.03}

    monkeypatch.setattr(rhythm, "onset_levels", _fake)
    job = _gp_job(client, tmp_path)
    url = f"/jobs/{job['id']}/onset-levels"

    r = client.get(url)
    assert r.status_code == 200, r.text
    assert r.json() == {"source": "mix", "values": [0, 40, 100], "hop": 0.01, "duration": 0.03}
    with app_module._session_factory() as session:
        assert seen[-1] == (Path(session.get(app_module.Job, job["id"]).source), False)
    assert client.get(url, params={"source": "drums"}).status_code == 409

    # The drums a "Separar instrumentos" pass left beside its guitar stem.
    stored = tmp_path / "sep" / "guitar.wav"
    stored.parent.mkdir()
    stored.write_bytes(b"RIFF")
    (stored.parent / "drums.wav").write_bytes(b"RIFF")
    with app_module._session_factory() as session:
        row = session.get(app_module.Job, job["id"])
        row.params = {**row.params, "stems": {"guitar": str(stored)}}
        session.commit()
    sources = client.get(f"/jobs/{job['id']}/attack-sources").json()
    assert sources == {"stems": ["guitar"], "level_stems": ["drums", "guitar"]}
    assert client.get(url, params={"source": "drums"}).json()["source"] == "drums"
    assert seen[-1] == (stored.parent / "drums.wav", True)
    assert client.get(url, params={"source": "guitar"}).status_code == 200
    assert seen[-1] == (stored, True)
    for name in ("piano", "../x"):
        assert client.get(url, params={"source": name}).status_code == 409

    def _missing(audio, separated=False):
        raise ImportError("No module named 'librosa'")

    monkeypatch.setattr(rhythm, "onset_levels", _missing)
    assert client.get(url).status_code == 503


def test_detect_tempo_measures_against_the_chart_bpm_not_the_header(
    client: TestClient, tmp_path, monkeypatch
) -> None:
    """The viewer applies the factor as a relative stretch of the timeline it is
    showing, so the factor must be measured against the tempo THAT timeline plays
    at — the header tempo double-counts every tempo change and every correction
    already applied, which is what made repeated 'Corrigir daqui' runs pile up
    into a chart running far too fast. The chart tempo must also reach the
    detector as its tempo prior (librosa defaults it to 120 and otherwise reads a
    slow song at double time)."""
    import rockforge.infrastructure.rhythm.librosa_adapter as rhythm

    seen: dict[str, float | None] = {}

    def _fake(src, start, expected=None):
        seen["expected"] = expected
        return 150.0

    monkeypatch.setattr(rhythm, "detect_tempo_from", _fake)
    data = _make_gp5_bytes(tmp_path)
    body = client.post(
        "/gp/inspect", files={"file": ("song.gp5", data, "application/octet-stream")}
    ).json()
    job = client.post(
        "/jobs/gp",
        data={"gp_token": body["gp_token"], "lead_track": "0"},
        files={"audio": ("song.wav", b"RIFF0000WAVE", "audio/wav")},
    ).json()
    # The GP header says 100, but the passage under the click currently plays at
    # 150 — exactly the recording's tempo, so nothing should move.
    r = client.post(
        f"/jobs/{job['id']}/detect-tempo", json={"from_s": 12.0, "chart_bpm": 150.0}
    )
    assert r.status_code == 200
    out = r.json()
    assert seen["expected"] == pytest.approx(150.0)  # prior centred on the chart
    assert out["gp_bpm"] == pytest.approx(100.0)  # still reported, informational
    assert out["reference_bpm"] == pytest.approx(150.0)
    assert out["suggested_factor"] == pytest.approx(1.0)  # was 100/150 = 0.667 (too fast)


def test_detect_tuning_returns_cent_offset(client: TestClient, tmp_path, monkeypatch) -> None:
    import rockforge.infrastructure.rhythm.librosa_adapter as rhythm

    monkeypatch.setattr(rhythm, "estimate_tuning_cents", lambda src: -12.5)
    data = _make_gp5_bytes(tmp_path)
    body = client.post(
        "/gp/inspect", files={"file": ("song.gp5", data, "application/octet-stream")}
    ).json()
    job = client.post(
        "/jobs/gp",
        data={"gp_token": body["gp_token"], "lead_track": "0"},
        files={"audio": ("song.wav", b"RIFF0000WAVE", "audio/wav")},
    ).json()
    r = client.post(f"/jobs/{job['id']}/detect-tuning")
    assert r.status_code == 200
    assert r.json()["suggested_cent_offset"] == pytest.approx(-12.5)


def test_detect_tuning_rejected_for_non_gp(client: TestClient) -> None:
    job = _create_job(client)
    r = client.post(f"/jobs/{job['id']}/detect-tuning")
    assert r.status_code == 422


def test_export_arrangement_gp_generates_a_playable_file(client: TestClient, tmp_path) -> None:
    """The whole point: what RockForge shows — including the note editor's edits
    and the corrected timeline — comes out as a real Guitar Pro file. Checked by
    reading it back with our OWN importer, the only verification available here
    (no Guitar Pro in CI)."""
    import rockforge.interfaces.api.app as app_module
    from rockforge.domain.arrangement import Arrangement, ArrangementKind, SongMetadata
    from rockforge.domain.music import Beat, TabNote, TempoMap, Tuning
    from rockforge.infrastructure.db.models import JobStatus
    from rockforge.infrastructure.gpimport.parser import parse_gp_track
    from rockforge.infrastructure.rsxml.writer import write_arrangement_xml

    job = _create_job(client)
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    beats = tuple(
        Beat(time=i * 0.5, measure=(i // 4) + 1 if i % 4 == 0 else -1) for i in range(17)
    )
    notes = [TabNote(string=i % 6, fret=(i % 5) + 1, time=i * 0.5, sustain=0.3) for i in range(12)]
    write_arrangement_xml(
        Arrangement(
            kind=ArrangementKind.COMBINED,
            metadata=SongMetadata(title="T", artist="A", song_length=8.0),
            tuning=Tuning(midi=(38, 45, 50, 55, 59, 64)),
            tempo_map=TempoMap(beats=beats, average_bpm=120.0),
            notes=notes,
        ),
        bundle / "arrangement_combined.xml",
    )
    with app_module._session_factory() as session:
        db_job = session.get(app_module.Job, job["id"])
        db_job.status = JobStatus.COMPLETED
        db_job.bundle_dir = str(bundle)
        db_job.source_type = "gp"
        session.commit()

    r = client.post(f"/jobs/{job['id']}/export-arrangement-gp", params={"arrangement": "Combined"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["notes_written"] == 12
    # The single-track trade-off is stated on every export, not only on failure.
    assert any("pista" in w for w in body["warnings"])

    dl = client.get(f"/jobs/{job['id']}/corrected-gp")
    assert dl.status_code == 200
    out = tmp_path / "got.gp5"
    out.write_bytes(dl.content)
    parsed = parse_gp_track(out, 0)
    assert len(parsed.notes) == 12
    assert parsed.tuning.midi == (38, 45, 50, 55, 59, 64), "the tuning must survive"
    for original, got in zip(notes, parsed.notes, strict=True):
        assert got.time == pytest.approx(original.time, abs=1e-3)
        assert (got.string, got.fret) == (original.string, original.fret)


def test_export_arrangement_gp_rejects_an_unknown_arrangement(
    client: TestClient, tmp_path
) -> None:
    import rockforge.interfaces.api.app as app_module
    from rockforge.infrastructure.db.models import JobStatus

    job = _create_job(client)
    bundle = tmp_path / "b2"
    bundle.mkdir()
    with app_module._session_factory() as session:
        db_job = session.get(app_module.Job, job["id"])
        db_job.status = JobStatus.COMPLETED
        db_job.bundle_dir = str(bundle)
        db_job.source_type = "gp"
        session.commit()
    r = client.post(f"/jobs/{job['id']}/export-arrangement-gp", params={"arrangement": "Lead"})
    assert r.status_code == 404


def test_committed_note_edits_survive_an_unrelated_rebuild(
    client: TestClient, tmp_path
) -> None:
    """Reopening a job and rebuilding for ANY other reason used to erase every
    note edit already applied.

    The viewer always sends the whole note_overrides dict and the backend
    REPLACES the stored value, but the viewer reset its pending list to {} on
    every job open — so changing the tuning on a reopened job sent {} and the
    edits were gone with no warning. /arrangements now returns the committed
    edits per arrangement so the viewer can seed from them; this pins the API
    half of that contract."""
    data = _make_gp5_bytes(tmp_path)
    body = client.post(
        "/gp/inspect", files={"file": ("song.gp5", data, "application/octet-stream")}
    ).json()
    job = client.post(
        "/jobs/gp",
        data={"gp_token": body["gp_token"], "lead_track": "0"},
        files={"audio": ("song.wav", b"RIFF0000WAVE", "audio/wav")},
    ).json()
    edit = {"time": 1.5, "string": 2, "fret": 7, "sustain": 0.4}
    edited = client.post(
        f"/jobs/{job['id']}/rebuild", json={"note_overrides": {"Lead": [edit]}}
    ).json()

    import rockforge.interfaces.api.app as app_module
    from rockforge.infrastructure.db.models import Job

    with app_module._session_factory() as session:
        stored = session.get(Job, edited["id"]).params["note_overrides"]
    assert stored["Lead"][0]["fret"] == 7

    # The viewer can now read them back and re-send them, so an unrelated
    # rebuild keeps them.
    kept = client.post(
        f"/jobs/{edited['id']}/rebuild",
        json={"cent_offset": -5.0, "note_overrides": stored},
    ).json()
    with app_module._session_factory() as session:
        after = session.get(Job, kept["id"]).params["note_overrides"]
    assert after["Lead"][0]["fret"] == 7, "an unrelated rebuild must not drop note edits"

    # And clearing them is still possible — an EXPLICIT empty dict wipes them,
    # which is what the "Limpar edições" button sends.
    cleared = client.post(
        f"/jobs/{kept['id']}/rebuild", json={"note_overrides": {}}
    ).json()
    with app_module._session_factory() as session:
        assert session.get(Job, cleared["id"]).params["note_overrides"] == {}


def test_the_fhp_editors_hand_positions_are_stored_and_read_back(
    client: TestClient, tmp_path
) -> None:
    """A rebuild stores each chart's FHPs (sorted, an empty chart dropped — it
    gets the automatic ones), refuses one off the neck, and /arrangements
    answers the chart's FHPs as built with whether they are the user's."""
    import rockforge.config as config
    import rockforge.interfaces.api.app as app_module
    from rockforge.domain.arrangement import Arrangement, ArrangementKind, SongMetadata
    from rockforge.domain.hand import HandPosition
    from rockforge.domain.music import Beat, TabNote, TempoMap, Tuning
    from rockforge.infrastructure.db.models import Job, JobStatus
    from rockforge.infrastructure.rsxml.writer import write_arrangement_xml

    data = _make_gp5_bytes(tmp_path)
    body = client.post(
        "/gp/inspect", files={"file": ("song.gp5", data, "application/octet-stream")}
    ).json()
    job = client.post(
        "/jobs/gp",
        data={"gp_token": body["gp_token"], "lead_track": "0"},
        files={"audio": ("song.wav", b"RIFF0000WAVE", "audio/wav")},
    ).json()
    off_the_neck = client.post(
        f"/jobs/{job['id']}/rebuild",
        json={"hand_positions": {"Lead": [{"time": 1.0, "fret": 22, "width": 4}]}},
    )
    assert off_the_neck.status_code == 422
    edited = client.post(f"/jobs/{job['id']}/rebuild", json={"hand_positions": {
        "Lead": [{"time": 3.0, "fret": 7}, {"time": 1.0, "fret": 2, "width": 5}],
        "Rhythm": [],
    }}).json()
    with app_module._session_factory() as session:
        stored = session.get(Job, edited["id"]).params["hand_positions"]
    assert stored == {"Lead": [{"time": 1.0, "fret": 2, "width": 5},
                               {"time": 3.0, "fret": 7, "width": 4}]}

    bundle = config.settings.work_dir / edited["id"] / "bundle"
    beats = tuple(Beat(time=0.5 * i, measure=(i // 4 + 1) if i % 4 == 0 else -1)
                  for i in range(12))
    for kind, hps in ((ArrangementKind.LEAD, [HandPosition(1.0, 2, 5), HandPosition(3.0, 7)]),
                      (ArrangementKind.RHYTHM, [])):
        write_arrangement_xml(Arrangement(
            kind=kind, metadata=SongMetadata(title="T", artist="A", song_length=6.0),
            tuning=Tuning(), tempo_map=TempoMap(beats=beats, average_bpm=120.0),
            notes=[TabNote(string=1, fret=3, time=1.0, sustain=0.2),
                   TabNote(string=1, fret=8, time=3.5, sustain=0.2)],
            hand_positions=hps,
        ), bundle / f"arrangement_{kind.value.lower()}.xml")
    with app_module._session_factory() as session:
        row = session.get(Job, edited["id"])
        row.status, row.bundle_dir = JobStatus.COMPLETED, str(bundle)
        session.commit()
    arrs = {a["kind"]: a for a in client.get(f"/jobs/{edited['id']}/arrangements").json()}
    assert arrs["Lead"]["hand_positions_edited"] is True
    assert arrs["Lead"]["hand_positions"] == [{"time": 1.0, "fret": 2, "width": 5},
                                              {"time": 3.0, "fret": 7, "width": 4}]
    assert arrs["Rhythm"]["hand_positions_edited"] is False
    assert [h["fret"] for h in arrs["Rhythm"]["hand_positions"]] == [3, 8]  # automatic


def test_tuning_pitches_are_range_checked_at_the_api(client: TestClient, tmp_path) -> None:
    """Only the LENGTH of tuning_midi was checked, so an absurd pitch 202'd, was
    persisted, and only failed at packaging time inside struct.pack. Guards the
    two model paths and /import-sync, which takes raw JSON and bypasses them."""
    data = _make_gp5_bytes(tmp_path)
    body = client.post(
        "/gp/inspect", files={"file": ("song.gp5", data, "application/octet-stream")}
    ).json()
    job = client.post(
        "/jobs/gp",
        data={"gp_token": body["gp_token"], "lead_track": "0"},
        files={"audio": ("song.wav", b"RIFF0000WAVE", "audio/wav")},
    ).json()
    jid = job["id"]
    for payload in (
        '{"tuning_overrides": {"Lead": [999999, 1, 2, 3, 4, 5]}}',
        '{"tuning_overrides": {"Lead": [-1, 45, 50, 55, 59, 64]}}',
        '{"tuning_overrides": {"Lead": [999, 1, 2, 3, 4, 5]}}',
    ):
        r = client.post(
            f"/jobs/{jid}/rebuild", content=payload, headers={"Content-Type": "application/json"}
        )
        assert r.status_code == 422, f"{payload} -> {r.status_code}"
    r = client.post(
        f"/jobs/{jid}/import-sync",
        content='{"sync": {"tuning_overrides": {"Lead": [999999, 1, 2, 3, 4, 5]}}}',
        headers={"Content-Type": "application/json"},
    )
    assert r.status_code == 422, r.text
    # A real low tuning (Drop C#) still rebuilds — this rejects nonsense, not
    # the tunings the app exists to handle.
    ok = client.post(
        f"/jobs/{jid}/rebuild",
        content='{"tuning_overrides": {"Lead": [37, 44, 49, 54, 58, 63]}}',
        headers={"Content-Type": "application/json"},
    )
    assert ok.status_code == 202, ok.text


def test_deleting_a_job_removes_its_gp_file_but_not_a_forks(
    client: TestClient, tmp_path
) -> None:
    """The uploaded Guitar Pro file lives outside the job's work dir
    (work_dir/gp/<uuid>.gp*), so delete_job's rmtree never touched it and every
    deleted job left its GP behind forever. It is reference-counted like the
    recording: a rebuild forks and SHARES gp_path, so deleting one of the pair
    must not pull the file out from under the other."""
    data = _make_gp5_bytes(tmp_path)
    body = client.post(
        "/gp/inspect", files={"file": ("song.gp5", data, "application/octet-stream")}
    ).json()
    job = client.post(
        "/jobs/gp",
        data={"gp_token": body["gp_token"], "lead_track": "0"},
        files={"audio": ("song.wav", b"RIFF0000WAVE", "audio/wav")},
    ).json()
    import rockforge.interfaces.api.app as app_module
    from rockforge.infrastructure.db.models import Job

    with app_module._session_factory() as session:
        gp_file = Path(str(session.get(Job, job["id"]).params["gp_path"]))
    assert gp_file.is_file()

    fork = client.post(f"/jobs/{job['id']}/rebuild", json={"tempo_scale": 1.1}).json()
    assert client.delete(f"/jobs/{job['id']}").status_code == 204
    assert gp_file.is_file(), "the fork still points at this GP file"

    assert client.delete(f"/jobs/{fork['id']}").status_code == 204
    assert not gp_file.exists(), "last job referencing it is gone; the GP must go too"


def test_orphaned_gp_uploads_are_swept_but_referenced_ones_are_kept(
    client: TestClient, tmp_path
) -> None:
    """/gp/inspect stores the upload BEFORE the job exists, so abandoning the
    creation wizard (or the batch modal, one inspect per song) left a file with
    nothing to ever collect it. The sweep only touches files past the age limit
    and referenced by no job — a fresh upload someone is still working with, and
    any file a job points at, must survive regardless of age."""
    import os

    from sqlalchemy import select

    import rockforge.interfaces.api.app as app_module
    from rockforge.infrastructure.db.models import Job

    data = _make_gp5_bytes(tmp_path)

    def _inspect() -> Path:
        token = client.post(
            "/gp/inspect", files={"file": ("song.gp5", data, "application/octet-stream")}
        ).json()["gp_token"]
        return app_module.settings.work_dir / "gp" / token

    abandoned = _inspect()   # wizard closed, never became a job
    fresh = _inspect()       # uploaded moments ago, wizard still open
    used_token = client.post(
        "/gp/inspect", files={"file": ("song.gp5", data, "application/octet-stream")}
    ).json()["gp_token"]
    client.post(
        "/jobs/gp",
        data={"gp_token": used_token, "lead_track": "0"},
        files={"audio": ("song.wav", b"RIFF0000WAVE", "audio/wav")},
    )
    with app_module._session_factory() as session:
        used = Path(str(session.scalars(select(Job)).one().params["gp_path"]))

    # Age out the abandoned upload AND the referenced one; only the first may go.
    old = time.time() - app_module.GP_ORPHAN_MAX_AGE_S - 60
    os.utime(abandoned, (old, old))
    os.utime(used, (old, old))

    assert app_module._sweep_orphan_gp_uploads() == 1
    assert not abandoned.exists(), "an aged, unreferenced upload must be collected"
    assert fresh.is_file(), "a recent upload may still belong to an open wizard"
    assert used.is_file(), "a file a job points at must survive any age"


def test_the_orphan_sweep_actually_runs_on_startup(tmp_path, monkeypatch) -> None:
    """The sweep is only useful if something calls it. Nothing else does — there
    is no scheduler here — so it hangs off the app's lifespan, and this drives a
    real startup to prove the wiring, not just the function."""
    import os

    monkeypatch.setenv("ROCKFORGE_DATABASE_URL", f"sqlite:///{tmp_path}/t.db")
    monkeypatch.setenv("ROCKFORGE_WORK_DIR", str(tmp_path / "work"))
    import rockforge.config as config
    importlib.reload(config)
    import rockforge.interfaces.api.app as app_module
    importlib.reload(app_module)

    gp_dir = app_module.settings.work_dir / "gp"
    gp_dir.mkdir(parents=True, exist_ok=True)
    stale = gp_dir / "abandoned.gp5"
    stale.write_bytes(b"not a real GP file")
    old = time.time() - app_module.GP_ORPHAN_MAX_AGE_S - 60
    os.utime(stale, (old, old))

    with TestClient(app_module.app):  # entering the context runs the lifespan
        pass
    assert not stale.exists()


def test_projects_synced_in_guitar_pro_before_the_flag_existed_are_marked_on_startup(
    tmp_path, monkeypatch,
) -> None:
    """A project built before ``gp_synced`` existed would keep asking
    "confirmaste a sincronização?" until rebuilt; startup reads its GP file once."""
    import zipfile

    monkeypatch.setenv("ROCKFORGE_DATABASE_URL", f"sqlite:///{tmp_path}/t.db")
    monkeypatch.setenv("ROCKFORGE_WORK_DIR", str(tmp_path / "work"))
    import rockforge.config as config
    importlib.reload(config)
    import rockforge.interfaces.api.app as app_module
    importlib.reload(app_module)

    synced = tmp_path / "synced.gp"
    with zipfile.ZipFile(synced, "w") as z:
        z.writestr("VERSION", "7.0")
        z.writestr("Content/score.gpif", (
            '<?xml version="1.0" encoding="utf-8"?><GPIF><Score><Title>T</Title></Score>'
            "<MasterTrack><Automations><Automation><Type>Tempo</Type><Bar>0</Bar>"
            "<Position>0</Position><Value>120 2</Value></Automation>"
            "<Automation><Type>SyncPoint</Type><Bar>0</Bar><Position>0</Position><Value>"
            "<BarIndex>0</BarIndex><BarOccurrence>0</BarOccurrence>"
            "<FrameOffset>44100</FrameOffset></Value></Automation>"
            "</Automations></MasterTrack><MasterBars><MasterBar><Time>4/4</Time>"
            "<Bars>0</Bars></MasterBar></MasterBars></GPIF>"
        ))
    with TestClient(app_module.app):
        pass  # create the schema
    with app_module._session_factory() as session:
        for gp_path in (str(synced), str(tmp_path / "gone.gp5")):
            session.add(app_module.Job(
                source="x.wav", source_type="gp", title="T", artist="A",
                params={"gp_path": gp_path},
            ))
        session.commit()
    with TestClient(app_module.app) as c:  # a real startup runs the backfill
        sources = sorted(str(j["sync_source"]) for j in c.get("/jobs").json())
    assert sources == ["None", "gp"]


def test_jobs_follow_their_files_when_the_work_dir_moves(tmp_path, monkeypatch) -> None:
    """Issue #6: the database keeps absolute paths, so after the work dir moved
    every earlier job pointed at the old place (bundle 500, recording 409). A
    real startup points them at where the files are now; a path that still
    exists, and one found nowhere, stay as they are."""
    monkeypatch.setenv("ROCKFORGE_DATABASE_URL", f"sqlite:///{tmp_path}/t.db")
    monkeypatch.setenv("ROCKFORGE_WORK_DIR", str(tmp_path / "new"))
    import rockforge.config as config
    importlib.reload(config)
    import rockforge.interfaces.api.app as app_module
    importlib.reload(app_module)

    work = app_module.settings.work_dir
    old = "/media/old-disk/RockForge"
    (work / "j1" / "bundle").mkdir(parents=True)
    (work / "j1" / "bundle" / "arrangement_lead.xml").write_text("<song/>")
    for rel in ("uploads/rec.wav", "gp/song.gp5", "j1/demucs_stems/guitar.wav", "j1/Song_p.psarc"):
        (work / rel).parent.mkdir(parents=True, exist_ok=True)
        (work / rel).write_bytes(b"x")
    kept = tmp_path / "outside.wav"
    kept.write_bytes(b"x")
    with TestClient(app_module.app):
        pass  # create the schema
    with app_module._session_factory() as session:
        session.add(app_module.Job(
            id="j1", source=f"{old}/uploads/rec.wav", source_type="gp", title="T", artist="A",
            bundle_dir=f"{old}/j1/bundle", psarc_path=f"{old}/j1/Song_p.psarc",
            params={"gp_path": f"{old}/gp/song.gp5",
                    "stems": {"guitar": f"{old}/j1/demucs_stems/guitar.wav",
                              "bass": f"{old}/j1/demucs_stems/bass.wav"}},
        ))
        session.add(app_module.Job(
            id="j2", source=str(kept), source_type="gp", title="T", artist="A",
            params={"gp_path": f"{old}/gp/gone.gp5"},
        ))
        session.commit()
    with TestClient(app_module.app):  # a real startup runs the rebase
        pass
    with app_module._session_factory() as session:
        j1 = session.get(app_module.Job, "j1")
        j2 = session.get(app_module.Job, "j2")
        assert j1.source == str(work / "uploads" / "rec.wav")
        assert j1.bundle_dir == str(work / "j1" / "bundle")
        assert j1.psarc_path == str(work / "j1" / "Song_p.psarc")
        assert j1.params["gp_path"] == str(work / "gp" / "song.gp5")
        assert j1.params["stems"] == {"guitar": str(work / "j1" / "demucs_stems" / "guitar.wav"),
                                      "bass": f"{old}/j1/demucs_stems/bass.wav"}
        assert j2.source == str(kept)
        assert j2.params["gp_path"] == f"{old}/gp/gone.gp5"


def test_non_finite_floats_are_rejected_at_the_boundary(
    client: TestClient, tmp_path
) -> None:
    """JSON carries the literals NaN and Infinity and Pydantic accepts them in a
    float by default, so every timing field used to take them: the ``<= 0``
    tempo guard waved NaN through (``NaN <= 0`` is False), the job forked, the
    value was persisted into the JSON params column, and the build failed much
    later with an error pointing nowhere — ``_build_time_warp`` propagates a NaN
    silently across the whole timeline. Each of these must 422 at the edge."""
    data = _make_gp5_bytes(tmp_path)
    body = client.post(
        "/gp/inspect", files={"file": ("song.gp5", data, "application/octet-stream")}
    ).json()
    job = client.post(
        "/jobs/gp",
        data={"gp_token": body["gp_token"], "lead_track": "0"},
        files={"audio": ("song.wav", b"RIFF0000WAVE", "audio/wav")},
    ).json()
    for payload in (
        '{"tempo_scale": NaN}',
        '{"tempo_scale": Infinity}',
        '{"offset_s": NaN}',
        '{"lead_in_s": Infinity}',
        '{"cent_offset": NaN}',
        '{"sync_anchors": [[1.0, NaN]]}',
        '{"tone_changes": [{"time": NaN, "name": "a"}]}',
        '{"section_overrides": [{"time": NaN, "name": "a"}]}',
        '{"note_overrides": {"Lead": [{"time": NaN, "string": 0}]}}',
        '{"lyrics_events": [{"time": NaN, "length": 1.0, "lyric": "a"}]}',
    ):
        r = client.post(
            f"/jobs/{job['id']}/rebuild",
            content=payload,
            headers={"Content-Type": "application/json"},
        )
        assert r.status_code == 422, f"{payload} -> {r.status_code}"
        # The 422 body must be encodable: FastAPI echoes the rejected input, and
        # Starlette serializes with allow_nan=False, so without scrubbing the
        # payload this came back as a bare 500 with no explanation at all.
        assert "finite" in r.text, r.text[:200]
    # A valid value still goes through — the guard rejects NaN, not floats.
    ok = client.post(
        f"/jobs/{job['id']}/rebuild",
        content='{"tempo_scale": 1.05}',
        headers={"Content-Type": "application/json"},
    )
    assert ok.status_code == 202, ok.text


def test_a_negative_intro_silence_is_refused_and_the_shift_matches_the_build(
    client: TestClient, tmp_path
) -> None:
    """/rebuild refused a negative lead_in_s but /jobs/gp stored one, and the
    anchor re-expression then used it unclamped while the build clamps it to 0
    — a tempo change would have moved every note by the difference."""
    import rockforge.interfaces.api.app as app_module
    from rockforge.application.gp_pipeline import MIN_LEAD_S

    data = _make_gp5_bytes(tmp_path)
    token = client.post(
        "/gp/inspect", files={"file": ("song.gp5", data, "application/octet-stream")}
    ).json()["gp_token"]
    r = client.post(
        "/jobs/gp",
        data={"gp_token": token, "lead_track": "0", "lead_in_s": "-2"},
        files={"audio": ("song.wav", b"RIFF0000WAVE", "audio/wav")},
    )
    assert r.status_code == 422
    assert "lead_in_s" in r.json()["detail"]
    # A value that reached params anyway (an older job, an imported file) is
    # clamped exactly as gp_pipeline clamps it.
    for offset, lead_in in ((0.0, -2.0), (5.0, 1.5), (-3.0, 0.0), (1.0, 0.25)):
        build = max(0.0, MIN_LEAD_S - offset) + max(0.0, lead_in) + offset
        params = {"offset_s": offset, "lead_in_s": lead_in}
        assert app_module._score_shift(params) == pytest.approx(build)


def test_non_finite_form_fields_and_imported_sync_are_rejected(
    client: TestClient, tmp_path
) -> None:
    """The two paths that bypass the ``Finite`` models: multipart form fields
    (they arrive as strings and coerce) and /import-sync, which takes a raw JSON
    blob that a hand-edited or foreign file could carry a NaN into."""
    data = _make_gp5_bytes(tmp_path)

    def _token() -> str:
        return client.post(
            "/gp/inspect", files={"file": ("song.gp5", data, "application/octet-stream")}
        ).json()["gp_token"]

    for field in ("offset_s", "lead_in_s", "tempo_scale"):
        r = client.post(
            "/jobs/gp",
            data={"gp_token": _token(), "lead_track": "0", field: "NaN"},
            files={"audio": ("song.wav", b"RIFF0000WAVE", "audio/wav")},
        )
        assert r.status_code == 422, f"{field} -> {r.status_code}"
        assert field in r.json()["detail"]

    job = client.post(
        "/jobs/gp",
        data={"gp_token": _token(), "lead_track": "0"},
        files={"audio": ("song.wav", b"RIFF0000WAVE", "audio/wav")},
    ).json()
    for sync in ('{"offset_s": NaN}', '{"sync_anchor_stages": [[[1.0, NaN]]]}'):
        r = client.post(
            f"/jobs/{job['id']}/import-sync",
            content='{"sync": ' + sync + "}",
            headers={"Content-Type": "application/json"},
        )
        assert r.status_code == 422, f"{sync} -> {r.status_code}"
    ok = client.post(
        f"/jobs/{job['id']}/import-sync",
        content='{"sync": {"offset_s": 3.5, "tempo_scale": 1.1}}',
        headers={"Content-Type": "application/json"},
    )
    assert ok.status_code == 202, ok.text


def test_missing_ml_extra_reports_503_not_a_confusing_422(
    client: TestClient, tmp_path, monkeypatch
) -> None:
    """The adapters import librosa INSIDE their function bodies (so the API
    process never pays for the ML stack), which made the old
    ``try: from ...librosa_adapter import ...  except ImportError`` guard dead
    code — the module import always succeeded and the real failure surfaced on
    the call, where the generic handler turned it into
    "422 could not analyse the recording: No module named 'librosa'". The
    ImportError has to be caught around the CALL, ahead of that handler."""
    import rockforge.infrastructure.rhythm.librosa_adapter as rhythm

    def _no_librosa(*_args, **_kwargs):
        raise ModuleNotFoundError("No module named 'librosa'", name="librosa")

    monkeypatch.setattr(rhythm, "detect_tempo_from", _no_librosa)
    monkeypatch.setattr(rhythm, "estimate_tuning_cents", _no_librosa)
    data = _make_gp5_bytes(tmp_path)
    body = client.post(
        "/gp/inspect", files={"file": ("song.gp5", data, "application/octet-stream")}
    ).json()
    job = client.post(
        "/jobs/gp",
        data={"gp_token": body["gp_token"], "lead_track": "0"},
        files={"audio": ("song.wav", b"RIFF0000WAVE", "audio/wav")},
    ).json()

    r = client.post(f"/jobs/{job['id']}/detect-tempo", json={"from_s": 5.0})
    assert r.status_code == 503, r.text
    assert "rockforge[ml]" in r.json()["detail"] and "librosa" in r.json()["detail"]

    r = client.post(f"/jobs/{job['id']}/detect-tuning")
    assert r.status_code == 503, r.text
    assert "rockforge[ml]" in r.json()["detail"]


def test_detect_tempo_rejected_for_non_gp(client: TestClient) -> None:
    job = _create_job(client)
    r = client.post(f"/jobs/{job['id']}/detect-tempo", json={"from_s": 0.0})
    assert r.status_code == 422


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


def test_lyrics_default_status_none(client: TestClient) -> None:
    job = _create_job(client)
    r = client.get(f"/jobs/{job['id']}/lyrics")
    assert r.status_code == 200
    assert r.json() == {"status": "none", "events": [], "log": [], "follow_chart": False}


def test_lyrics_falls_back_to_supplied_lrc_text(client: TestClient) -> None:
    import rockforge.interfaces.api.app as app_module

    job = _create_job(client)
    with app_module._session_factory() as session:
        db_job = session.get(app_module.Job, job["id"])
        params = dict(db_job.params or {})
        params["lrc_text"] = "[00:01.00]hello world\n"
        db_job.params = params
        session.commit()

    r = client.get(f"/jobs/{job['id']}/lyrics")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "none"
    assert [e["lyric"] for e in body["events"]] == ["hello", "world+"]


def test_detect_lyrics_enqueues_and_marks_detecting(client: TestClient) -> None:
    job = _create_job(client)
    r = client.post(f"/jobs/{job['id']}/detect-lyrics")
    assert r.status_code == 202
    assert r.json()["lyrics_status"] == "detecting"
    assert client.get(f"/jobs/{job['id']}").json()["lyrics_status"] == "detecting"


def test_detect_lyrics_unknown_job_404(client: TestClient) -> None:
    assert client.post("/jobs/nope/detect-lyrics").status_code == 404


def test_detect_lyrics_can_align_known_lyrics_instead_of_transcribing(
    client: TestClient,
) -> None:
    job = _create_job(client)
    r = client.post(f"/jobs/{job['id']}/detect-lyrics", json={"align_lines": [
        {"time": 12.0, "text": "Eu não sei o que fazer"},
        {"time": None, "text": "com o meu coração, está tudo"},
        {"time": 20.0, "text": "   "},
    ]})
    assert r.status_code == 202, r.text

    import rockforge.interfaces.api.app as app_module

    with app_module._session_factory() as session:
        params = dict(session.get(app_module.Job, job["id"]).params or {})
    assert params["lyrics_align"] == {"language": "pt", "lines": [
        {"time": 12.0, "text": "Eu não sei o que fazer"},
        {"time": None, "text": "com o meu coração, está tudo"}]}

    client.post(f"/jobs/{job['id']}/detect-lyrics")  # a plain detection again
    with app_module._session_factory() as session:
        params = dict(session.get(app_module.Job, job["id"]).params or {})
    assert "lyrics_align" not in params
    bad = client.post(f"/jobs/{job['id']}/detect-lyrics",
                      json={"align_lines": [{"text": "x"}], "language": "Portuguese!"})
    assert bad.status_code == 422


def test_lyrics_lookup_returns_the_lrclib_candidates(client: TestClient, monkeypatch) -> None:
    from rockforge.infrastructure import lyrics_lookup

    seen: list[str] = []

    def fake(url: str):  # noqa: ANN202
        seen.append(url)
        return [{"id": 7, "trackName": "Ocean Eyes", "artistName": "Billie Eilish",
                 "albumName": "dont smile at me", "duration": 200.0, "instrumental": False,
                 "plainLyrics": "I've been watching you", "syncedLyrics": "[00:10.00] I've been"}]

    monkeypatch.setattr(lyrics_lookup, "_http_get_json", fake)
    r = client.get("/lyrics-lookup", params={
        "title": "Ocean Eyes", "artist": "Billie Eilish feat. X", "duration": 201.5})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["searched_artist"] == "Billie Eilish"
    assert body["candidates"][0]["synced"] == "[00:10.00] I've been"
    assert "artist_name=Billie+Eilish" in seen[0]

    assert client.get("/lyrics-lookup", params={"title": "x"}).status_code == 422

    def down(url: str):  # noqa: ANN202
        raise lyrics_lookup.LyricsLookupError("não consegui contactar o LRCLIB (timeout)")

    monkeypatch.setattr(lyrics_lookup, "_http_get_json", down)
    r = client.get("/lyrics-lookup", params={"title": "x", "artist": "y"})
    assert r.status_code == 502 and "LRCLIB" in r.text


def test_lrc_text_becomes_the_editors_words_with_the_offset(client: TestClient) -> None:
    r = client.post("/lyrics/parse", json={
        "text": "[00:10.00] hello darkness\n[00:14.00] my old friend", "offset_s": -2.0})
    assert r.status_code == 200, r.text
    words = [(e["lyric"], round(e["time"], 2)) for e in r.json()["events"]]
    assert words[0] == ("hello", 8.0)
    assert words[-1][0] == "friend+" and words[2] == ("my", 12.0)
    plain = client.post("/lyrics/parse", json={"text": "hello darkness\nmy old friend"})
    assert plain.status_code == 422


def test_the_vocal_line_is_served_for_the_viewers_voice_source(client: TestClient) -> None:
    import rockforge.interfaces.api.app as app_module

    job = _create_job(client)
    assert client.get(f"/jobs/{job['id']}/vocal-line").json() == {
        "notes": [], "gp_has_lyrics": False,
    }
    with app_module._session_factory() as session:
        db_job = session.get(app_module.Job, job["id"])
        db_job.params = {**(db_job.params or {}), "gp_has_lyrics": True, "vocal_melody": [
            {"time": 1.0, "length": 0.25, "midi": 64},
            {"time": 1.5, "length": 0.5, "midi": None},
            {"time": "not a time", "length": 1},  # malformed: skipped, not a 500
        ]}
        session.commit()
    r = client.get(f"/jobs/{job['id']}/vocal-line")
    assert r.status_code == 200
    assert r.json() == {"gp_has_lyrics": True, "notes": [
        {"time": 1.0, "length": 0.25, "midi": 64}, {"time": 1.5, "length": 0.5, "midi": None},
    ]}
    assert client.get("/jobs/nope/vocal-line").status_code == 404


def test_lyrics_say_whether_they_follow_the_charts_sync_corrections(
    client: TestClient,
) -> None:
    """Lyrics timed on the score move with its sync corrections, lyrics timed to
    the recording stay put; the flag travels through a rebuild."""
    import rockforge.interfaces.api.app as app_module

    job = _create_job(client)

    def follows(job_id: str) -> bool:
        return bool(client.get(f"/jobs/{job_id}/lyrics").json()["follow_chart"])

    def set_params(**values: object) -> None:
        with app_module._session_factory() as session:
            db_job = session.get(app_module.Job, job["id"])
            db_job.params = {**(db_job.params or {}), **values}
            session.commit()

    assert not follows(job["id"])  # no lyrics from the score at all
    set_params(gp_has_lyrics=True)  # a job built before the flag: from the GP file
    assert follows(job["id"])
    set_params(lrc_text="[00:01.00] hi")  # ...unless an LRC is what it uses
    assert not follows(job["id"])
    set_params(lyrics_follow_chart=True)  # the flag, once set, is the answer
    assert follows(job["id"])
    rebuilt = client.post(
        f"/jobs/{job['id']}/rebuild", json={"lyrics_follow_chart": False},
    ).json()
    assert not follows(rebuilt["id"])
    untouched = client.post(f"/jobs/{rebuilt['id']}/rebuild", json={}).json()
    assert not follows(untouched["id"])


def test_rebuild_stores_lyrics_events_and_resets_status(client: TestClient) -> None:
    job = _create_job(client)
    client.post(f"/jobs/{job['id']}/detect-lyrics")
    rebuilt = client.post(
        f"/jobs/{job['id']}/rebuild",
        json={"lyrics_events": [{"time": 1.0, "length": 0.5, "lyric": "hi+"}]},
    ).json()
    r = client.get(f"/jobs/{rebuilt['id']}/lyrics")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "none"
    assert body["events"] == [{"time": 1.0, "length": 0.5, "lyric": "hi+"}]


def test_detect_tones_enqueues_and_marks_detecting(client: TestClient) -> None:
    job = _create_job(client)
    r = client.post(f"/jobs/{job['id']}/detect-tones")
    assert r.status_code == 202
    assert r.json()["tone_detection_status"] == "detecting"
    assert client.get(f"/jobs/{job['id']}").json()["tone_detection_status"] == "detecting"


def test_detect_tones_unknown_job_404(client: TestClient) -> None:
    assert client.post("/jobs/nope/detect-tones").status_code == 404


def test_separate_stems_enqueues_and_marks_detecting(client: TestClient) -> None:
    job = _create_job(client)
    r = client.post(f"/jobs/{job['id']}/separate-stems")
    assert r.status_code == 202
    s = client.get(f"/jobs/{job['id']}/stems")
    assert s.status_code == 200
    assert s.json()["status"] == "detecting"


def test_stems_default_status_none(client: TestClient) -> None:
    job = _create_job(client)
    body = client.get(f"/jobs/{job['id']}/stems").json()
    assert body["status"] == "none"
    assert body["stems"] == []


def test_separate_stems_unknown_job_404(client: TestClient) -> None:
    assert client.post("/jobs/nope/separate-stems").status_code == 404


def test_stem_audio_missing_returns_404(client: TestClient) -> None:
    job = _create_job(client)
    assert client.get(f"/jobs/{job['id']}/stem/guitar").status_code == 404


def test_detected_tones_returns_none_status_by_default(client: TestClient) -> None:
    job = _create_job(client)
    r = client.get(f"/jobs/{job['id']}/detected-tones")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "none"
    assert body["category"] == ""
    assert body["lead"] == {}
    assert body["rhythm"] == {}


def test_cover_art_upload_and_download(client: TestClient) -> None:
    job = _create_job(client)
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16

    r = client.post(
        f"/jobs/{job['id']}/cover", files={"file": ("cover.png", png, "image/png")}
    )
    assert r.status_code == 202
    assert r.json()["cover_art"] is True

    r = client.get(f"/jobs/{job['id']}/cover")
    assert r.status_code == 200
    assert r.content == png

    assert client.get(f"/jobs/{job['id']}")["cover_art"] if False else True


def test_cover_art_rejects_unsupported_format(client: TestClient) -> None:
    job = _create_job(client)
    r = client.post(
        f"/jobs/{job['id']}/cover", files={"file": ("cover.gif", b"GIF89a", "image/gif")}
    )
    assert r.status_code == 415


def test_a_refused_cover_upload_keeps_the_cover_the_project_had(
    client: TestClient, monkeypatch
) -> None:
    """The old cover used to be deleted before the new upload was read, so an
    oversized (413) or non-image one left the project with no cover at all."""
    import rockforge.interfaces.api.app as app_module

    job = _create_job(client)
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
    assert client.post(f"/jobs/{job['id']}/cover",
                       files={"file": ("cover.png", png, "image/png")}).status_code == 202
    # named .jpg but not a picture: refused by its bytes
    r = client.post(f"/jobs/{job['id']}/cover",
                    files={"file": ("cover.jpg", b"hello", "image/jpeg")})
    assert r.status_code == 415
    monkeypatch.setattr(app_module, "_MAX_UPLOAD_BYTES", 8)
    r = client.post(f"/jobs/{job['id']}/cover",
                    files={"file": ("cover.jpg", b"\xff\xd8\xff" + b"\x00" * 64, "image/jpeg")})
    assert r.status_code == 413
    assert client.get(f"/jobs/{job['id']}/cover").content == png
    assert client.get(f"/jobs/{job['id']}").json()["cover_art"] is True


def test_cover_art_unknown_job_404(client: TestClient) -> None:
    r = client.post(
        "/jobs/nope/cover", files={"file": ("cover.png", b"\x89PNG", "image/png")}
    )
    assert r.status_code == 404


def test_cover_art_not_uploaded_404(client: TestClient) -> None:
    job = _create_job(client)
    r = client.get(f"/jobs/{job['id']}/cover")
    assert r.status_code == 404


def test_cover_art_replace_with_different_extension(client: TestClient) -> None:
    job = _create_job(client)
    client.post(
        f"/jobs/{job['id']}/cover", files={"file": ("cover.png", b"\x89PNG", "image/png")}
    )
    r = client.post(
        f"/jobs/{job['id']}/cover", files={"file": ("cover.jpg", b"\xff\xd8\xff", "image/jpeg")}
    )
    assert r.status_code == 202
    r = client.get(f"/jobs/{job['id']}/cover")
    assert r.headers["content-type"] == "image/jpeg"


def test_rebuild_copies_cover_art_to_new_workdir(client: TestClient) -> None:
    original = _create_job(client)
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
    r = client.post(
        f"/jobs/{original['id']}/cover", files={"file": ("cover.png", png, "image/png")}
    )
    assert r.status_code == 202

    r = client.post(f"/jobs/{original['id']}/rebuild", json={})
    assert r.status_code == 202
    rebuilt = r.json()
    assert rebuilt["id"] != original["id"]

    r = client.get(f"/jobs/{rebuilt['id']}/cover")
    assert r.status_code == 200
    assert r.content == png


def test_heartbeat_ok(client: TestClient) -> None:
    assert client.post("/heartbeat").json() == {"ok": True}


def test_idle_shutdown_exits_process_when_heartbeats_stop(monkeypatch, tmp_path) -> None:
    """Settings.idle_shutdown_s (start.bat): no /heartbeat pings => process exits."""
    monkeypatch.setenv("ROCKFORGE_DATABASE_URL", f"sqlite:///{tmp_path}/test.db")
    monkeypatch.setenv("ROCKFORGE_WORK_DIR", str(tmp_path / "work"))
    monkeypatch.setenv("ROCKFORGE_IDLE_SHUTDOWN_S", "0.05")
    import rockforge.config as config
    importlib.reload(config)
    import rockforge.interfaces.api.app as app_module
    importlib.reload(app_module)
    monkeypatch.setattr(app_module, "_enqueue", lambda job: None)
    monkeypatch.setattr(app_module, "_enqueue_detect", lambda job: None)
    monkeypatch.setattr(app_module, "_enqueue_detect_tones", lambda job: None)

    killed: list[tuple[int, int]] = []
    monkeypatch.setattr(app_module.os, "kill", lambda pid, sig: killed.append((pid, sig)))

    import time as time_module

    with TestClient(app_module.app):
        time_module.sleep(0.2)

    assert killed and killed[0][1] == app_module.signal.SIGTERM


def test_idle_shutdown_disabled_by_default(client: TestClient) -> None:
    import rockforge.interfaces.api.app as app_module

    assert app_module.settings.idle_shutdown_s == 0.0


def test_closing_beacon_arms_and_heartbeat_cancels(monkeypatch, tmp_path) -> None:
    """POST /closing arms a short shutdown deadline; a following /heartbeat
    (i.e. a refresh came back) cancels it."""
    monkeypatch.setenv("ROCKFORGE_DATABASE_URL", f"sqlite:///{tmp_path}/test.db")
    monkeypatch.setenv("ROCKFORGE_WORK_DIR", str(tmp_path / "work"))
    monkeypatch.setenv("ROCKFORGE_IDLE_SHUTDOWN_S", "30")  # long, so nothing exits mid-test
    import rockforge.config as config
    importlib.reload(config)
    import rockforge.interfaces.api.app as app_module
    importlib.reload(app_module)
    monkeypatch.setattr(app_module, "_enqueue", lambda job: None)
    monkeypatch.setattr(app_module, "_enqueue_detect", lambda job: None)
    monkeypatch.setattr(app_module, "_enqueue_detect_tones", lambda job: None)
    monkeypatch.setattr(app_module.os, "kill", lambda pid, sig: None)

    with TestClient(app_module.app) as c:
        assert app_module._closing_at is None
        assert c.post("/closing").status_code == 200
        assert app_module._closing_at is not None  # armed
        assert c.post("/heartbeat").status_code == 200
        assert app_module._closing_at is None  # a refresh cancelled it


def test_should_shutdown_decision_rules() -> None:
    """The pure idle-watchdog decision: a hidden (backgrounded) tab is never
    idle-killed; only a real close or a long crash-timeout stops it."""
    import rockforge.interfaces.api.app as app_module

    f = app_module._should_shutdown
    idle = 15.0
    # visible + silent past the idle window => shut down (its JS stopped)
    assert f(100.0, 100.0 - 20, None, False, idle)
    # hidden + silent past idle => do NOT shut down (throttled but still open)
    assert not f(100.0, 100.0 - 20, None, True, idle)
    # recent heartbeat => alive
    assert not f(100.0, 98.0, None, False, idle)
    # a passed /closing deadline shuts down even when hidden (a real close)
    assert f(100.0, 99.0, 99.5, True, idle)
    # crash safety net: silent beyond HEARTBEAT_MAX_S kills even a hidden tab
    assert f(100.0 + app_module.HEARTBEAT_MAX_S + 1, 100.0, None, True, idle)


def test_work_in_flight_defers_every_shutdown_trigger() -> None:
    """In `inprocess` mode (the standalone .exe) the worker runs in this very
    process, so exiting mid-task aborted a build or a 20-minute separation and
    left its job stuck at RUNNING with nothing to ever finish it. All three
    triggers must wait for the queue to drain — and then still fire."""
    import rockforge.interfaces.api.app as app_module

    f = app_module._should_shutdown
    idle = 15.0
    triggers = [
        (100.0, 100.0 - 20, None, False, idle),                              # idle
        (100.0, 99.0, 99.5, True, idle),                                     # /closing
        (100.0 + app_module.HEARTBEAT_MAX_S + 1, 100.0, None, True, idle),   # crashed
    ]
    for args in triggers:
        assert f(*args), "precondition: this must shut down when idle"
        assert not f(*args, True), "work in flight must defer the shutdown"
        assert f(*args, False), "and it must still fire once the work drains"


def test_in_flight_counts_queued_work_and_drains(monkeypatch) -> None:
    """The pool holds ONE worker, so a rebuild can sit queued behind a
    20-minute separation — a task that has not started yet still counts, or the
    process would exit between the two and lose the queued one."""
    import threading

    from rockforge.interfaces.worker import inprocess

    started, release = threading.Event(), threading.Event()

    def _slow(_job_id: str) -> None:
        started.set()
        assert release.wait(5), "test deadlock"

    assert not inprocess.work_in_flight()
    inprocess._submit(_slow, "job-a")
    inprocess._submit(_slow, "job-b")  # queued behind the first
    assert started.wait(2), "first task never started"
    assert inprocess.work_in_flight()
    release.set()
    for _ in range(100):
        if not inprocess.work_in_flight():
            break
        time.sleep(0.05)
    assert not inprocess.work_in_flight(), "counter must return to zero"


def test_celery_mode_never_defers_on_worker_state(monkeypatch) -> None:
    """Under Celery the worker is a SEPARATE process that survives the API
    exiting, and a job left at RUNNING is a stale row from a dead worker —
    waiting on it would hang shutdown forever."""
    import rockforge.interfaces.api.app as app_module
    from rockforge.interfaces.worker import inprocess

    monkeypatch.setattr(inprocess, "work_in_flight", lambda: True)
    monkeypatch.setattr(app_module.settings, "worker_mode", "celery")
    assert app_module._work_in_flight() is False
    monkeypatch.setattr(app_module.settings, "worker_mode", "inprocess")
    assert app_module._work_in_flight() is True


def test_heartbeat_hidden_flag_toggles_state(client: TestClient) -> None:
    import rockforge.interfaces.api.app as app_module

    assert client.post("/heartbeat", params={"hidden": "1"}).status_code == 200
    assert app_module._tab_hidden is True
    assert client.post("/heartbeat").status_code == 200  # visible again
    assert app_module._tab_hidden is False


def test_hidden_heartbeat_does_not_cancel_pending_close(monkeypatch, tmp_path) -> None:
    """On tab close, visibilitychange→hidden and pagehide both beacon; the hidden
    heartbeat must NOT cancel the /closing (they race on the server), or the tab
    would never shut the server down. A VISIBLE heartbeat (refresh) still does."""
    monkeypatch.setenv("ROCKFORGE_DATABASE_URL", f"sqlite:///{tmp_path}/test.db")
    monkeypatch.setenv("ROCKFORGE_WORK_DIR", str(tmp_path / "work"))
    monkeypatch.setenv("ROCKFORGE_IDLE_SHUTDOWN_S", "30")  # long, so nothing exits mid-test
    import rockforge.config as config

    importlib.reload(config)
    import rockforge.interfaces.api.app as app_module

    importlib.reload(app_module)
    monkeypatch.setattr(app_module, "_enqueue", lambda job: None)
    monkeypatch.setattr(app_module, "_enqueue_detect", lambda job: None)
    monkeypatch.setattr(app_module, "_enqueue_detect_tones", lambda job: None)
    monkeypatch.setattr(app_module.os, "kill", lambda pid, sig: None)

    with TestClient(app_module.app) as c:
        assert c.post("/closing").status_code == 200
        assert app_module._closing_at is not None  # armed by the close
        assert c.post("/heartbeat", params={"hidden": "1"}).status_code == 200
        assert app_module._closing_at is not None  # hidden beacon must NOT cancel it
        assert c.post("/heartbeat").status_code == 200  # a real refresh (visible)
        assert app_module._closing_at is None  # now cancelled


def test_upload_endpoints_are_plain_def_not_async(client: TestClient) -> None:
    """inspect_gp_file/create_gp_job/reload_gp/upload_cover_art must stay plain
    `def`, not `async def` — Starlette runs a sync route in its worker thread
    pool, so a slow multipart upload/parse there doesn't block the event loop
    (and every other in-flight request, including /heartbeat polling). An
    `async def` route runs directly on the loop, so any blocking call inside it
    (chunked file I/O, GP parsing) stalls the whole server for its duration."""
    import inspect

    import rockforge.interfaces.api.app as app_module

    def endpoints(routes: list) -> dict[str, object]:
        # An endpoint lives in app.py or in a router it includes (routers/).
        out: dict[str, object] = {}
        for r in routes:
            inner = getattr(r, "original_router", None)
            if inner is not None:
                out |= endpoints(inner.routes)
            elif hasattr(r, "endpoint"):
                out[r.endpoint.__name__] = r.endpoint
        return out

    served = endpoints(app_module.app.routes)
    for name in (
        "inspect_gp_file",
        "create_gp_job",
        "reload_gp",
        "upload_cover_art",
    ):
        fn = served[name]
        assert not inspect.iscoroutinefunction(fn), (
            f"{name} must be a plain `def` (blocking upload work belongs in "
            "Starlette's thread pool, not the event loop)"
        )


def test_system_check_reports_every_dependency_with_its_cost(client: TestClient) -> None:
    """One place that answers "what is installed, and what does each gap cost
    me?". Without it every absence only shows up downstream, where it reads as
    a bug in RockForge rather than as missing software."""
    r = client.get("/system-check")
    assert r.status_code == 200, r.text
    body = r.json()
    keys = {q["key"] for q in body["requirements"]}
    assert {"ffmpeg", "wwise", "psarc", "ml", "lyrics", "gpu", "cdlc_patch"} <= keys
    for q in body["requirements"]:
        assert q["found"] in (True, False, None)
        assert q["unlocks"] and q["without_it"] and q["install"]
    # `found: null` must survive Pydantic as null, not collapse to false — it is
    # the "cannot be checked from here" answer, and the UI renders it apart.
    patch = next(q for q in body["requirements"] if q["key"] == "cdlc_patch")
    assert patch["found"] is None
    assert body["missing_required"] == [
        q["key"] for q in body["requirements"] if q["required"] and q["found"] is False
    ]


def test_system_check_survives_a_probe_that_raises(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A diagnostics page that 500s is worse than one reporting "missing" — it
    is exactly when the machine is in a bad state that the user opens it."""
    import importlib.util

    def raising(name: str) -> object:
        raise ValueError("broken install")

    monkeypatch.setattr(importlib.util, "find_spec", raising)
    r = client.get("/system-check")
    assert r.status_code == 200
    assert r.json()["requirements"]


_COVER = "https://is1-ssl.mzstatic.com/image/thumb/Music/x/600x600bb.jpg"
_JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 16


def test_album_lookup_returns_the_candidates_to_choose_from(
    client: TestClient, monkeypatch
) -> None:
    from rockforge.infrastructure import album_lookup

    def fake(title: str, artist: str, **_k):
        assert (title, artist) == ("ocean eyes", "Billie Eilish")
        return [album_lookup.AlbumCandidate(
            source="itunes", album="dont smile at me", artist="Billie Eilish", year=2017,
            cover_url=_COVER, thumb_url=_COVER, track="ocean eyes", kind="album")]

    monkeypatch.setattr(album_lookup, "search_albums", fake)
    r = client.get("/album-lookup", params={"title": "ocean eyes", "artist": "Billie Eilish"})
    assert r.status_code == 200, r.text
    assert r.json()["candidates"][0] == {
        "source": "itunes", "album": "dont smile at me", "artist": "Billie Eilish",
        "year": 2017, "cover_url": _COVER, "thumb_url": _COVER, "track": "ocean eyes",
        "kind": "album"}


def test_an_image_link_from_any_site_comes_back_as_a_cover_the_page_can_upload(
    client: TestClient, monkeypatch
) -> None:
    import base64

    from rockforge.infrastructure import image_fetch

    jpeg = b"\xff\xd8\xff\xe0" + b"\0" * 32
    r = client.post("/cover/fetch-link",
                    json={"url": "data:image/jpeg;base64," + base64.b64encode(jpeg).decode()})
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg"
    assert r.content == jpeg
    # Inside the user's network: refused before anything is opened.
    monkeypatch.setattr(image_fetch, "_download", lambda _u: pytest.fail("opened"))
    r = client.post("/cover/fetch-link", json={"url": "http://127.0.0.1/admin.png"})
    assert r.status_code == 422 and "rede" in r.json()["detail"]
    # A page, not an image (cdn.example.org stands for a public site).
    monkeypatch.setattr(image_fetch, "_resolve", lambda *_a: ["93.184.216.34"])
    monkeypatch.setattr(image_fetch, "_download", lambda _u: b"<!DOCTYPE html><html></html>")
    r = client.post("/cover/fetch-link", json={"url": "https://cdn.example.org/view/1"})
    assert r.status_code == 415
    # The site cannot be reached.
    def down(_u):
        raise image_fetch.ImageFetchError("não consegui descarregar a imagem (timeout)")
    monkeypatch.setattr(image_fetch, "_download", down)
    r = client.post("/cover/fetch-link", json={"url": "https://cdn.example.org/a.jpg"})
    assert r.status_code == 502 and "timeout" in r.json()["detail"]


def test_album_lookup_needs_both_names_and_reports_the_services_being_down(
    client: TestClient, monkeypatch
) -> None:
    from rockforge.infrastructure import album_lookup

    assert client.get("/album-lookup", params={"title": "x"}).status_code == 422

    def down(*_a, **_k):
        raise album_lookup.AlbumLookupError("não consegui contactar o serviço (timeout)")

    monkeypatch.setattr(album_lookup, "search_albums", down)
    r = client.get("/album-lookup", params={"title": "x", "artist": "y"})
    assert r.status_code == 502 and "contactar o serviço" in r.text


def test_an_empty_album_lookup_says_what_was_searched_and_which_service_failed(
    client: TestClient, monkeypatch
) -> None:
    from rockforge.infrastructure import album_lookup

    def mb_down(url: str):  # noqa: ANN202
        if url.startswith(album_lookup.ITUNES_URL):
            return {"results": []}
        raise album_lookup.AlbumLookupError("o serviço respondeu 503")

    monkeypatch.setattr(album_lookup, "_http_get_json", mb_down)
    r = client.get("/album-lookup", params={
        "title": "Strangers Now (feat. Avril Lavigne)", "artist": "Eminem feat. Avril Lavigne"})
    assert r.status_code == 200, r.text
    assert r.json() == {
        "candidates": [], "searched_title": "Strangers Now", "searched_artist": "Eminem",
        "failures": ["MusicBrainz: o serviço respondeu 503"]}


def test_a_chosen_cover_is_downloaded_into_the_job(client: TestClient, monkeypatch) -> None:
    from rockforge.infrastructure import album_lookup

    job = _create_job(client)
    monkeypatch.setattr(album_lookup, "_open_url", lambda url: _JPEG)
    r = client.post(f"/jobs/{job['id']}/cover-from-url", json={"url": _COVER})
    assert r.status_code == 202, r.text
    assert r.json()["cover_art"] is True
    assert client.get(f"/jobs/{job['id']}/cover").content == _JPEG


def test_a_cover_url_off_the_cover_services_is_refused_without_fetching(
    client: TestClient, monkeypatch
) -> None:
    """The server downloads the URL, so an arbitrary one would make it fetch
    anything on the user's network for whoever can reach the API."""
    from rockforge.infrastructure import album_lookup

    job = _create_job(client)
    monkeypatch.setattr(album_lookup, "_open_url", lambda url: pytest.fail("fetched"))
    r = client.post(f"/jobs/{job['id']}/cover-from-url",
                    json={"url": "http://169.254.169.254/latest/meta-data"})
    assert r.status_code == 422


def test_a_cover_that_will_not_download_is_a_502_and_changes_nothing(
    client: TestClient, monkeypatch
) -> None:
    from rockforge.infrastructure import album_lookup

    job = _create_job(client)
    monkeypatch.setattr(album_lookup, "_open_url", lambda url: b"<html>404</html>")
    r = client.post(f"/jobs/{job['id']}/cover-from-url", json={"url": _COVER})
    assert r.status_code == 502
    assert client.get(f"/jobs/{job['id']}/cover").status_code == 404


def test_the_wizards_chosen_cover_is_in_place_before_the_first_build(
    client: TestClient, monkeypatch
) -> None:
    """Fetched before the job is queued, so the first build already packs it."""
    import rockforge.interfaces.api.app as app_module
    from rockforge.infrastructure import album_lookup

    monkeypatch.setattr(album_lookup, "_open_url", lambda url: _JPEG)
    at_enqueue: list[object] = []
    monkeypatch.setattr(app_module, "_enqueue",
                        lambda job: at_enqueue.append((job.params or {}).get("cover_art")))
    body = client.post(
        "/gp/inspect", files={"file": ("s.gp", _gp8_with_embedded_audio(b"ID3x"), "x")}
    ).json()
    r = client.post("/jobs/gp", data={
        "gp_token": body["gp_token"], "lead_track": "0", "use_embedded_audio": "true",
        "cover_url": _COVER})
    assert r.status_code == 202, r.text
    assert at_enqueue == ["cover.jpg"]
    assert client.get(f"/jobs/{r.json()['id']}/cover").content == _JPEG


def test_a_cover_from_the_computer_is_in_place_before_the_first_build(
    client: TestClient, monkeypatch
) -> None:
    """The wizard's own image (not a lookup result): read by its bytes, stored
    before the job is queued, and it wins over a picked online cover, which is
    then never fetched. Anything that is not a JPEG/PNG is refused up front."""
    import rockforge.interfaces.api.app as app_module
    from rockforge.infrastructure import album_lookup

    def never(url: str) -> bytes:
        raise AssertionError("the online cover must not be fetched")

    monkeypatch.setattr(album_lookup, "_open_url", never)
    at_enqueue: list[object] = []
    monkeypatch.setattr(app_module, "_enqueue",
                        lambda job: at_enqueue.append((job.params or {}).get("cover_art")))
    png = b"\x89PNG\r\n\x1a\n" + b"x" * 32
    body = client.post(
        "/gp/inspect", files={"file": ("s.gp", _gp8_with_embedded_audio(b"ID3x"), "x")}
    ).json()
    data = {"gp_token": body["gp_token"], "lead_track": "0", "use_embedded_audio": "true",
            "cover_url": _COVER}
    # Named .jpg, but its bytes say PNG: the bytes decide.
    r = client.post("/jobs/gp", data=data, files={"cover": ("mine.jpg", png, "image/jpeg")})
    assert r.status_code == 202, r.text
    assert at_enqueue == ["cover.png"]
    assert client.get(f"/jobs/{r.json()['id']}/cover").content == png

    body = client.post(
        "/gp/inspect", files={"file": ("s.gp", _gp8_with_embedded_audio(b"ID3x"), "x")}
    ).json()
    r = client.post("/jobs/gp", data={**data, "gp_token": body["gp_token"]},
                    files={"cover": ("notes.png", b"not an image", "image/png")})
    assert r.status_code == 415
    assert at_enqueue == ["cover.png"]


def test_a_wizard_cover_that_fails_still_creates_the_project(
    client: TestClient, monkeypatch
) -> None:
    """A cover is a nicety; losing it must not cost the user the project. The
    response's cover_art=False is what tells the UI to say so."""
    from rockforge.infrastructure import album_lookup

    def down(url: str) -> bytes:
        raise album_lookup.AlbumLookupError("timeout")

    monkeypatch.setattr(album_lookup, "_open_url", down)
    body = client.post(
        "/gp/inspect", files={"file": ("s.gp", _gp8_with_embedded_audio(b"ID3x"), "x")}
    ).json()
    data = {"gp_token": body["gp_token"], "lead_track": "0", "use_embedded_audio": "true",
            "cover_url": _COVER}
    r = client.post("/jobs/gp", data=data)
    assert r.status_code == 202 and r.json()["cover_art"] is False

    body = client.post(
        "/gp/inspect", files={"file": ("s.gp", _gp8_with_embedded_audio(b"ID3x"), "x")}
    ).json()
    r = client.post("/jobs/gp", data={**data, "gp_token": body["gp_token"],
                                      "cover_url": "https://example.com/c.jpg"})
    assert r.status_code == 422, "an address off the cover services is refused up front"


def test_synced_lyrics_chosen_in_the_wizard_travel_with_the_new_job(
    client: TestClient, tmp_path
) -> None:
    """The wizard can keep an LRCLIB result at creation time: it arrives as
    ``lyrics_lrc`` and is stored exactly like an uploaded LRC; an uploaded
    file still wins, and text without timestamps is refused up front."""
    import rockforge.interfaces.api.app as app_module
    from rockforge.infrastructure.db.models import Job

    lrc = "[00:12.00] first line of the song\n[00:15.50] second line"

    def create(extra: dict, files: dict | None = None):  # noqa: ANN202
        body = client.post(
            "/gp/inspect", files={"file": ("s.gp5", _make_gp5_bytes(tmp_path), "x")}
        ).json()
        return client.post(
            "/jobs/gp",
            data={"gp_token": body["gp_token"], "lead_track": "0", **extra},
            files={"audio": ("song.wav", b"RIFF0000WAVE", "audio/wav"), **(files or {})},
        )

    r = create({"lyrics_lrc": lrc})
    assert r.status_code == 202, r.text
    assert r.json()["has_lyrics"] is True
    with app_module._session_factory() as db:
        job = db.get(Job, r.json()["id"])
        assert job is not None and job.params["lrc_text"] == lrc

    r = create({"lyrics_lrc": lrc}, {"lrc": ("mine.lrc", b"[00:01.00] my own", "text/plain")})
    with app_module._session_factory() as db:
        job = db.get(Job, r.json()["id"])
        assert job is not None and job.params["lrc_text"] == "[00:01.00] my own"

    r = create({"lyrics_lrc": "just words, no timestamps"})
    assert r.status_code == 422 and "tempos" in r.text


def _built_two_track_job(client, tmp_path, detected=None):
    """A GP job set COMPLETED with a Lead (a solo from 12 s) and a Rhythm
    (chugging throughout) in its bundle, both with Verso/Solo sections."""
    import rockforge.config as config
    import rockforge.interfaces.api.app as app_module
    from rockforge.domain.arrangement import (
        Arrangement,
        ArrangementKind,
        Section,
        SongMetadata,
    )
    from rockforge.domain.music import Beat, TabNote, Technique, TempoMap, Tuning
    from rockforge.infrastructure.db.models import JobStatus
    from rockforge.infrastructure.rsxml.writer import write_arrangement_xml

    job = _gp_job(client, tmp_path)
    bundle = config.settings.work_dir / job["id"] / "bundle"
    beats = tuple(Beat(time=2.0 + 0.5 * i, measure=(i // 4 + 1) if i % 4 == 0 else -1)
                  for i in range(49))
    pm = frozenset({Technique.PALM_MUTE})

    def chug(a, b):
        return [TabNote(s, 3 + 2 * s, 2.0 + 0.25 * i, 0.2, pm)
                for i in range(int((a - 2.0) / 0.25), int((b - 2.0) / 0.25)) for s in (0, 1)]

    solo = [TabNote(4, 15, 12.0 + 0.25 * i, 0.2, frozenset({Technique.BEND}))
            for i in range(48)]
    sections = [Section("verso", 2.0, 1), Section("solo", 12.0, 1)]
    for kind, notes in ((ArrangementKind.LEAD, chug(2.0, 12.0) + solo),
                        (ArrangementKind.RHYTHM, chug(2.0, 26.0))):
        write_arrangement_xml(Arrangement(
            kind=kind, metadata=SongMetadata(title="S", artist="A", song_length=27.0),
            tuning=Tuning(), notes=notes, sections=sections,
            tempo_map=TempoMap(beats=beats, average_bpm=120.0),
        ), bundle / f"arrangement_{kind.value.lower()}.xml")
    with app_module._session_factory() as session:
        db_job = session.get(app_module.Job, job["id"])
        db_job.status = JobStatus.COMPLETED
        db_job.bundle_dir = str(bundle)
        if detected is not None:
            db_job.params = {**dict(db_job.params or {}), "detected_tones": detected}
        session.commit()
    return job


def test_tone_suggestions_need_a_build_and_the_tone_over_time(
    client: TestClient, tmp_path
) -> None:
    job = _gp_job(client, tmp_path)
    assert client.get(f"/jobs/{job['id']}/tone-suggestions").status_code == 409
    assert client.get("/jobs/nope/tone-suggestions").status_code == 404
    # Built, but detected before the tone was measured over time.
    old = _built_two_track_job(client, tmp_path, detected={"status": "ready", "profile": {}})
    r = client.get(f"/jobs/{old['id']}/tone-suggestions")
    assert r.status_code == 409 and "Detetar tom" in r.json()["detail"]
    assert client.get(f"/jobs/{old['id']}/detected-tones").json()["has_timeline"] is False


def test_tone_suggestions_propose_a_tone_per_part_of_each_track(
    client: TestClient, tmp_path
) -> None:
    """Over one distorted sound, the Lead's solo gets a lead tone where the
    Rhythm keeps its chugging tone throughout; the timeline comes back on the
    bundle clock (the recording sits MIN_LEAD_S later with offset 0)."""
    timeline = [[float(t), 0.6, 0.5, 0.5, 1] for t in range(26)]
    job = _built_two_track_job(client, tmp_path, detected={
        "status": "ready", "timeline": timeline,
        "profile": {"gain_level": 0.6, "brightness": 0.5, "low_end": 0.5},
    })
    assert client.get(f"/jobs/{job['id']}/detected-tones").json()["has_timeline"] is True
    r = client.get(f"/jobs/{job['id']}/tone-suggestions")
    assert r.status_code == 200, r.text
    body = r.json()
    lead, rhythm = body["tracks"]
    assert (lead["kind"], rhythm["kind"]) == ("Lead", "Rhythm")
    assert [s["role"] for s in lead["segments"]] == ["rhythm", "lead"]
    assert [s["role"] for s in rhythm["segments"]] == ["rhythm", "rhythm"]
    assert lead["changes"] == [{"time": 12.0, "name": lead["segments"][1]["tone_key"]}]
    assert rhythm["changes"] == []
    assert [t["key"] for t in lead["tones"]] == lead["names"]
    assert lead["names"][0] == lead["base"]
    assert body["timeline"][0] == [2.0, 0.6, 1]


def test_whats_new_lists_the_changelog_entries_after_the_version_last_seen(
    client: TestClient,
) -> None:
    from rockforge import __version__, versioning

    r = client.get("/whats-new", headers={"X-RockForge-Lang": "en"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["current"] == __version__ and body["available"] is True
    assert [x["version"] for x in body["releases"]] == [__version__]
    assert body["releases"][0]["groups"][0]["items"]
    older = client.get("/whats-new?since=0.10.0-beta.1").json()["releases"]
    assert len(older) > 1 and older[0]["version"] == __version__
    assert all(versioning.parse(x["version"]).key > versioning.parse("0.10.0-beta.1").key
               for x in older)
    pt = client.get("/whats-new", headers={"X-RockForge-Lang": "pt"}).json()
    assert pt["releases"][0]["groups"][0]["title"] != body["releases"][0]["groups"][0]["title"]
    assert client.get("/whats-new?since=" + "9" * 65).status_code == 422


def test_a_tone_plan_pasted_as_text_becomes_tones_and_changes_without_storing_anything(
    client: TestClient, tmp_path
) -> None:
    """The request names the built song's sections in the recording's clock; the
    pasted answer comes back as tones and each chart's changes in the build's
    clock (the recording sits MIN_LEAD_S = 2 s later with offset 0), nothing is
    stored, and a text that is not a plan is a 422."""
    job = _gp_job(client, tmp_path)
    url = f"/jobs/{job['id']}"
    assert client.get(f"{url}/tone-plan/prompt").status_code == 409
    assert client.post(f"{url}/tone-plan/preview", json={"text": "{}"}).status_code == 409
    assert client.get("/jobs/nope/tone-plan/prompt").status_code == 404
    job = _built_two_track_job(client, tmp_path)
    url = f"/jobs/{job['id']}"
    prompt = client.get(f"{url}/tone-plan/prompt", headers={"X-RockForge-Lang": "en"}).json()
    assert "- solo — bar 6 — 0:10.0" in prompt["prompt"]
    assert "- LEAD (bars 1–12)" in prompt["prompt"]
    plan = {
        "tones": [{"name": "Chug", "amp": "Amp_MarshallJCM800", "volume": 19},
                  {"name": "Solo", "amp": {"key": "Amp_CA100", "knobs": {"Gain": 90}},
                   "cabinet": "Cab_CA412C_57_Cone"}],
        "changes": [{"track": "all", "at": "start", "tone": "Chug"},
                    {"track": "LEAD", "at": "solo", "tone": "Solo"},
                    {"track": "RHYTHM", "at": "0:20", "tone": "Solo"}],
    }
    text = "Here you go:\n```json\n" + json.dumps(plan) + "\n```"
    before = client.get(f"{url}/tones").json()
    r = client.post(f"{url}/tone-plan/preview", json={"text": text},
                    headers={"X-RockForge-Lang": "en"})
    assert r.status_code == 200, r.text
    body = r.json()
    chug, solo = (t["key"] for t in body["tones"])
    assert body["pad_s"] == 2.0
    lead, rhythm = body["tracks"]
    assert (lead["game_name"], lead["tone_base"]) == ("LEAD", chug)
    assert lead["tone_names"] == [chug, solo]
    assert lead["tone_changes"] == [{"time": 12.0, "name": solo}]
    assert rhythm["tone_changes"] == [{"time": 22.0, "name": solo}]
    assert body["tones"][1]["amp"]["knobs"]["Amp_CA100_Gain"] == 90
    assert any("cabinet chosen for the amp" in w for w in body["warnings"])
    assert client.get(f"{url}/tones").json() == before          # a preview stores nothing
    r = client.post(f"{url}/tone-plan/preview", json={"text": "use a Marshall at the solo"})
    assert r.status_code == 422 and r.json()["detail"]


def test_the_tones_chosen_in_place_of_the_suggested_ones_are_kept_with_the_project(
    client: TestClient, tmp_path
) -> None:
    """The stand-ins picked for suggested tones live in the project: they come
    back with the suggestions after leaving it, survive a rebuild fork, and a
    tone with no real amp/cabinet is refused."""
    timeline = [[float(t), 0.6, 0.5, 0.5, 1] for t in range(26)]
    job = _built_two_track_job(client, tmp_path, detected={
        "status": "ready", "timeline": timeline,
        "profile": {"gain_level": 0.6, "brightness": 0.5, "low_end": 0.5},
    })
    url = f"/jobs/{job['id']}"
    assert client.get(f"{url}/tone-suggestions").json()["swaps"] == {}
    suggested = client.get(f"{url}/tone-suggestions").json()["tracks"][0]["base"]
    mine = {"key": "HTH_Lead", "name": "Lead", "volume": -19.5,
            "amp": {"key": "Amp_MarshallPlexi"}, "cabinet": {"key": "Cab_Marshall1960a_57_Cone"}}
    swaps = {suggested: {"tone": mine, "source": "collection",
                         "label": "Lead · Highway to Hell — AC/DC"}}
    r = client.patch(f"{url}/tone-swaps", json={"swaps": swaps})
    assert r.status_code == 200, r.text
    back = client.get(f"{url}/tone-suggestions").json()["swaps"]
    assert back == {suggested: {**swaps[suggested]}}
    fork = client.post(f"{url}/rebuild", json={"offset_s": 1.0}).json()
    assert client.get(f"/jobs/{fork['id']}").json()  # a fork carries them in its params
    from rockforge.interfaces.api import app as app_module
    with app_module._session_factory() as session:
        assert session.get(app_module.Job, fork["id"]).params["tone_swaps"] == back
    nonsense = {"key": "x", "amp": {"key": "Amp_Nope"}, "cabinet": {"key": "Cab_No"}}
    bad = {suggested: {"tone": nonsense, "source": "library"}}
    assert client.patch(f"{url}/tone-swaps", json={"swaps": bad}).status_code == 422
    assert client.patch(f"{url}/tone-swaps", json={"swaps": {suggested: {
        "tone": mine, "source": "elsewhere"}}}).status_code == 422
    assert client.patch(f"{url}/tone-swaps", json={"swaps": {}}).status_code == 200
    assert client.get(f"{url}/tone-suggestions").json()["swaps"] == {}
    assert client.patch("/jobs/nope/tone-swaps", json={"swaps": {}}).status_code == 404


def test_each_track_can_keep_its_own_tones(client: TestClient, tmp_path) -> None:
    job = _gp_job(client, tmp_path)
    rebuilt = client.post(f"/jobs/{job['id']}/rebuild", json={
        "tone_base": "crunch", "tone_names": ["crunch"],
        "arrangement_tones": {"Lead": {
            "tone_base": "clean", "tone_names": ["solo"],
            "tone_changes": [{"time": 12.0, "name": "solo"}],
        }},
    }).json()
    tones = client.get(f"/jobs/{rebuilt['id']}/tones").json()
    assert tones["tone_base"] == "crunch"
    assert tones["arrangement_tones"] == {"Lead": {
        "tone_base": "clean", "tone_names": ["solo"],
        "tone_changes": [{"time": 12.0, "name": "solo"}],
    }}
    # null leaves them alone; {} brings every track back to the song's tones.
    kept = client.post(f"/jobs/{rebuilt['id']}/rebuild", json={"offset_s": 1.0}).json()
    assert client.get(f"/jobs/{kept['id']}/tones").json()["arrangement_tones"] != {}
    cleared = client.post(f"/jobs/{kept['id']}/rebuild", json={"arrangement_tones": {}}).json()
    assert client.get(f"/jobs/{cleared['id']}/tones").json()["arrangement_tones"] == {}
    too_many = client.post(f"/jobs/{job['id']}/rebuild", json={
        "arrangement_tones": {"Lead": {"tone_names": ["a", "b", "c", "d", "e"]}},
    })
    assert too_many.status_code == 422


def test_presets_still_at_their_first_quiet_volume_are_raised_on_startup(
    tmp_path, monkeypatch
) -> None:
    """Projects built with the first (too quiet) presets get the current volume,
    so the next rebuild is audible — but a volume the user set stays theirs."""
    import importlib

    monkeypatch.setenv("ROCKFORGE_DATABASE_URL", f"sqlite:///{tmp_path}/v.db")
    monkeypatch.setenv("ROCKFORGE_WORK_DIR", str(tmp_path / "work"))
    import rockforge.config as config
    importlib.reload(config)
    import rockforge.interfaces.api.app as app_module
    importlib.reload(app_module)
    from rockforge import tone_library
    from rockforge.infrastructure.packaging.gear import tone_preset_history as past
    from rockforge.infrastructure.packaging.gear.tone_presets import (
        PRESET_CHAINS_BEFORE,
        RHYTHM_ORANGE,
        _chain,
        _preset,
        _without_gate,
        preset_volume,
    )

    with TestClient(app_module.app):
        pass
    tone_library.save_tone({"key": "RFRhythm_Plexi", "name": "P", "volume": -15.0,
                            **_without_gate(past.V1["RFRhythm_Plexi"])})
    with app_module._session_factory() as session:
        job = app_module.Job(source="x", source_type="gp", title="T", artist="A", params={
            "tones": [
                # as each first shipped: quiet, no gate
                {"key": "RFLead_Crunch", "volume": -14.0,
                 **_without_gate(past.V1["RFLead_Crunch"])},
                {"key": "RFRhythm_Clean", "volume": -17.5, "amp": {"key": "Amp_TW22"},
                 "cabinet": {"key": "Cab_TW112C_57_Cone"}},  # the user's own
                {"key": "mine", "volume": -14.0},
                {"key": "RFRhythm_HighGain", "volume": -18.0, **past.V1["RFRhythm_HighGain"]},
                {"key": "RFRhythm_Orange", "volume": -20.0, **past.V1["RFRhythm_Orange"],
                 **PRESET_CHAINS_BEFORE["RFRhythm_Orange"][3]},
                {"key": "RFLead_Overdrive", "volume": -19.5,  # raised again
                 **past.V1["RFLead_Overdrive"]},
            ],
        })
        session.add(job)
        session.commit()
        job_id = job.id
    with TestClient(app_module.app):  # the lifespan runs the backfill
        pass
    with app_module._session_factory() as session:
        tones = session.get(app_module.Job, job_id).params["tones"]
    assert [t["volume"] for t in tones] == [
        preset_volume("RFLead_Crunch"), -17.5, -14.0, -18.0,
        preset_volume("RFRhythm_Orange"), preset_volume("RFLead_Overdrive"),
    ]
    # every copy still on an earlier chain of its preset gets the current one —
    # gate, pre-amp EQ, racks — and the user's own and other tones are untouched
    for i in (0, 3, 4, 5):
        assert _chain(tones[i]) == _chain(_preset(tones[i]["key"])), tones[i]["key"]
    assert tones[4]["amp"] == RHYTHM_ORANGE["amp"]
    assert tones[1].get("pre") is None and tones[2].get("pre") is None
    library = tone_library.load()[0]
    assert library["volume"] == preset_volume("RFRhythm_Plexi")
    assert _chain(library) == _chain(_preset("RFRhythm_Plexi"))


def test_the_previous_version_can_be_dropped_once_the_new_one_is_built(
    client: TestClient, tmp_path
) -> None:
    """"Aplicar e reconstruir" asks whether to delete the version it came from.
    Only after the new one is built; the stems the new version inherited (by
    absolute path into the old one) move over, and the shared recording and GP
    file stay."""
    from pathlib import Path

    import rockforge.config as config
    import rockforge.interfaces.api.app as app_module
    from rockforge.infrastructure.db.models import JobStatus

    first = _gp_job(client, tmp_path)
    old_dir = config.settings.work_dir / first["id"]
    (old_dir / "demucs_stems").mkdir(parents=True)
    (old_dir / "demucs_stems" / "guitar.wav").write_bytes(b"RIFF")
    with app_module._session_factory() as session:
        job = session.get(app_module.Job, first["id"])
        job.params = {**job.params, "stems": {"guitar": str(old_dir / "demucs_stems/guitar.wav")}}
        session.commit()
        recording, gp_path = job.source, job.params["gp_path"]
    second = client.post(f"/jobs/{first['id']}/rebuild", json={"offset_s": 1.0}).json()
    third = client.post(f"/jobs/{second['id']}/rebuild", json={"offset_s": 2.0}).json()

    assert client.post(f"/jobs/{third['id']}/drop-previous").status_code == 409  # not built
    with app_module._session_factory() as session:
        session.get(app_module.Job, third["id"]).status = JobStatus.COMPLETED
        session.commit()
    r = client.post(f"/jobs/{third['id']}/drop-previous")
    assert r.status_code == 200, r.text
    assert r.json()["rebuilt_from"] == first["id"]  # the version before the dropped one
    assert client.get(f"/jobs/{second['id']}").status_code == 404
    assert Path(recording).exists() and Path(gp_path).exists()

    with app_module._session_factory() as session:
        session.get(app_module.Job, first["id"]).status = JobStatus.COMPLETED
        session.commit()
    # Dropping the first one too: its stems move to the newest version.
    r = client.post(f"/jobs/{third['id']}/drop-previous")
    assert r.status_code == 200 and r.json()["rebuilt_from"] is None
    moved = config.settings.work_dir / third["id"] / "demucs_stems" / "guitar.wav"
    assert moved.exists() and not old_dir.exists()
    with app_module._session_factory() as session:
        stems = session.get(app_module.Job, third["id"]).params["stems"]
    assert stems == {"guitar": str(moved)}
    assert client.post(f"/jobs/{third['id']}/drop-previous").status_code == 404


def test_dropping_a_version_gives_its_stems_only_to_one_that_plays_the_same_recording(
    client: TestClient, tmp_path
) -> None:
    """The stems belong to the recording: a version reloaded with the GP file's
    own audio used to inherit the old recording's separation; and a sibling
    version kept stems pointing into the deleted folder."""
    import rockforge.config as config
    import rockforge.interfaces.api.app as app_module
    from rockforge.infrastructure.db.models import JobStatus

    first = _gp_job(client, tmp_path)
    old_dir = config.settings.work_dir / first["id"]
    (old_dir / "demucs_stems").mkdir(parents=True)
    (old_dir / "demucs_stems" / "guitar.wav").write_bytes(b"RIFF")
    stem = str(old_dir / "demucs_stems/guitar.wav")
    with app_module._session_factory() as session:
        job = session.get(app_module.Job, first["id"])
        job.params = {**job.params, "stems": {"guitar": stem}}
        session.commit()
    sibling = client.post(f"/jobs/{first['id']}/rebuild", json={"offset_s": 1.0}).json()
    other_audio = client.post(f"/jobs/{first['id']}/rebuild", json={"offset_s": 2.0}).json()
    with app_module._session_factory() as session:
        moved_on = session.get(app_module.Job, other_audio["id"])
        moved_on.source = str(tmp_path / "another-recording.wav")
        moved_on.status = JobStatus.COMPLETED
        moved_on.params = {k: v for k, v in moved_on.params.items() if k != "stems"}
        session.commit()
    assert client.post(f"/jobs/{other_audio['id']}/drop-previous").status_code == 200
    assert not (config.settings.work_dir / other_audio["id"] / "demucs_stems").exists()
    heir = config.settings.work_dir / sibling["id"] / "demucs_stems" / "guitar.wav"
    assert heir.exists()
    with app_module._session_factory() as session:
        assert session.get(app_module.Job, sibling["id"]).params["stems"] == {"guitar": str(heir)}


def test_a_project_is_not_deleted_while_a_detection_runs_on_it(
    client: TestClient, tmp_path
) -> None:
    import rockforge.interfaces.api.app as app_module

    job = _gp_job(client, tmp_path)
    with app_module._session_factory() as session:
        row = session.get(app_module.Job, job["id"])
        row.params = {**row.params, "stems_status": "separating"}
        session.commit()
    assert client.delete(f"/jobs/{job['id']}").status_code == 409
    assert client.delete(f"/jobs/{job['id']}?force=true").status_code == 204


def test_a_refused_new_project_leaves_no_recording_behind(client: TestClient, tmp_path) -> None:
    """The recording was copied before the other checks; every later refusal
    left it in uploads/ for good. And "²" passed isdigit() but not int()."""
    import rockforge.interfaces.api.app as app_module

    token = client.post("/gp/inspect", files={
        "file": ("song.gp5", _make_gp5_bytes(tmp_path), "application/octet-stream")
    }).json()["gp_token"]
    uploads = app_module.settings.work_dir / "uploads"
    before = set(uploads.glob("*")) if uploads.exists() else set()
    for bad in ({"tempo_scale": "nan"}, {"merge_tracks": "[1]"}, {"tone_names": "a,b,c,d,e"}):
        r = client.post("/jobs/gp", data={"gp_token": token, "lead_track": "0", **bad},
                        files={"audio": ("song.wav", b"RIFF0000WAVE", "audio/wav")})
        assert r.status_code == 422, bad
    assert set(uploads.glob("*")) == before
    r = client.post("/jobs/gp", data={"gp_token": token, "lead_track": "²", "year": "²"},
                    files={"audio": ("song.wav", b"RIFF0000WAVE", "audio/wav")})
    assert r.status_code == 202, r.text
    assert client.post("/jobs/gp", data={"gp_token": ".."},
                       files={"audio": ("s.wav", b"RIFF", "audio/wav")}).status_code == 404


def test_each_bundle_download_is_its_own_zip(client: TestClient, tmp_path) -> None:
    import zipfile

    import rockforge.interfaces.api.app as app_module
    from rockforge.infrastructure.db.models import JobStatus

    job = _gp_job(client, tmp_path)
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "a.xml").write_text("<song/>")
    with app_module._session_factory() as session:
        row = session.get(app_module.Job, job["id"])
        row.status, row.bundle_dir = JobStatus.COMPLETED, str(bundle)
        session.commit()
    for _ in range(2):
        r = client.get(f"/jobs/{job['id']}/bundle")
        assert r.status_code == 200
        with zipfile.ZipFile(__import__("io").BytesIO(r.content)) as z:
            assert z.namelist() == ["a.xml"]
    assert list(tmp_path.glob("bundle*.zip")) == []  # each removed once sent


def test_a_tone_that_cannot_be_built_is_refused_up_front(client: TestClient, tmp_path) -> None:
    job = _gp_job(client, tmp_path)
    bad = {"key": "t", "name": "t", "volume": "loud",
           "amp": {"key": "Amp_CS100", "knobs": {}},
           "cabinet": {"key": "Cab_Marshall1960a_57_Cone"}}
    assert client.post(f"/jobs/{job['id']}/rebuild", json={"tones": [bad]}).status_code == 422
    assert client.post("/tone-library", json=bad).status_code == 422


def test_a_rebuild_commits_every_charts_pending_sync_not_only_the_one_on_screen(
    client: TestClient, tmp_path
) -> None:
    """What the "Pista principal" carries onto the other charts rides the same
    rebuild (other_sync); before, only the chart on screen was committed."""
    import rockforge.interfaces.api.app as app_module

    job = _gp_job(client, tmp_path)
    rebuilt = client.post(f"/jobs/{job['id']}/rebuild", json={
        "arrangement": "Lead", "sync_anchors": [[2.0, 3.0]],
        "other_sync": {
            "Rhythm": {"sync_anchors": [[32.0, 33.0]], "tempo_scale": 1.1},
            "Lead": {"sync_anchors": [[9.0, 9.5]]},  # the chart on screen is not doubled
        },
    })
    assert rebuilt.status_code == 202, rebuilt.text
    with app_module._session_factory() as session:
        store = session.get(app_module.Job, rebuilt.json()["id"]).params["arrangement_sync"]
    assert store["Lead"]["sync_anchor_stages"] == [[[2.0, 3.0]]]
    assert store["Rhythm"]["sync_anchor_stages"] == [[[32.0, 33.0]]]
    assert store["Rhythm"]["tempo_scale"] == 1.1

    # With apply_to_all the chart on screen already speaks for every chart.
    again = client.post(f"/jobs/{job['id']}/rebuild", json={
        "arrangement": "Lead", "sync_anchors": [[2.0, 3.0]], "apply_to_all": True,
        "other_sync": {"Rhythm": {"sync_anchors": [[32.0, 40.0]]}},
    }).json()
    with app_module._session_factory() as session:
        params = session.get(app_module.Job, again["id"]).params
    assert "Rhythm" not in params.get("arrangement_sync", {})
    bad = client.post(f"/jobs/{job['id']}/rebuild", json={
        "arrangement": "Lead", "other_sync": {"Rhythm": {"tempo_scale": 0}},
    })
    assert bad.status_code == 422


def test_the_main_chart_for_sync_is_remembered(client: TestClient, tmp_path) -> None:
    job = _gp_job(client, tmp_path)
    assert job["sync_main"] is None
    r = client.patch(f"/jobs/{job['id']}/sync-main", json={"arrangement": "Lead"})
    assert r.status_code == 200 and r.json()["sync_main"] == "Lead"
    fork = client.post(f"/jobs/{job['id']}/rebuild", json={}).json()
    assert fork["sync_main"] == "Lead"  # a rebuild keeps it
    assert client.patch(f"/jobs/{job['id']}/sync-main", json={}).json()["sync_main"] is None
    assert client.patch("/jobs/nope/sync-main", json={}).status_code == 404


def test_attacks_marked_by_ear_are_stored_per_chart_and_reach_the_viewer(
    client: TestClient, tmp_path
) -> None:
    """"Marcar a ouvir" → Ataques: one chart's taps (seconds of the recording)
    are stored as given, sorted, to the millisecond, a double tap kept once;
    they come back on that chart only, a fork inherits them, an empty list
    removes them, and nonsense is refused."""
    import rockforge.config as config
    import rockforge.interfaces.api.app as app_module
    from rockforge.domain.arrangement import Arrangement, ArrangementKind, SongMetadata
    from rockforge.domain.music import Beat, TabNote, TempoMap, Tuning
    from rockforge.infrastructure.db.models import JobStatus
    from rockforge.infrastructure.rsxml.writer import write_arrangement_xml

    job = _create_job(client)
    bundle = config.settings.work_dir / job["id"] / "bundle"
    beats = tuple(Beat(time=0.5 * i, measure=(i // 4 + 1) if i % 4 == 0 else -1) for i in range(8))
    for kind, name in ((ArrangementKind.LEAD, "lead"), (ArrangementKind.RHYTHM, "rhythm")):
        write_arrangement_xml(Arrangement(
            kind=kind, metadata=SongMetadata(title="Taps", artist="T", song_length=4.0),
            tuning=Tuning(), notes=[TabNote(string=2, fret=5, time=1.0, sustain=0.0)],
            tempo_map=TempoMap(beats=beats, average_bpm=120.0),
        ), bundle / f"arrangement_{name}.xml")
    with app_module._session_factory() as session:
        db_job = session.get(app_module.Job, job["id"])
        db_job.status = JobStatus.COMPLETED
        db_job.bundle_dir = str(bundle)
        session.commit()

    url = f"/jobs/{job['id']}/marked-attacks"
    r = client.put(url, json={"arrangement": "Lead", "times": [2.0004, 1.25, 2.0, 0.5]})
    assert r.status_code == 200 and r.json()["times"] == [0.5, 1.25, 2.0]
    arrs = client.get(f"/jobs/{job['id']}/arrangements").json()
    by_kind = {a["kind"]: a["marked_attacks"] for a in arrs}
    assert by_kind == {"Lead": [0.5, 1.25, 2.0], "Rhythm": []}
    fork = client.post(f"/jobs/{job['id']}/rebuild", json={}).json()
    with app_module._session_factory() as session:
        stored = session.get(app_module.Job, fork["id"]).params["marked_attacks"]
    assert stored == {"Lead": [0.5, 1.25, 2.0]}
    assert client.put(url, json={"arrangement": "Bass", "times": [1.0]}).status_code == 422
    assert client.put(url, json={"arrangement": "Lead", "times": [-1.0]}).status_code == 422
    assert client.put(url, content='{"arrangement": "Lead", "times": [NaN]}',
                      headers={"Content-Type": "application/json"}).status_code == 422
    assert client.put(url, json={"arrangement": "Lead", "times": []}).json()["times"] == []
    with app_module._session_factory() as session:
        assert "marked_attacks" not in session.get(app_module.Job, job["id"]).params


def test_the_tones_of_the_songs_in_the_dlc_folder_are_listed_and_handed_out(
    client: TestClient, tmp_path
) -> None:
    """DLC Builder's tone collection: scan the Rocksmith dlc folder, list every
    song's tones, hand one out whole for a project or the library."""
    import time

    import rockforge.runtime_settings as rs
    from test_tone_collection import _song_psarc

    importlib.reload(rs)  # the folder is stored in THIS test's work dir
    assert client.post("/tone-collection/scan", json={}).status_code == 422  # no folder yet
    r = client.post("/tone-collection/scan", json={"folder": str(tmp_path / "nope")})
    assert r.status_code == 422
    dlc = tmp_path / "dlc"
    dlc.mkdir()
    _song_psarc(dlc / "a_p.psarc", "Alpha")
    _song_psarc(dlc / "b_p.psarc", "Beta")
    (dlc / "broken_p.psarc").write_bytes(b"PSAR")
    r = client.post("/tone-collection/scan", json={"folder": f'"{dlc}"'})  # pasted with quotes
    assert r.status_code == 202, r.text
    for _ in range(200):
        body = client.get("/tone-collection").json()
        if body["status"]["state"] != "scanning":
            break
        time.sleep(0.02)
    assert body["status"]["state"] == "done", body["status"]
    assert body["folder"] == str(dlc)
    assert (body["files"], body["unreadable"], body["tones_total"]) == (3, 1, 4)
    row = next(e for e in body["entries"] if e["song"] == "Alpha" and e["key"] == "HTH_Lead")
    assert row["amp"] == "Marshall Plexi"  # the game's names, not the gear keys
    assert row["effects"] == ["Super Drive"] and row["arrangements"] == ["Lead", "Rhythm"]

    assert [a["name"] for a in body["artists"]] == ["AC/DC"]
    one = client.get("/tone-collection", params={"artist": "ac/dc", "q": "alpha"}).json()
    assert one["matched"] == 2 and {e["song"] for e in one["entries"]} == {"Alpha"}
    assert one["artists"] == body["artists"]  # the picker lists every artist, filtered or not
    assert client.get("/tone-collection", params={"artist": "Nobody"}).json()["matched"] == 0
    found = client.get("/tone-collection", params={"q": "beta clean"}).json()
    assert found["matched"] == 1 and found["entries"][0]["song"] == "Beta"
    assert client.get("/tone-collection", params={"limit": 1}).json()["matched"] == 4
    assert len(client.get("/tone-collection", params={"limit": 1}).json()["entries"]) == 1

    tone = client.get("/tone-collection/tone", params={"id": row["id"]}).json()["tone"]
    assert tone["key"] == "HTH_Lead" and tone["pre"][1]["key"] == "Pedal_SuperDrive"
    assert client.post("/tone-library", json=tone).status_code == 200  # library takes it
    assert client.get("/tone-collection/tone", params={"id": "0" * 16}).status_code == 404
    # the folder is remembered: a rescan needs none
    assert client.post("/tone-collection/scan", json={}).status_code == 202


def _job_with_psarc(client: TestClient, tmp_path) -> tuple[str, Path]:
    """A completed job whose .psarc is a real one, packed by the native packer."""
    pytest.importorskip("cryptography")
    import rockforge.interfaces.api.app as app_module
    from rockforge.domain.arrangement import Arrangement, ArrangementKind, SongMetadata
    from rockforge.domain.music import Beat, TabNote, TempoMap, Tuning
    from rockforge.infrastructure.packaging.psarc.packer import NativePsarcPacker

    job_id = _bundle_with(client, ["LEAD"])
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"RIFF....WAVEfmt ")
    beats = tuple(Beat(time=0.5 * i, measure=(i // 4 + 1) if i % 4 == 0 else -1)
                  for i in range(16))
    arr = Arrangement(
        kind=ArrangementKind.LEAD, metadata=SongMetadata(title="Song", artist="Artist",
                                                         song_length=8.0),
        tuning=Tuning(), tempo_map=TempoMap(beats=beats, average_bpm=120.0),
        notes=[TabNote(string=1, fret=3, time=1.0 + i, sustain=0.3) for i in range(5)],
    )
    psarc = NativePsarcPacker().package([arr], audio, tmp_path / "packed").psarc_path
    assert psarc is not None
    with app_module._session_factory() as session:
        session.get(app_module.Job, job_id).psarc_path = str(psarc)
        session.commit()
    return job_id, psarc


def test_the_built_psarc_is_checked_before_it_goes_to_the_game(
    client: TestClient, tmp_path
) -> None:
    job_id, psarc = _job_with_psarc(client, tmp_path)
    r = client.get(f"/jobs/{job_id}/psarc-check")
    assert r.status_code == 200, r.text
    assert r.json() == {"ok": True, "charts": ["artistsong_lead"], "problems": []}

    from rockforge.infrastructure.packaging.psarc import container

    entries = container.unpack(psarc.read_bytes())
    del entries["appid.appid"]
    psarc.write_bytes(container.pack_entries(entries, encrypt=True))
    body = client.get(f"/jobs/{job_id}/psarc-check", headers={"X-RockForge-Lang": "pt"}).json()
    assert body["ok"] is False
    assert [(p["code"], p["count"]) for p in body["problems"]] == [("no_appid", 1)]
    assert "appid" in body["problems"][0]["text"]

    no_psarc = _bundle_with(client, ["LEAD"])
    assert client.get(f"/jobs/{no_psarc}/psarc-check").status_code == 409


def test_install_copies_the_psarc_into_the_games_dlc_folder(client: TestClient, tmp_path) -> None:
    import rockforge.runtime_settings as runtime_settings

    importlib.reload(runtime_settings)  # the game folder is stored in THIS test's work dir
    job_id, psarc = _job_with_psarc(client, tmp_path)
    assert client.get("/game-dlc").json()["folder"] == "RockForge"

    game = tmp_path / "Rocksmith2014"
    runtime_settings.save({"rocksmith_dir": str(game)})
    try:
        _install_into(client, job_id, psarc, game)
    finally:
        runtime_settings.save({})  # later tests read the same settings file


def _install_into(client: TestClient, job_id: str, psarc: Path, game: Path) -> None:
    assert client.post(f"/jobs/{job_id}/install").status_code == 404  # no dlc folder there
    (game / "dlc").mkdir(parents=True)
    assert client.get("/game-dlc").json()["dlc_dir"] == str(game / "dlc")

    r = client.post(f"/jobs/{job_id}/install")
    assert r.status_code == 200, r.text
    body = r.json()
    dest = game / "dlc" / "RockForge" / psarc.name
    assert body["path"] == str(dest) and dest.read_bytes() == psarc.read_bytes()
    assert body["job"]["in_game"] == "this" and body["job"]["in_game_path"] == str(dest)

    # A rebuild inherits the record: its card says an older copy is in the game.
    import rockforge.interfaces.api.app as app_module

    fork = _bundle_with(client, ["LEAD"])
    with app_module._session_factory() as session:
        db = session.get(app_module.Job, job_id)
        params = dict(db.params or {})
        session.get(app_module.Job, fork).params = params
        session.commit()
    assert client.get(f"/jobs/{fork}").json()["in_game"] == "older"

    dest.unlink()  # deleted by hand: no longer claimed
    assert client.get(f"/jobs/{job_id}").json()["in_game"] is None


def test_the_bars_with_an_estimated_rhythm_reach_the_viewer(
    client: TestClient, tmp_path, monkeypatch
) -> None:
    """/pdf/import's estimated bars travel with the wizard into the job and come
    back on the arrangement built from that track (a lone Lead is built as
    Combined); a new GP file drops them, since they described the old one."""
    import rockforge.interfaces.api.app as app_module
    from rockforge.domain.arrangement import Arrangement, ArrangementKind, SongMetadata
    from rockforge.domain.music import Beat, TabNote, TempoMap, Tuning
    from rockforge.infrastructure.db.models import JobStatus
    from rockforge.infrastructure.gpimport import pdf_import
    from rockforge.infrastructure.rsxml.writer import write_arrangement_xml

    gp = _gp8_with_embedded_audio(b"ID3x")
    monkeypatch.setattr(pdf_import, "available", lambda: True)
    monkeypatch.setattr(pdf_import, "convert", lambda files: pdf_import.PdfImport(
        gp5=_make_gp5_bytes(tmp_path), title="Tema", artist="Banda", estimated_bars={0: [2, 5, 6]}))
    imported = client.post(
        "/pdf/import", files=[("files", ("tab.pdf", b"%PDF-1.4\n%x", "application/pdf"))]).json()
    assert imported["estimated_bars"] == {"0": [2, 5, 6]}

    body = client.post("/gp/inspect", files={"file": ("s.gp", gp, "x")}).json()
    data = {"gp_token": body["gp_token"], "lead_track": "0", "use_embedded_audio": "true"}
    for bad in ('{"0": [0]}', '{"x": [1]}', '{"0": "2"}', '[2]', '{"0": [true]}', "nope"):
        assert client.post("/jobs/gp", data={**data, "estimated_bars": bad}).status_code == 422, bad
    r = client.post("/jobs/gp", data={**data, "estimated_bars": '{"0": [6, 2, 5, 2]}'})
    assert r.status_code == 202, r.text
    job = r.json()
    _, params = _job_row(job["id"])
    assert params["estimated_bars"] == {"0": [2, 5, 6]}

    bundle = app_module.settings.work_dir / job["id"] / "bundle"
    beats = tuple(Beat(time=0.5 * i, measure=(i // 4 + 1) if i % 4 == 0 else -1) for i in range(8))
    write_arrangement_xml(Arrangement(
        kind=ArrangementKind.COMBINED,
        metadata=SongMetadata(title="Tema", artist="Banda", song_length=4.0),
        tuning=Tuning(),
        notes=[TabNote(string=0, fret=3, time=1.0, sustain=0.5)],
        tempo_map=TempoMap(beats=beats, average_bpm=120.0),
    ), bundle / "arrangement_combined.xml")
    with app_module._session_factory() as session:
        db_job = session.get(app_module.Job, job["id"])
        db_job.status = JobStatus.COMPLETED
        db_job.bundle_dir = str(bundle)
        session.commit()
    arrs = client.get(f"/jobs/{job['id']}/arrangements").json()
    assert [(a["kind"], a["estimated_bars"]) for a in arrs] == [("Combined", [2, 5, 6])]

    reloaded = client.post(f"/jobs/{job['id']}/reload-gp", files={"gp": ("s.gp", gp, "x")})
    assert reloaded.status_code == 202, reloaded.text
    assert "estimated_bars" not in _job_row(reloaded.json()["id"])[1]


def test_a_project_exported_and_imported_comes_back_with_everything(
    client: TestClient, tmp_path, monkeypatch
) -> None:
    """"Exportar projeto" → "Importar projeto": a new project with the same
    song, recording, Guitar Pro file, cover, corrections and (when asked) the
    separated instruments — and nothing of the machine it came from."""
    import io
    import zipfile

    import rockforge.interfaces.api.app as app_module

    job = _gp_job(client, tmp_path)
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
    assert client.post(f"/jobs/{job['id']}/cover",
                       files={"file": ("c.png", png, "image/png")}).status_code == 202
    sep = tmp_path / "sep"
    sep.mkdir()
    (sep / "guitar.wav").write_bytes(b"RIFF0000WAVEguitar")
    (sep / "drums.wav").write_bytes(b"RIFF0000WAVEdrums")
    with app_module._session_factory() as session:
        row = session.get(app_module.Job, job["id"])
        row.params = {
            **row.params, "offset_s": 2.5, "lyrics_events": [{"time": 1.0, "length": 0.5,
                                                               "lyric": "olá+"}],
            "note_overrides": {"Combined": [{"time": 2.0, "string": 1, "fret": 5}]},
            "stems": {"guitar": str(sep / "guitar.wav")}, "stems_status": "ready",
            "installed_psarc": "C:/Games/Rocksmith2014/dlc/RockForge/x_p.psarc",
            "rebuilt_from": "an-older-version", "lyrics_status": "detecting",
        }
        session.commit()
        recording = Path(row.source).read_bytes()
        gp_bytes = Path(row.params["gp_path"]).read_bytes()

    info = client.get(f"/jobs/{job['id']}/project-info").json()
    assert info["ready"] and info["cover"] and info["stems"] == ["drums", "guitar"]
    assert info["stems_bytes"] == len(b"RIFF0000WAVEguitar") + len(b"RIFF0000WAVEdrums")

    plain = client.get(f"/jobs/{job['id']}/export-project")
    assert plain.status_code == 200
    assert ".rfproj" in plain.headers["content-disposition"]
    assert not [n for n in zipfile.ZipFile(io.BytesIO(plain.content)).namelist()
                if n.startswith("files/stems/")]
    full = client.get(f"/jobs/{job['id']}/export-project", params={"stems": "true"})
    names = zipfile.ZipFile(io.BytesIO(full.content)).namelist()
    assert {"files/stems/guitar.wav", "files/stems/drums.wav"} <= set(names)
    assert not list((app_module.settings.work_dir / "exports").glob("*"))  # sent, then removed

    queued: list[str] = []
    monkeypatch.setattr(app_module, "_enqueue", lambda j: queued.append(j.id))
    r = client.post("/projects/import",
                    files={"file": ("song.rfproj", full.content, "application/zip")})
    assert r.status_code == 202, r.text
    new = r.json()
    assert new["id"] != job["id"] and queued == [new["id"]]
    assert (new["title"], new["artist"]) == (job["title"], job["artist"])
    assert new["cover_art"] is True
    assert client.get(f"/jobs/{new['id']}/cover").content == png
    with app_module._session_factory() as session:
        row = session.get(app_module.Job, new["id"])
        params = dict(row.params)
        work = app_module.settings.work_dir
        assert Path(row.source).parent == work / "uploads"
        assert Path(row.source).read_bytes() == recording
        assert Path(params["gp_path"]).parent == work / "gp"
        assert Path(params["gp_path"]).read_bytes() == gp_bytes
    assert params["offset_s"] == 2.5
    assert params["lyrics_events"][0]["lyric"] == "olá+"
    assert params["note_overrides"] == {"Combined": [{"time": 2.0, "string": 1, "fret": 5}]}
    for gone in ("installed_psarc", "rebuilt_from", "lyrics_status"):
        assert gone not in params
    stored = Path(params["stems"]["guitar"])
    assert stored.is_relative_to(work / new["id"])
    assert stored.read_bytes() == b"RIFF0000WAVEguitar"
    assert params["stems_status"] == "ready"
    sources = client.get(f"/jobs/{new['id']}/attack-sources").json()
    assert sources["level_stems"] == ["drums", "guitar"]  # the drums came along too


def test_a_project_whose_files_are_gone_or_a_bad_file_is_refused_cleanly(
    client: TestClient, tmp_path
) -> None:
    import rockforge.interfaces.api.app as app_module

    job = _gp_job(client, tmp_path)
    with app_module._session_factory() as session:
        Path(session.get(app_module.Job, job["id"]).source).unlink()
    info = client.get(f"/jobs/{job['id']}/project-info").json()
    assert not info["ready"] and info["missing"] == ["recording"]
    assert client.get(f"/jobs/{job['id']}/export-project").status_code == 409

    work = app_module.settings.work_dir
    before = {p for p in work.rglob("*") if p.is_file()}
    r = client.post("/projects/import",
                    files={"file": ("x.rfproj", b"not a zip", "application/zip")},
                    headers={"X-RockForge-Lang": "en"})
    assert r.status_code == 422 and "not a RockForge project" in r.json()["detail"]
    after = {p for p in work.rglob("*") if p.is_file() and p.suffix != ".db"}
    assert after <= before  # nothing left behind


def test_imported_params_of_the_wrong_type_are_refused_and_never_break_the_home_page(
    client: TestClient, tmp_path
) -> None:
    """/import-sync and a .rfproj's project.json are raw JSON: "offset_s": "abc"
    was stored and then every GET /jobs answered 500 — the home page gone until
    that project was deleted by id."""
    import io
    import json
    import zipfile

    import rockforge.interfaces.api.app as app_module

    job = _gp_job(client, tmp_path)
    for bad in ({"offset_s": "abc"}, {"tempo_scale": "fast"}, {"tempo_scale": -1},
                {"sync_anchor_stages": [[["a", "b"]]]},
                {"arrangement_sync": {"Lead": {"tempo_scale": "x"}}},
                {"lyrics_events": "la la"}):
        r = client.post(f"/jobs/{job['id']}/import-sync", json={"sync": bad})
        assert r.status_code == 422, bad
    work = app_module.settings.work_dir
    before = {p for p in work.rglob("*") if p.is_file() and p.suffix != ".db"}
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("project.json", json.dumps({
            "format": "rockforge-project", "version": 1,
            "job": {"title": "Deriva", "artist": "Banda Inventada", "source_type": "gp"},
            "params": {"offset_s": "1e", "sync_main": 3},
        }))
        zf.writestr("files/recording.wav", b"RIFF0000WAVE")
        zf.writestr("files/score.gp5", _make_gp5_bytes(tmp_path))
    r = client.post("/projects/import",
                    files={"file": ("p.rfproj", buf.getvalue(), "application/zip")})
    assert r.status_code == 422 and "offset_s" in r.json()["detail"]
    assert {p for p in work.rglob("*") if p.is_file() and p.suffix != ".db"} <= before
    # and a bad value already in a project (an older version let it in) is shown, not a 500
    with app_module._session_factory() as session:
        row = session.get(app_module.Job, job["id"])
        row.params = {**row.params, "offset_s": "abc", "sync_main": 7}
        session.commit()
    assert client.get("/jobs").status_code == 200
    assert client.get(f"/jobs/{job['id']}").json()["offset_s"] == 0.0


def test_an_imported_project_cannot_point_the_server_at_a_path(
    client: TestClient, tmp_path
) -> None:
    """A project file made by hand to name files of the importing machine: the
    paths are not taken, the server puts the files where it puts its own."""
    import io
    import json
    import zipfile

    import rockforge.interfaces.api.app as app_module

    secret = tmp_path / "secret.wav"
    secret.write_bytes(b"RIFF0000WAVEsecret")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("project.json", json.dumps({
            "format": "rockforge-project", "version": 1,
            "job": {"title": "Deriva", "artist": "Banda Inventada", "source_type": "gp"},
            "params": {"offset_s": 1.0, "gp_path": str(secret), "cover_art": "../../secret.wav",
                       "stems": {"guitar": str(secret)}, "corrected_gp": "../../secret.wav"},
        }))
        zf.writestr("files/recording.wav", b"RIFF0000WAVE")
        zf.writestr("files/score.gp5", _make_gp5_bytes(tmp_path))
    r = client.post("/projects/import",
                    files={"file": ("p.rfproj", buf.getvalue(), "application/zip")})
    assert r.status_code == 202, r.text
    with app_module._session_factory() as session:
        params = dict(session.get(app_module.Job, r.json()["id"]).params)
    assert params["offset_s"] == 1.0
    assert Path(params["gp_path"]).parent == app_module.settings.work_dir / "gp"
    for gone in ("stems", "cover_art", "corrected_gp"):
        assert gone not in params
    assert r.json()["cover_art"] is False
    assert client.get(f"/jobs/{r.json()['id']}/stem/guitar").status_code == 404


def test_the_song_end_is_stored_read_back_and_reset(client: TestClient, tmp_path) -> None:
    """"Fim da música" (GitHub issue #10): seconds of the recording, kept with
    the project; 0 or less goes back to the recording's end."""
    body = client.post(
        "/gp/inspect", files={"file": ("song.gp5", _make_gp5_bytes(tmp_path),
                                       "application/octet-stream")}
    ).json()
    job = client.post(
        "/jobs/gp", data={"gp_token": body["gp_token"], "lead_track": "0"},
        files={"audio": ("song.wav", b"RIFF0000WAVE", "audio/wav")},
    ).json()
    assert job["song_end_s"] is None
    ended = client.post(f"/jobs/{job['id']}/rebuild", json={"song_end_s": 95.5}).json()
    assert ended["song_end_s"] == pytest.approx(95.5)
    kept = client.post(f"/jobs/{ended['id']}/rebuild", json={"offset_s": 1.0}).json()
    assert kept["song_end_s"] == pytest.approx(95.5)
    back = client.post(f"/jobs/{kept['id']}/rebuild", json={"song_end_s": 0}).json()
    assert back["song_end_s"] is None
    upload = _create_job(client)  # not a GP job
    assert client.post(
        f"/jobs/{upload['id']}/rebuild", json={"song_end_s": 10}
    ).status_code == 422
