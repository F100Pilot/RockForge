"""Which build is running: the version names the release, the build the code."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from rockforge import __version__, build_info


@pytest.fixture(autouse=True)
def _fresh() -> None:
    build_info.build_info.cache_clear()
    yield
    build_info.build_info.cache_clear()


def test_a_bundle_says_the_commit_and_build_it_was_made_from(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "rockforge").mkdir()
    (tmp_path / "rockforge" / build_info.FILE_NAME).write_text(json.dumps({
        "version": __version__, "commit": "a" * 40, "dirty": False, "build_id": "ci.57",
        "built_at": "2026-10-18T10:00:00Z", "ci_run_url": "https://example.invalid/run/1"}))
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    info = build_info.build_info()
    assert info["source"] == "exe"
    assert info["full"] == f"{__version__}+ci.57.aaaaaaaaaa"
    assert info["commit_short"] == "a" * 10 and info["built_at"] == "2026-10-18T10:00:00Z"
    assert build_info.summary().startswith(f"RockForge {__version__}+ci.57.")


def test_a_git_checkout_asks_git(monkeypatch: pytest.MonkeyPatch) -> None:
    if not (build_info._REPO / ".git").exists():
        pytest.skip("not a git checkout")
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)
    info = build_info.build_info()
    assert info["source"] == "git" and len(info["commit"]) == 40
    assert info["full"].startswith(f"{__version__}+{info['commit'][:10]}")


def test_without_git_only_the_version_is_known(tmp_path: Path,
                                               monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)
    monkeypatch.setattr(build_info, "_REPO", tmp_path)
    info = build_info.build_info()
    assert info["source"] == "source" and info["full"] == __version__ and not info["commit"]


def test_an_unreadable_bundle_file_never_breaks_the_app(tmp_path: Path,
                                                        monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "rockforge").mkdir()
    (tmp_path / "rockforge" / build_info.FILE_NAME).write_text("{not json")
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    info = build_info.build_info()
    assert info["version"] == __version__ and info["source"] == "unknown"


def test_collect_names_the_ci_run(tmp_path: Path) -> None:
    info = build_info.collect(tmp_path, env={"GITHUB_RUN_NUMBER": "12", "GITHUB_RUN_ID": "99",
                                             "GITHUB_REPOSITORY": "o/r"})
    assert info["build_id"] == "ci.12"
    assert info["ci_run_url"] == "https://github.com/o/r/actions/runs/99"
    assert info["commit"] == "" and info["dirty"] is False  # tmp_path is no git repo
    assert build_info.collect(tmp_path, env={})["build_id"] == "local"
