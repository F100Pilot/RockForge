"""The technical log: rotated, levelled, tied to requests, and never a secret."""

from __future__ import annotations

import importlib
import logging
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from rockforge import app_logging


def test_secrets_and_the_account_name_are_taken_out(monkeypatch: pytest.MonkeyPatch) -> None:
    from rockforge import config

    monkeypatch.setattr(config.settings, "api_token", "s3cr3t-token-value")
    home = str(Path.home())
    text = app_logging.redact(
        "token s3cr3t-token-value; Authorization: Basic dXNlcjpwYXNz; "
        "Cookie: session=abc; password=hunter2 api_key=XYZ123 "
        f"file {home}/Music/song.gp5 and C:\\Users\\Maria\\Desktop\\a.gp5 /home/joao/x.wav")
    for secret in ("s3cr3t-token-value", "dXNlcjpwYXNz", "session=abc", "hunter2", "XYZ123",
                   "Maria", "joao"):
        assert secret not in text
    assert "~/Music/song.gp5" in text or home in ("/", "")
    assert "C:\\Users\\<user>\\Desktop\\a.gp5" in text


def test_the_log_rotates_and_a_second_setup_does_not_write_twice(tmp_path: Path) -> None:
    path = app_logging.configure(tmp_path, level="INFO", loggers=("rockforge-test",))
    assert path == tmp_path / "logs" / "rockforge.log"
    app_logging.configure(tmp_path, level="INFO", loggers=("rockforge-test",))
    log = logging.getLogger("rockforge-test")
    log.setLevel(logging.INFO)
    log.warning("one line password=hunter2")
    for h in log.handlers:
        h.flush()
    text = path.read_text(encoding="utf-8")
    assert text.count("one line") == 1
    assert "WARNING" in text and "[rockforge-test]" in text and "hunter2" not in text
    handler = next(h for h in log.handlers if h.name == "rockforge-file")
    assert isinstance(handler, logging.handlers.RotatingFileHandler)
    assert (handler.maxBytes, handler.backupCount) == (app_logging.MAX_BYTES, app_logging.BACKUPS)
    log.removeHandler(handler)
    handler.close()


def test_a_folder_that_cannot_be_written_does_not_stop_the_app(tmp_path: Path) -> None:
    blocker = tmp_path / "file"
    blocker.write_text("not a folder")
    assert app_logging.configure(blocker, loggers=("rockforge-test-2",)) is None
    assert logging.raiseExceptions is False


def test_the_end_of_a_log_is_read_back_redacted(tmp_path: Path) -> None:
    log = tmp_path / "x.log"
    log.write_text("".join(f"line {n}\n" for n in range(200)) + "token=abcdef\n")
    tail = app_logging.tail(log, 3)
    assert tail == ["line 198", "line 199", "token=<redacted>"]
    assert app_logging.tail(tmp_path / "missing.log") == []


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("ROCKFORGE_DATABASE_URL", f"sqlite:///{tmp_path}/test.db")
    monkeypatch.setenv("ROCKFORGE_WORK_DIR", str(tmp_path / "work"))
    import rockforge.config as config

    importlib.reload(config)
    import rockforge.interfaces.api.app as app_module

    importlib.reload(app_module)

    @app_module.app.get("/__boom")
    def boom() -> None:
        raise RuntimeError("something broke password=hunter2")

    with TestClient(app_module.app, raise_server_exceptions=False) as c:
        yield c


def test_an_internal_error_is_logged_with_an_id_the_user_can_report(client: TestClient,
                                                                     tmp_path: Path) -> None:
    log = tmp_path / "work" / "logs" / "rockforge.log"
    assert "RockForge API starting" in log.read_text(encoding="utf-8")
    r = client.get("/__boom")
    assert r.status_code == 500
    body = r.json()
    rid = body["error_id"]
    assert len(rid) == 8 and rid in body["detail"] and r.headers["X-Request-ID"] == rid
    for h in logging.getLogger().handlers:
        h.flush()
    text = log.read_text(encoding="utf-8")
    assert f"[{rid}]" in text and "unhandled error in GET /__boom" in text
    assert "RuntimeError: something broke" in text and "hunter2" not in text
    ok = client.get("/version")
    assert len(ok.headers["X-Request-ID"]) == 8


def test_version_says_which_build_this_is(client: TestClient) -> None:
    from rockforge import __version__

    d = client.get("/version").json()
    assert d["version"] == __version__ and d["full"].startswith(__version__)
    assert {"commit", "build_id", "built_at", "source", "display"} <= set(d)


def test_the_diagnostic_report_names_the_build_and_hides_secrets(
        client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    import rockforge.interfaces.api.app as app_module
    from rockforge import __version__

    monkeypatch.setattr(app_module.settings, "api_token", None)
    logging.getLogger("rockforge.test").warning("Authorization: Bearer abcdefghijkl")
    for h in logging.getLogger().handlers:
        h.flush()
    text = client.get("/diagnostic-report").json()["text"]
    assert f"RockForge {__version__}" in text
    assert "### External software" in text and "ffmpeg" in text.lower()
    assert "### Last lines of logs/rockforge.log" in text
    assert "abcdefghijkl" not in text
