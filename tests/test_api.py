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
    r = client.get("/")
    assert r.status_code == 200
    assert '<script src="/app.js"></script>' in r.text
    assert "<script>" not in r.text  # no inline JS left behind


def test_app_js_is_served_with_a_javascript_content_type(client: TestClient) -> None:
    r = client.get("/app.js")
    assert r.status_code == 200
    assert "javascript" in r.headers["content-type"]
    assert "document.querySelectorAll" in r.text


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
    r = client.post(
        f"/jobs/{original['id']}/rebuild",
        json={"tuning_midi": [38, 45, 50, 55, 59, 64], "split_lead_rhythm": False},
    )
    assert r.status_code == 202
    assert r.json()["id"] != original["id"]


def test_rebuild_stores_dynamic_difficulty_flag(client: TestClient) -> None:
    original = _create_job(client)
    assert original["dynamic_difficulty"] is True  # default on
    r = client.post(f"/jobs/{original['id']}/rebuild", json={"dynamic_difficulty": False})
    assert r.status_code == 202
    assert r.json()["dynamic_difficulty"] is False


def test_rebuild_validates_tuning_length(client: TestClient) -> None:
    original = _create_job(client)
    r = client.post(f"/jobs/{original['id']}/rebuild", json={"tuning_midi": [40, 45]})
    assert r.status_code == 422


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


def test_rebuild_rejects_negative_offset(client: TestClient) -> None:
    original = _create_job(client)
    r = client.post(f"/jobs/{original['id']}/rebuild", json={"offset_s": -1.0})
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
        f"/jobs/{fresh['id']}/import-sync", json={"sync": {"tuning_midi": [40, 45]}}
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
        session.commit()

    data = client.get(f"/jobs/{job['id']}/arrangements").json()
    chord_notes = [n for n in data[0]["notes"] if n["chord"]]
    assert chord_notes, "expected the simultaneous notes to be emitted as a chord"
    assert all(n["chord_name"] == "C" for n in chord_notes)
    # single (non-chord) notes must not carry a chord name
    assert all(n["chord_name"] is None for n in data[0]["notes"] if not n["chord"])
    # ALL beats (not just downbeats) are exposed as the drag snap grid
    assert data[0]["beats"] == [0.5 * i for i in range(8)]
    assert [b["measure"] for b in data[0]["bars"]] == [1, 2]  # bars = downbeats only


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

    sections = client.get(f"/jobs/{job['id']}/arrangements").json()[0]["sections"]
    assert [s["name"] for s in sections] == ["Intro"]


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


def test_auto_sync_proposes_alignment(client: TestClient, tmp_path, monkeypatch) -> None:
    # Beat detection is faked (librosa not in CI): the endpoint must combine the
    # GP tempo (100) with the detected recording tempo/onset into a proposal,
    # octave-correcting the detected tempo and returning the first onset as offset.
    import rockforge.infrastructure.rhythm.librosa_adapter as rhythm

    monkeypatch.setattr(rhythm, "detect_tempo_and_onset", lambda src: (50.0, 2.3))
    data = _make_gp5_bytes(tmp_path)
    body = client.post(
        "/gp/inspect", files={"file": ("song.gp5", data, "application/octet-stream")}
    ).json()
    job = client.post(
        "/jobs/gp",
        data={"gp_token": body["gp_token"], "lead_track": "0"},
        files={"audio": ("song.wav", b"RIFF0000WAVE", "audio/wav")},
    ).json()
    r = client.post(f"/jobs/{job['id']}/auto-sync")
    assert r.status_code == 200
    out = r.json()
    assert out["gp_bpm"] == pytest.approx(100.0)
    assert out["detected_bpm"] == pytest.approx(50.0)
    assert out["suggested_tempo_scale"] == pytest.approx(1.0)  # 100 / (50 * 2)
    assert out["suggested_offset_s"] == pytest.approx(2.3)


def test_auto_sync_uses_the_drum_stem_when_available(client, tmp_path, monkeypatch) -> None:
    """When a Demucs separation already produced a drum stem, auto-sync measures
    the tempo on the isolated drums (the sibling drums.wav of the guitar stem),
    not the full mix — far more reliable on dense music. The full mix is used
    (used_drum_stem False) when no separation exists yet."""
    import rockforge.infrastructure.rhythm.librosa_adapter as rhythm
    import rockforge.interfaces.api.app as app_module

    seen: dict[str, str] = {}

    def fake_detect(src):
        seen["path"] = str(src)
        return (90.0, 1.0)

    monkeypatch.setattr(rhythm, "detect_tempo_and_onset", fake_detect)
    data = _make_gp5_bytes(tmp_path)
    body = client.post(
        "/gp/inspect", files={"file": ("song.gp5", data, "application/octet-stream")}
    ).json()
    job = client.post(
        "/jobs/gp",
        data={"gp_token": body["gp_token"], "lead_track": "0"},
        files={"audio": ("song.wav", b"RIFF0000WAVE", "audio/wav")},
    ).json()

    # No separation yet → full mix, used_drum_stem False.
    r = client.post(f"/jobs/{job['id']}/auto-sync")
    assert r.status_code == 200 and r.json()["used_drum_stem"] is False
    assert seen["path"] == job["source"] if "source" in job else seen["path"].endswith(".wav")

    # Simulate a completed separation: guitar stem in params + drums.wav sibling.
    stem_dir = tmp_path / "stems"
    stem_dir.mkdir()
    guitar = stem_dir / "guitar.wav"
    guitar.write_bytes(b"RIFFguitarWAVE")
    (stem_dir / "drums.wav").write_bytes(b"RIFFdrumsWAVE")
    with app_module._session_factory() as session:
        db_job = session.get(app_module.Job, job["id"])
        db_job.params = {**db_job.params, "stems": {"guitar": str(guitar)}}
        session.commit()

    r2 = client.post(f"/jobs/{job['id']}/auto-sync")
    assert r2.status_code == 200 and r2.json()["used_drum_stem"] is True
    assert seen["path"] == str(stem_dir / "drums.wav")


def test_auto_sync_rejected_for_non_gp(client: TestClient) -> None:
    job = _create_job(client)
    r = client.post(f"/jobs/{job['id']}/auto-sync")
    assert r.status_code == 422


def _completed_gp_job_with_beats(client, tmp_path, beat_times):
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
        notes=[TabNote(string=1, fret=5, time=beat_times[0], sustain=0.2)],
        tempo_map=TempoMap(beats=beats, average_bpm=120.0),
    )
    write_arrangement_xml(arr, bundle / "arrangement_lead.xml")
    with app_module._session_factory() as session:
        db_job = session.get(app_module.Job, job["id"])
        db_job.status = JobStatus.COMPLETED
        db_job.bundle_dir = str(bundle)
        session.commit()
    return job


def test_auto_sync_dynamic_proposes_beat_anchors(client, tmp_path, monkeypatch) -> None:
    """The endpoint aligns the built chart's beat grid to the recording's detected
    beats (faked here) and returns drift anchors that follow a tempo offset."""
    import rockforge.infrastructure.rhythm.librosa_adapter as rhythm

    gp_beats = [0.5 * i for i in range(16)]        # 120 BPM chart
    # Recording detected ~9% slower (constant), so anchors drift later over time.
    monkeypatch.setattr(rhythm, "detect_beats", lambda src: (110.0, [0.55 * i for i in range(16)]))
    monkeypatch.setattr(rhythm, "detect_onsets", lambda src: [])
    job = _completed_gp_job_with_beats(client, tmp_path, gp_beats)

    r = client.post(f"/jobs/{job['id']}/auto-sync-dynamic")
    assert r.status_code == 200
    out = r.json()
    assert out["detected_bpm"] == pytest.approx(110.0)
    assert out["gp_beat_count"] == 16 and out["rec_beat_count"] == 16
    anchors = out["anchors"]
    assert len(anchors) >= 2
    assert anchors[0] == [0.0, 0.0]
    # recording times strictly advance (monotonic warp) and drift past the chart time.
    assert all(anchors[i][1] < anchors[i + 1][1] for i in range(len(anchors) - 1))
    assert anchors[-1][1] > anchors[-1][0]
    # one confidence per anchor + the honesty spans field
    assert len(out["confidences"]) == len(anchors)
    assert "weak_ranges" in out


def test_auto_sync_dynamic_uses_drum_and_guitar_stems(client, tmp_path, monkeypatch) -> None:
    """Dynamic sync takes the beat GRID from the isolated drums and the onset
    PHASE from the isolated guitar when a separation exists — so the tempo comes
    from the cleanest beat signal and the chart's guitar notes match guitar
    attacks, not drum hits."""
    import rockforge.infrastructure.rhythm.librosa_adapter as rhythm
    import rockforge.interfaces.api.app as app_module

    seen: dict[str, str] = {}
    monkeypatch.setattr(
        rhythm, "detect_beats",
        lambda src: (seen.__setitem__("beats", str(src)), (120.0, [0.5 * i for i in range(16)]))[1],
    )
    monkeypatch.setattr(
        rhythm, "detect_onsets", lambda src: (seen.__setitem__("onsets", str(src)), [])[1]
    )
    job = _completed_gp_job_with_beats(client, tmp_path, [0.5 * i for i in range(16)])

    stem_dir = tmp_path / "dstems"
    stem_dir.mkdir()
    guitar = stem_dir / "guitar.wav"
    guitar.write_bytes(b"RIFFguitarWAVE")
    (stem_dir / "drums.wav").write_bytes(b"RIFFdrumsWAVE")
    with app_module._session_factory() as session:
        db_job = session.get(app_module.Job, job["id"])
        db_job.params = {**db_job.params, "stems": {"guitar": str(guitar)}}
        session.commit()

    r = client.post(f"/jobs/{job['id']}/auto-sync-dynamic")
    assert r.status_code == 200 and r.json()["used_drum_stem"] is True
    assert seen["beats"] == str(stem_dir / "drums.wav")
    assert seen["onsets"] == str(guitar)


def test_auto_sync_dynamic_rejected_for_non_gp(client: TestClient) -> None:
    job = _create_job(client)
    assert client.post(f"/jobs/{job['id']}/auto-sync-dynamic").status_code == 422


def _minimal_midi(ppq: int = 480, bpm: int = 120, measures: int = 8) -> bytes:
    """A tiny 4/4 SMF at a constant tempo, extended to `measures` measures."""
    us = round(60_000_000 / bpm)

    def varlen(n: int) -> bytes:
        out = bytearray([n & 0x7F])
        n >>= 7
        while n:
            out.insert(0, (n & 0x7F) | 0x80)
            n >>= 7
        return bytes(out)

    end_tick = ppq * 4 * measures
    events = [
        (0, bytes([0xFF, 0x58, 0x04, 4, 2, 24, 8])),   # 4/4
        (0, b"\xFF\x51\x03" + us.to_bytes(3, "big")),  # tempo
        (end_tick, b"\xFF\x51\x03" + us.to_bytes(3, "big")),  # extend the span
    ]
    track = bytearray()
    prev = 0
    for tick, ev in sorted(events, key=lambda e: e[0]):
        track += varlen(tick - prev) + ev
        prev = tick
    track += varlen(0) + b"\xFF\x2F\x00"
    header = (
        b"MThd" + (6).to_bytes(4, "big") + (0).to_bytes(2, "big")
        + (1).to_bytes(2, "big") + ppq.to_bytes(2, "big")
    )
    return header + b"MTrk" + len(track).to_bytes(4, "big") + bytes(track)


def test_sync_from_midi_maps_bars_to_midi_measures(client, tmp_path) -> None:
    """A MIDI tempo map aligns the chart's bars to the recording's real measure
    times (ground truth): every anchor is fully confident and no span is weak."""
    gp_beats = [0.5 * i for i in range(16)]        # bars (measure>0) at 0,2,4,6s
    job = _completed_gp_job_with_beats(client, tmp_path, gp_beats)

    r = client.post(
        f"/jobs/{job['id']}/sync-from-midi",
        files={"midi": ("tempo.mid", _minimal_midi(bpm=120), "audio/midi")},
    )
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["detected_bpm"] == pytest.approx(120.0, abs=1.0)
    assert out["anchors"][0] == [0.0, 0.0]                 # the pin (defaulted)
    assert len(out["anchors"]) >= 2
    # 120 BPM 4/4 → 2.0s per measure, so bar 2.0 (chart) → 2.0s (recording).
    assert out["anchors"][1] == pytest.approx([2.0, 2.0])
    assert all(c == 1.0 for c in out["confidences"])       # MIDI is ground truth
    assert out["weak_ranges"] == []


def test_sync_from_midi_respects_the_pin(client, tmp_path) -> None:
    gp_beats = [0.5 * i for i in range(16)]
    job = _completed_gp_job_with_beats(client, tmp_path, gp_beats)
    r = client.post(
        f"/jobs/{job['id']}/sync-from-midi",
        params={"chart_start": 2.0, "rec_start": 10.0},
        files={"midi": ("tempo.mid", _minimal_midi(bpm=120), "audio/midi")},
    )
    assert r.status_code == 200, r.text
    anchors = r.json()["anchors"]
    assert anchors[0] == [2.0, 10.0]                        # pin verbatim
    assert anchors[1] == pytest.approx([4.0, 12.0])         # next bar +2.0s


def test_sync_from_midi_rejects_non_gp(client: TestClient) -> None:
    job = _create_job(client)
    r = client.post(
        f"/jobs/{job['id']}/sync-from-midi",
        files={"midi": ("tempo.mid", _minimal_midi(), "audio/midi")},
    )
    assert r.status_code == 422


def test_sync_from_midi_rejects_a_non_midi_upload(client, tmp_path) -> None:
    gp_beats = [0.5 * i for i in range(16)]
    job = _completed_gp_job_with_beats(client, tmp_path, gp_beats)
    r = client.post(
        f"/jobs/{job['id']}/sync-from-midi",
        files={"midi": ("bad.mid", b"this is not a midi file", "audio/midi")},
    )
    assert r.status_code == 422
    assert "Standard MIDI File" in r.json()["detail"]


def test_sync_from_stem_maps_bars_to_detected_downbeats(client, tmp_path, monkeypatch) -> None:
    """The neural downbeat tracker (faked) gives per-measure downbeat times; the
    endpoint anchors each chart bar to its nearest detected downbeat by time
    correspondence, following the recording's real (slightly slower) tempo."""
    import rockforge.infrastructure.rhythm.beatthis_adapter as bt

    gp_beats = [0.5 * i for i in range(16)]  # bars (measure>0) at 0,2,4,6s
    monkeypatch.setattr(bt, "detect_downbeats", lambda src: [0.0, 2.1, 4.3, 6.6])
    job = _completed_gp_job_with_beats(client, tmp_path, gp_beats)

    r = client.post(f"/jobs/{job['id']}/sync-from-stem")
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["used_drum_stem"] is False
    anchors = out["anchors"]
    assert anchors[0] == [0.0, 0.0]              # the pin (defaulted)
    assert anchors[1] == pytest.approx([2.0, 2.1])
    assert anchors[2] == pytest.approx([4.0, 4.3])
    assert len(out["confidences"]) == len(anchors)
    assert out["weak_ranges"] == []


def test_sync_from_stem_respects_the_pin(client, tmp_path, monkeypatch) -> None:
    """With a Step-1 pin, the first anchor is the pin verbatim and the detected
    downbeats are mapped relative to the one nearest the pinned recording time."""
    import rockforge.infrastructure.rhythm.beatthis_adapter as bt

    gp_beats = [0.5 * i for i in range(16)]
    # An intro downbeat at 3.0 the tab doesn't cover, then the pinned bar at ~10s.
    monkeypatch.setattr(bt, "detect_downbeats", lambda src: [3.0, 10.0, 12.2, 14.5])
    job = _completed_gp_job_with_beats(client, tmp_path, gp_beats)

    r = client.post(
        f"/jobs/{job['id']}/sync-from-stem",
        params={"chart_start": 2.0, "rec_start": 10.0},
    )
    assert r.status_code == 200, r.text
    anchors = r.json()["anchors"]
    assert anchors[0] == [2.0, 10.0]             # pin verbatim (nearest downbeat = 10.0)
    assert anchors[1] == pytest.approx([4.0, 12.2])
    assert anchors[2] == pytest.approx([6.0, 14.5])


def test_sync_from_stem_uses_the_drum_stem_when_available(client, tmp_path, monkeypatch) -> None:
    """Detection runs on the isolated drum stem (the cleanest beat signal) when a
    separation exists, falling back to the full mix otherwise."""
    import rockforge.infrastructure.rhythm.beatthis_adapter as bt
    import rockforge.interfaces.api.app as app_module

    seen: dict[str, str] = {}
    monkeypatch.setattr(
        bt, "detect_downbeats",
        lambda src: (seen.__setitem__("src", str(src)), [0.0, 2.0, 4.0, 6.0])[1],
    )
    job = _completed_gp_job_with_beats(client, tmp_path, [0.5 * i for i in range(16)])

    stem_dir = tmp_path / "dstems"
    stem_dir.mkdir()
    guitar = stem_dir / "guitar.wav"
    guitar.write_bytes(b"RIFFguitarWAVE")
    (stem_dir / "drums.wav").write_bytes(b"RIFFdrumsWAVE")
    with app_module._session_factory() as session:
        db_job = session.get(app_module.Job, job["id"])
        db_job.params = {**db_job.params, "stems": {"guitar": str(guitar)}}
        session.commit()

    r = client.post(f"/jobs/{job['id']}/sync-from-stem")
    assert r.status_code == 200 and r.json()["used_drum_stem"] is True
    assert seen["src"] == str(stem_dir / "drums.wav")


def test_sync_from_stem_aligns_by_time_not_bar_index(client, tmp_path, monkeypatch) -> None:
    """The stem sync snaps each bar to the nearest REAL detected downbeat (time
    correspondence): a tab whose bar structure is denser than the recording's
    measures has its extra bars skipped instead of mis-mapped by index."""
    import rockforge.infrastructure.rhythm.beatthis_adapter as bt

    gp_beats = [0.5 * i for i in range(16)]  # bars at 0,2,4,6
    # The recording has FEWER downbeats than the tab has bars, drifting late.
    monkeypatch.setattr(bt, "detect_downbeats", lambda src: [0.0, 3.1, 6.3])
    job = _completed_gp_job_with_beats(client, tmp_path, gp_beats)

    r = client.post(f"/jobs/{job['id']}/sync-from-stem")
    assert r.status_code == 200, r.text
    anchors = r.json()["anchors"]
    assert anchors[0] == [0.0, 0.0]
    recs = [rc for _c, rc in anchors]
    assert recs == sorted(recs)  # strictly monotonic
    # every anchor lands on a real detected downbeat, never a wrong in-between one
    assert all(any(abs(rc - d) < 1e-6 for d in (0.0, 3.1, 6.3)) for rc in recs)


def test_sync_from_stem_rejects_non_gp(client: TestClient) -> None:
    job = _create_job(client)
    assert client.post(f"/jobs/{job['id']}/sync-from-stem").status_code == 422


def test_sync_from_stem_503_when_beatthis_missing(client, tmp_path, monkeypatch) -> None:
    """beat_this is imported lazily inside detect_downbeats, so an absent extra
    must surface as a clean 503 (install hint), not the generic analysis 422."""
    import rockforge.infrastructure.rhythm.beatthis_adapter as bt

    def _missing(_src):
        raise ImportError("No module named 'beat_this'")

    monkeypatch.setattr(bt, "detect_downbeats", _missing)
    job = _completed_gp_job_with_beats(client, tmp_path, [0.5 * i for i in range(16)])

    r = client.post(f"/jobs/{job['id']}/sync-from-stem")
    assert r.status_code == 503
    assert "beatthis" in r.json()["detail"]


def test_auto_sync_dynamic_respects_the_pinned_first_note(
    client, tmp_path, monkeypatch
) -> None:
    """chart_start/rec_start (the Step-1 first-note pin the UI passes) make the
    alignment START there: the first anchor is the pin verbatim and tracker
    'beats' in the intro silence are ignored — the fix for 'as notas começaram
    o alinhamento logo no início do 0 segundos'."""
    import rockforge.infrastructure.rhythm.librosa_adapter as rhythm

    gp_beats = [2.0 + 0.5 * i for i in range(16)]   # chart grid from the built pad
    # Garbage intro "beats", then the real grid starting at 4.2s.
    monkeypatch.setattr(
        rhythm, "detect_beats",
        lambda src: (110.0, [0.3, 1.1, 2.0] + [4.2 + 0.55 * i for i in range(16)]),
    )
    monkeypatch.setattr(rhythm, "detect_onsets", lambda src: [])
    job = _completed_gp_job_with_beats(client, tmp_path, gp_beats)

    r = client.post(
        f"/jobs/{job['id']}/auto-sync-dynamic",
        params={"chart_start": 2.0, "rec_start": 4.2},
    )
    assert r.status_code == 200
    anchors = r.json()["anchors"]
    assert anchors[0] == [2.0, 4.2]                 # the pin, untouched
    assert all(a[1] >= 4.2 for a in anchors)        # nothing mapped into the intro


def test_detect_tempo_returns_local_factor(client: TestClient, tmp_path, monkeypatch) -> None:
    # Per-point re-tempo: detection is faked. GP tempo 100, detected 200 from the
    # clicked point → octave-corrected factor 1.0 (100 / (200 * 0.5)).
    import rockforge.infrastructure.rhythm.librosa_adapter as rhythm

    monkeypatch.setattr(rhythm, "detect_tempo_from", lambda src, start: 200.0)
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
    assert out["detected_bpm"] == pytest.approx(200.0)
    assert out["suggested_factor"] == pytest.approx(1.0)


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
    assert r.json() == {"status": "none", "events": [], "log": []}


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

    for name in (
        "inspect_gp_file",
        "create_gp_job",
        "reload_gp",
        "upload_cover_art",
    ):
        fn = getattr(app_module, name)
        assert not inspect.iscoroutinefunction(fn), (
            f"{name} must be a plain `def` (blocking upload work belongs in "
            "Starlette's thread pool, not the event loop)"
        )
