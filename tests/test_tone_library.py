"""Cross-project tone library (work_dir/tone_library.json) via the API.

Same per-test SQLite/work-dir fixture as the settings tests: a saved tone must
carry a valid amp+cabinet, is upserted by key, and survives a fresh read.
"""

from __future__ import annotations

import importlib
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch) -> Iterator[TestClient]:
    monkeypatch.setenv("ROCKFORGE_DATABASE_URL", f"sqlite:///{tmp_path}/test.db")
    monkeypatch.setenv("ROCKFORGE_WORK_DIR", str(tmp_path / "work"))
    import rockforge.config as config
    importlib.reload(config)
    import rockforge.tone_library as tl
    importlib.reload(tl)
    import rockforge.interfaces.api.app as app_module
    importlib.reload(app_module)
    with TestClient(app_module.app) as c:
        yield c


def _tone(key: str) -> dict[str, Any]:
    # amp+cabinet are the minimum tone_from_dict accepts; use real catalogue keys.
    return {
        "key": key,
        "name": key,
        "volume": -12.0,
        "descriptors": ["$[35723]CLEAN"],
        "amp": {"key": "Amp_AT120", "knobs": {}},
        "cabinet": {"key": "Cab_AT0112C_57_Cone", "knobs": {}},
        "pre": [],
        "post": [],
        "racks": [],
    }


def test_library_starts_empty(client: TestClient) -> None:
    assert client.get("/tone-library").json() == {"tones": []}


def test_save_and_read_back(client: TestClient) -> None:
    r = client.post("/tone-library", json=_tone("MyClean"))
    assert r.status_code == 200
    tones = r.json()["tones"]
    assert [t["key"] for t in tones] == ["MyClean"]
    # a fresh GET re-reads the JSON file
    assert client.get("/tone-library").json()["tones"][0]["key"] == "MyClean"


def test_save_same_key_overwrites(client: TestClient) -> None:
    client.post("/tone-library", json=_tone("Lead"))
    updated = _tone("Lead")
    updated["volume"] = -3.0
    tones = client.post("/tone-library", json=updated).json()["tones"]
    assert len(tones) == 1
    assert tones[0]["volume"] == -3.0


def test_delete(client: TestClient) -> None:
    client.post("/tone-library", json=_tone("A"))
    client.post("/tone-library", json=_tone("B"))
    tones = client.request("DELETE", "/tone-library/A").json()["tones"]
    assert [t["key"] for t in tones] == ["B"]


def test_tone_without_amp_rejected(client: TestClient) -> None:
    bad = _tone("Broken")
    del bad["amp"]
    assert client.post("/tone-library", json=bad).status_code == 422
