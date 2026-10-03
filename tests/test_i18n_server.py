"""The text the SERVER writes follows the user's language (``rockforge.i18n``).

Portuguese is the default, so every other test keeps reading the Portuguese
originals; these switch to English and check that each family of messages —
diagnostics, Songsterr, YouTube, the lookups, the exports, the desktop window
— really has its English, and that the API picks the language from the
``X-RockForge-Lang`` header and remembers it with ``PUT /ui-language``.
"""

from __future__ import annotations

import importlib
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from rockforge import i18n


@pytest.fixture()
def english() -> Iterator[None]:
    token = i18n.use("en")
    try:
        yield
    finally:
        i18n.reset(token)


def test_portuguese_is_the_default_and_english_is_there_when_asked() -> None:
    assert i18n.tr("não encontrado", "not found") == "não encontrado"
    token = i18n.use("en")
    try:
        assert i18n.tr("não encontrado", "not found") == "not found"
    finally:
        i18n.reset(token)
    assert i18n.tr("não encontrado", "not found") == "não encontrado"


def test_a_diagnostics_row_is_in_english(
    english: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from rockforge import config
    from rockforge.infrastructure import diagnostics, tone_collection

    monkeypatch.setattr(config.settings, "work_dir", tmp_path)
    monkeypatch.setattr(tone_collection, "rocksmith_game_folders", lambda: [])
    row = diagnostics._loader_patch()
    assert row.name == "Rocksmith CDLC patch (D3DX9_42.dll)"
    assert "was not found on this computer" in row.detail
    assert "never shows up" in row.without_it
    assert diagnostics._installed(False) == "missing"


def test_a_songsterr_refusal_is_in_english(
    english: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    import requests

    from rockforge.infrastructure import songsterr

    class Answer:
        status_code = 403

        def json(self) -> Any:
            return {"code": "ERR_UNPUBLISHED", "reason": "unpublished"}

    monkeypatch.setattr(requests, "get", lambda *_a, **_k: Answer())
    with pytest.raises(songsterr.SongsterrError, match="not published") as info:
        songsterr._http_get_json("https://www.songsterr.com/api/meta/1")
    assert info.value.status == 403
    with pytest.raises(songsterr.SongsterrError, match="could not read the Songsterr link"):
        songsterr.parse_song_id("nothing here")


def test_a_youtube_failure_is_in_english(english: None, tmp_path: Path) -> None:
    from rockforge.infrastructure import youtube_audio as ya

    exc = ya.classify_failure("ERROR: No supported JavaScript runtime could be found", 1)
    assert "has no JavaScript runtime" in str(exc)
    with pytest.raises(ya.YtDlpMissingError, match="yt-dlp is not installed"):
        ya.download_audio("dQw4w9WgXcQ", tmp_path, command=None, run=None)  # type: ignore[arg-type]


def test_the_lookups_and_the_network_errors_are_in_english(english: None) -> None:
    from rockforge.infrastructure._https import network_error_message
    from rockforge.infrastructure.album_lookup import AlbumLookupError, search_albums
    from rockforge.infrastructure.lyrics_lookup import LyricsLookupError, search_lyrics

    with pytest.raises(AlbumLookupError, match="I need the title and the band"):
        search_albums("", "")
    with pytest.raises(LyricsLookupError, match="I need the title and the band"):
        search_lyrics("", "")
    assert network_error_message(OSError("down"), "LRCLIB") == "could not reach LRCLIB (down)"


def test_the_ml_interpreter_messages_are_in_english(
    english: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from rockforge.infrastructure import ml_python

    monkeypatch.setattr(ml_python, "frozen", lambda: False)
    assert ml_python.missing_message("Audio separation").startswith(
        "Audio separation needs the ML extras"
    )
    monkeypatch.setattr(ml_python, "frozen", lambda: True)
    assert "needs Python 3.11" in ml_python.missing_message("Audio separation")


def test_the_gp_writers_warn_in_english(english: None, tmp_path: Path) -> None:
    from rockforge.domain.arrangement import Arrangement, ArrangementKind, SongMetadata
    from rockforge.domain.errors import IngestionError
    from rockforge.domain.music import Beat, TabNote, TempoMap, Tuning
    from rockforge.infrastructure.gpexport.arrangement_writer import write_arrangement_gp5
    from rockforge.infrastructure.gpimport.songsterr_gp import write_songsterr_gp5

    beats = tuple(
        Beat(time=i * 0.5, measure=(i // 4) + 1 if i % 4 == 0 else -1) for i in range(17)
    )
    arr = Arrangement(
        kind=ArrangementKind.LEAD,
        metadata=SongMetadata(title="Song", artist="Band", album="Album", song_length=8.0),
        tuning=Tuning(),
        tempo_map=TempoMap(beats=beats, average_bpm=120.0),
        notes=[TabNote(string=0, fret=3, time=0.0, sustain=0.2)],
        sections=[],
    )
    report = write_arrangement_gp5(arr, tmp_path / "out.gp5")
    assert any("holds only this track" in w for w in report.warnings)

    drums = {"instrument": "Drums", "measures": [{}]}
    with pytest.raises(IngestionError, match="no stringed track"):
        write_songsterr_gp5([drums], tmp_path / "drums.gp5", title="t", artist="a")


def test_the_desktop_windows_close_dialog_is_in_english(english: None) -> None:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    import start_standalone

    assert start_standalone.busy_message().startswith("RockForge is still working")


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
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


def test_an_api_error_follows_the_language_the_browser_sends(client: TestClient) -> None:
    body = {"song": "nothing here"}
    r = client.post("/songsterr/import", json=body, headers={"X-RockForge-Lang": "en"})
    assert r.status_code == 422
    assert r.json()["detail"].startswith("could not read the Songsterr link")
    r = client.post("/songsterr/import", json=body)
    assert r.status_code == 422
    assert r.json()["detail"].startswith("não percebi o link do Songsterr")
    # The header is per request: it does not leak into the next one.
    r = client.post("/songsterr/import", json=body, headers={"X-RockForge-Lang": "pt"})
    assert r.json()["detail"].startswith("não percebi")


def test_the_saved_language_is_what_runs_outside_a_request(client: TestClient) -> None:
    from rockforge import runtime_settings

    assert runtime_settings.ui_language() == "pt"
    r = client.put("/ui-language", json={"lang": "en"})
    assert r.status_code == 200
    assert runtime_settings.ui_language() == "en"
    # No request here — the worker's and the desktop window's case.
    assert i18n.tr("não encontrado", "not found") == "not found"
    client.put("/ui-language", json={"lang": "pt"})
    assert runtime_settings.ui_language() == "pt"
    assert i18n.tr("não encontrado", "not found") == "não encontrado"
