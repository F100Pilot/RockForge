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


def test_whisperx_compute_type_settable_from_the_ui(client: TestClient) -> None:
    """The user can set/clear the WhisperX compute type from ⚙️ Definições
    instead of the ROCKFORGE_WHISPERX_COMPUTE_TYPE env var."""
    assert client.get("/settings").json()["whisperx_compute_type"] == ""
    r = client.post("/settings", json={"whisperx_compute_type": "int8_float16"})
    assert r.status_code == 200
    assert r.json()["whisperx_compute_type"] == "int8_float16"
    assert client.get("/settings").json()["whisperx_compute_type"] == "int8_float16"
    # Empty string clears it back to automatic.
    cleared = client.post("/settings", json={"whisperx_compute_type": ""})
    assert cleared.json()["whisperx_compute_type"] == ""


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


def test_whisperx_compute_type_override_round_trips(client: TestClient) -> None:
    """The GPU escalation persists a working compute type to runtime_settings;
    the accessor returns it over the env default, and empty clears it."""
    import rockforge.runtime_settings as rs

    assert rs.whisperx_compute_type() == ""  # unset → pick by device
    rs.save({**rs.load(), "whisperx_compute_type": "int8_float16"})
    assert rs.whisperx_compute_type() == "int8_float16"
    rs.save({**rs.load(), "whisperx_compute_type": ""})  # empty clears the override
    assert rs.whisperx_compute_type() == ""


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


def test_concurrent_writers_never_publish_each_others_content(tmp_path, monkeypatch) -> None:
    """The temp file used to be a fixed "<file>.tmp", and the API and worker both
    write here: with a shared name two writers interleave — A creates it, B
    overwrites it, A renames it into place and publishes B's content. A unique
    temp name per write closes that; os.replace still makes the swap atomic."""
    import importlib
    import threading

    monkeypatch.setenv("ROCKFORGE_WORK_DIR", str(tmp_path))
    import rockforge.config as config
    importlib.reload(config)
    import rockforge.runtime_settings as rs
    importlib.reload(rs)

    a, b = "/repo-" + "a" * 40, "/repo-" + "b" * 40
    seen: list[str | None] = []

    def _writer(value: str) -> None:
        for _ in range(40):
            rs.save({"banquet_repo": value})
            seen.append(rs.load().get("banquet_repo"))

    threads = [threading.Thread(target=_writer, args=(v,)) for v in (a, b)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert seen, "the writers ran"
    # Every read is one writer's COMPLETE value — never a truncation or a blend.
    assert set(seen) <= {a, b}, [v for v in seen if v not in (a, b)]
    assert not list(tmp_path.glob("*.tmp")), "no temp file left behind"


def test_ml_python_round_trips_and_reaches_the_resolver(client: TestClient, tmp_path) -> None:
    """The setting is the standalone build's ONLY route to stem separation,
    tone/lyric detection and "Corrigir daqui": every one of those runs as a
    subprocess, so the `.exe` does not need the packages — it needs an
    interpreter that has them. Saving it has to actually change what the
    resolver hands those subprocesses, not merely echo back in the JSON.
    """
    from rockforge.infrastructure import ml_python

    assert client.get("/settings").json()["ml_python"] == ""

    fake = tmp_path / "py311" / "python"
    fake.parent.mkdir(parents=True)
    fake.write_text("")
    body = client.post("/settings", json={"ml_python": str(fake)}).json()
    assert body["ml_python"] == str(fake)
    assert ml_python.resolve() == str(fake)
    assert client.get("/settings").json()["ml_python"] == str(fake)

    # Cleared, it falls back to this process — which is what a Python install
    # wants, and what the .exe must NOT silently get (sys.executable is the
    # .exe there, so `resolve()` returns None instead; see test_ml_python.py).
    client.post("/settings", json={"ml_python": ""})
    assert client.get("/settings").json()["ml_python"] == ""


def test_ml_python_readiness_is_reported_per_extra(
    client: TestClient, tmp_path, monkeypatch
) -> None:
    """The likeliest mistakes are a path that is not a Python and a Python
    missing one of the two extras, and they need different fixes — so the UI
    gets a flag per extra rather than one "ready" boolean.

    The flags must come from probing THAT interpreter, not from what this
    process can import: in the .exe they are different Pythons, and our own
    answer is always "nothing".
    """
    from rockforge.infrastructure import ml_python

    fake = tmp_path / "python311"
    fake.write_text("")
    client.post("/settings", json={"ml_python": str(fake)})
    monkeypatch.setattr(
        ml_python, "probe",
        lambda *_a: {
            "python": True, "demucs": True, "librosa": True,
            "whisperx": False, "torch": True,
        },
    )
    info = client.get("/settings").json()["ml_python_info"]
    assert info["path"] == str(fake)
    assert info["python_ok"] is True
    assert info["ml_ok"] is True      # stems, tone, "Corrigir daqui"
    assert info["lyrics_ok"] is False  # but no automatic lyrics
