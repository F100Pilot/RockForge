"""«Há uma versão nova»: the GitHub Releases check (infrastructure/update_check.py)."""

from __future__ import annotations

import importlib
import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from rockforge.infrastructure import update_check as uc


def _rel(tag: str, *, draft: bool = False) -> dict[str, object]:
    return {"tag_name": tag, "draft": draft, "html_url": f"https://example.invalid/{tag}"}


def test_versions_sort_like_releases_do() -> None:
    order = ["0.9.0", "0.10.0a1", "0.10.0-beta.3", "0.10.0b4", "v0.10.0-rc.1", "0.10.0", "0.10.1"]
    keys = [uc.parse_version(v) for v in order]
    assert all(k is not None for k in keys)
    assert keys == sorted(keys)  # type: ignore[type-var]
    assert uc.parse_version("0.10.0b3") == uc.parse_version("0.10.0-beta.3")
    assert uc.parse_version("latest") is None
    assert uc.is_prerelease("0.10.0b3") and not uc.is_prerelease("1.0.0")


def test_a_beta_is_offered_the_next_beta_and_a_final_only_finals() -> None:
    releases = [_rel("0.10.0-beta.4"), _rel("0.9.2"), _rel("0.11.0", draft=True), _rel("nightly")]
    assert uc.newest_release(releases, "0.10.0b3") == ("0.10.0-beta.4", "https://example.invalid/0.10.0-beta.4")
    # Someone on a final version is not pushed onto a beta; drafts never count.
    assert uc.newest_release(releases, "0.9.1") == ("0.9.2", "https://example.invalid/0.9.2")
    assert uc.newest_release("not a list", "0.9.1") is None


@pytest.fixture()
def work(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    from rockforge import config

    monkeypatch.setattr(config.settings, "work_dir", tmp_path)
    monkeypatch.setattr(uc, "__version__", "0.10.0b3")
    return tmp_path


def test_a_newer_release_is_reported_and_asked_at_most_once_an_hour(work: Path) -> None:
    calls: list[int] = []

    def fetch() -> list[dict[str, object]]:
        calls.append(1)
        return [_rel("0.10.0-beta.4")]

    info = uc.check(fetch=fetch, now=1000.0, kind="exe")
    assert (info.newer, info.latest, info.current) == (True, "0.10.0-beta.4", "0.10.0b3")
    assert info.url.endswith("0.10.0-beta.4")
    assert uc.check(fetch=fetch, now=1000.0 + 3599, kind="exe").newer
    assert len(calls) == 1  # the second answer came from the hour's cache
    assert uc.CHECK_EVERY_S == 3600
    uc.check(fetch=fetch, now=1000.0 + uc.CHECK_EVERY_S + 1, kind="exe")
    assert len(calls) == 2


def test_offline_is_nothing_new_and_not_a_timeout_on_every_page(work: Path) -> None:
    calls: list[int] = []

    def offline() -> list[object]:
        calls.append(1)
        raise OSError("no network")

    info = uc.check(fetch=offline, now=5000.0, kind="exe")
    assert not info.newer and info.latest == ""
    uc.check(fetch=offline, now=5060.0, kind="exe")
    assert len(calls) == 1  # backing off for an hour
    uc.check(fetch=offline, now=5000.0 + uc.RETRY_AFTER_FAILURE_S + 1, kind="exe")
    assert len(calls) == 2


def test_the_same_version_is_not_newer_and_an_upgrade_forgets_the_old_answer(work: Path) -> None:
    assert not uc.check(fetch=lambda: [_rel("0.10.0-beta.3")], now=1.0, kind="exe").newer
    (work / "update_check.json").write_text(json.dumps(
        {"current": "0.9.0", "checked_at": 1.0, "latest": "0.10.0-beta.3", "url": "x"}))
    # The cache was written by an older RockForge: it is asked again, not trusted.
    assert uc.check(fetch=lambda: [], now=2.0, kind="exe").latest == ""


def test_a_git_checkout_is_told_apart_from_a_zip_download(tmp_path: Path) -> None:
    assert uc.install_kind(tmp_path) == "source"
    (tmp_path / ".git").mkdir()
    assert uc.install_kind(tmp_path) == "git"


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


def test_the_endpoint_says_nothing_when_turned_off(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from rockforge.infrastructure import update_check

    monkeypatch.setattr(update_check, "_fetch", lambda: [_rel("99.0.0")])
    on = client.get("/update-check").json()
    assert on["enabled"] and on["latest"] == "99.0.0" and on["newer"]
    assert client.post("/settings", json={"check_updates": False}).json()["check_updates"] is False
    off = client.get("/update-check").json()
    assert off["enabled"] is False and off["newer"] is False
