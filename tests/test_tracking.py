"""The bug, fix and release registers, and the gate before a release
(tools/tracking.py, tools/release_check.py, tools/bump_version.py).

The registers are the record of what went wrong and what was done about it; the
rules are what keep that record honest — no id lost or reused, nothing called
fixed without a commit, nothing closed without a verification and a published
release, no version that claims a fix it does not contain.
"""

from __future__ import annotations

import copy
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
from tools import bump_version, release_check, tracking
from tools.tracking import Registers

from rockforge import __version__

ROOT = Path(__file__).resolve().parents[1]

# ── the real registers ──────────────────────────────────────────────────────


def test_the_registers_follow_every_rule() -> None:
    reg = tracking.load()
    assert tracking.check_registers(reg, __version__) == []
    assert tracking.stale_logs(reg) == [], "python -m tools.tracking render"


def test_every_fix_is_in_the_version_it_is_said_to_be_in() -> None:
    if not (ROOT / ".git").exists():
        if os.environ.get("CI") == "true":
            pytest.fail("CI must check out the history (fetch-depth: 0)")
        pytest.skip("not a git checkout")
    shallow = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--is-shallow-repository"],
                             capture_output=True, text=True).stdout.strip()
    if shallow == "true":
        if os.environ.get("CI") == "true":
            pytest.fail("CI must check out the history (fetch-depth: 0)")
        pytest.skip("shallow clone")
    assert tracking.check_commits(tracking.load()) == []


# ── invented registers for the rules ────────────────────────────────────────

SHA_A = "a" * 40  # never resolved against git in these tests


def _release(version: str, status: str, published: str | None = "2026-01-02") -> dict[str, Any]:
    return {"version": version, "status": status, "created": "2026-01-01",
            "published": published, "commit": tracking.PENDING, "build": "test",
            "artifacts": [], "goal": "test", "features": [], "improvements": [],
            "breaking": [], "tests": "test", "approved_by": "the maintainer",
            "upgrade": "test", "exceptions": []}


def _bug(n: int, status: str = "Open", fixes: list[str] | None = None,
         severity: str = "Medium", priority: str = "P3",
         found: str = "1.0.0-beta.1") -> dict[str, Any]:
    history = [{"date": "2026-01-01", "status": "Open"}]
    path = {"Fixed": ["Fixed"], "Verified": ["Fixed", "Verified"],
            "Closed": ["Fixed", "Verified", "Closed"], "Triaged": ["Triaged"]}.get(status, [])
    history += [{"date": "2026-01-03", "status": s} for s in path]
    done = status in ("Fixed", "Verified", "Closed")
    return {
        "id": f"BUG-{n:04d}", "title": f"invented bug {n}", "detected": "2026-01-01",
        "reported_by": "found during development", "found_in_version": found,
        "found_in_build": tracking.PENDING, "module": "app", "description": "invented",
        "steps": tracking.PENDING, "expected": tracking.PENDING, "observed": tracking.PENDING,
        "severity": severity, "priority": priority, "status": status,
        "root_cause": tracking.PENDING, "fixes": fixes or [],
        "verified_by": "the test suite" if status in ("Verified", "Closed") else tracking.PENDING,
        "verification": "tests pass" if status in ("Verified", "Closed") else tracking.PENDING,
        "evidence": [], "resolved": "2026-01-03" if done else tracking.PENDING,
        "closed": "2026-01-03" if status == "Closed" else tracking.PENDING, "history": history,
    }


def _fix(n: int, bugs: list[str], version: str) -> dict[str, Any]:
    return {"id": f"FIX-{n:04d}", "bugs": bugs, "date": "2026-01-03", "author": "test",
            "root_cause": "invented", "solution": "invented", "components": [],
            "commits": [SHA_A], "version": version, "tests": ["tests/test_x.py::test_y"],
            "manual_checks": [], "test_result": "passed", "regression_risk": "low",
            "validation": "automated"}


def _registers() -> Registers:
    return Registers(
        bugs=[_bug(1, "Closed", ["FIX-0001"]), _bug(2, "Fixed", ["FIX-0002"]), _bug(3)],
        fixes=[_fix(1, ["BUG-0001"], "1.0.0-beta.2"), _fix(2, ["BUG-0002"], "unreleased")],
        releases=[_release("1.0.0-beta.1", "Superseded"), _release("1.0.0-beta.2", "Beta")],
    )


def _problems(reg: Registers) -> list[str]:
    return tracking.check_registers(reg)


def test_the_invented_registers_are_valid() -> None:
    assert _problems(_registers()) == []


def test_an_id_is_never_lost_or_reused() -> None:
    reg = _registers()
    del reg.bugs[1]
    reg.fixes[1]["bugs"] = ["BUG-0003"]
    reg.bugs[1]["fixes"] = ["FIX-0002"]
    assert any("expected BUG-0002" in p for p in _problems(reg))
    reg = _registers()
    reg.bugs[2]["id"] = "BUG-0002"
    assert any("expected BUG-0003" in p for p in _problems(reg))


@pytest.mark.parametrize(("change", "says"), [
    (lambda r: r.fixes[1].update(commits=[]), "names no commit"),
    (lambda r: r.bugs[0].update(verification="pending"), "without saying how"),
    (lambda r: r.fixes[0].update(test_result="not run", validation="pending"),
     "no fix has a passed test"),
    (lambda r: r.releases[1].update(status="Not published", published=None),
     "not in a published release"),
    (lambda r: r.bugs[2]["history"].append({"date": "2026-01-02", "status": "Closed"}),
     "Open → Closed"),
    (lambda r: r.bugs[2].update(status="Duplicate"), "duplicate_of"),
    (lambda r: r.fixes[0].update(bugs=["BUG-0003"]), "does not name it back"),
    (lambda r: r.bugs[2].update(found_in_version="2.0.0-beta.1"), "not in the release register"),
    (lambda r: r.bugs[0].update(found_in_version="1.0.0-beta.2", fixes=["FIX-0001"])
     or r.fixes[0].update(version="1.0.0-beta.1"), "before the version the bug was found in"),
    (lambda r: r.releases[0].update(status="Beta"), "it is Superseded"),
    (lambda r: r.bugs[2].update(severity="Huge"), "severity must be one of"),
    (lambda r: r.bugs[2].update(title="pending"), "never pending"),
])
def test_each_rule_says_what_is_wrong(change: Any, says: str) -> None:
    reg = _registers()
    change(reg)
    assert any(says in p for p in _problems(reg)), _problems(reg)


def test_what_a_release_fixed_and_carried_is_derived() -> None:
    reg = _registers()
    assert [b["id"] for b in tracking.bugs_fixed_in(reg, "1.0.0-beta.2")] == ["BUG-0001"]
    assert tracking.fixed_in(reg, reg.bugs[1]) is None  # its fix is unreleased
    carried = [b["id"] for b in tracking.known_open_at(reg, "1.0.0-beta.2")]
    assert carried == ["BUG-0002", "BUG-0003"]
    assert [b["id"] for b in tracking.known_open_at(reg, "1.0.0-beta.1")] == [
        "BUG-0001", "BUG-0002", "BUG-0003"]


def test_the_logs_name_every_record() -> None:
    reg = _registers()
    index = tracking.render_bug_log(reg)
    assert all(f"[BUG-000{n}](bugs/app.md#bug-000{n})" in index for n in (1, 2, 3))
    pages = tracking.render_bug_pages(reg)
    assert list(pages) == ["bugs/app.md"]
    assert all(f"## BUG-000{n}" in pages["bugs/app.md"] for n in (1, 2, 3))
    assert "## FIX-0002" in tracking.render_fix_log(reg)
    rel_log = tracking.render_release_log(reg)
    assert rel_log.index("## 1.0.0-beta.2") < rel_log.index("## 1.0.0-beta.1")


def test_a_status_change_is_a_step_of_the_history() -> None:
    reg = _registers()
    bug = reg.bugs[2]
    tracking.set_status(bug, "Triaged", "seen", date="2026-01-05")
    assert bug["status"] == "Triaged" and bug["history"][-1]["note"] == "seen"
    with pytest.raises(ValueError):
        tracking.set_status(bug, "Closed")
    new = tracking.new_bug(reg, "another", module="psarc", severity="High", priority="P2",
                           found_in="1.0.0-beta.2", reported_by="user report")
    assert new["id"] == "BUG-0004" and _problems(reg) == []


# ── the gate before a release ────────────────────────────────────────────────


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    """The files a release touches, with invented registers at 1.0.0-beta.2."""
    (tmp_path / "src" / "rockforge").mkdir(parents=True)
    (tmp_path / "src" / "rockforge" / "__init__.py").write_text('__version__ = "1.0.0-beta.2"\n')
    (tmp_path / "installer.iss").write_text('#define MyAppVersion "1.0.0-beta.2"\n')
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "RELEASE_NOTES.md").write_text("### Fixed\n- invented\n")
    (tmp_path / "CHANGELOG.md").write_text(
        "# Novidades\n\n## [Por lançar]\n\n### Corrigido\n- inventado\n\n"
        "## [1.0.0 beta 2] — 2026-01-02\n\n## [1.0.0 beta 1] — 2026-01-01\n")
    (tmp_path / "CHANGELOG.en.md").write_text(
        "# Changes\n\n## [Unreleased]\n\n### New\n- **Invented feature:** text\n\n"
        "### Fixed\n- invented\n\n## [1.0.0 beta 2] — 2026-01-02\n\n"
        "## [1.0.0 beta 1] — 2026-01-01\n")
    (tmp_path / "tracking").mkdir()
    reg = _registers()
    tracking.save(reg, tmp_path / "tracking")
    tracking.render(reg, tmp_path / "tracking")
    return tmp_path


def test_the_current_version_may_be_published(repo: Path) -> None:
    reg = tracking.load(repo / "tracking")
    reg.fixes[1]["version"] = "1.0.0-beta.2"  # nothing left unassigned
    tracking.render(reg, repo / "tracking")
    assert release_check.check("1.0.0-beta.2", repo, reg) == []


def test_a_beta_is_stopped_by_an_open_critical_bug_unless_an_exception_is_written(
        repo: Path) -> None:
    reg = tracking.load(repo / "tracking")
    reg.fixes[1]["version"] = "1.0.0-beta.2"
    reg.bugs[2].update(severity="Critical", priority="P1")
    tracking.render(reg, repo / "tracking")
    assert any("BUG-0003" in r and "Critical" in r
               for r in release_check.check("1.0.0-beta.2", repo, reg))
    reg.releases[1]["exceptions"] = [{"bug": "BUG-0003", "reason": "only one setup",
                                      "risk": "crash for those users",
                                      "approved_by": "the maintainer", "date": "2026-01-02"}]
    tracking.render(reg, repo / "tracking")
    assert release_check.check("1.0.0-beta.2", repo, reg) == []


def test_an_rc_is_stopped_by_an_open_high_bug_and_an_unverified_fix(repo: Path) -> None:
    reg = Registers(
        bugs=[_bug(1, "Open", severity="High", priority="P2"),
              _bug(2, "Fixed", ["FIX-0001"], severity="High", priority="P2")],
        fixes=[_fix(1, ["BUG-0002"], "1.0.0-rc.1")],
        releases=[_release("1.0.0-beta.1", "Superseded"),
                  _release("1.0.0-rc.1", "RC", tracking.PENDING)])
    for name, version in (("__init__.py", '__version__ = "1.0.0-rc.1"\n'),):
        (repo / "src" / "rockforge" / name).write_text(version)
    (repo / "installer.iss").write_text('#define MyAppVersion "1.0.0-rc.1"\n')
    for name in ("CHANGELOG.md", "CHANGELOG.en.md"):
        path = repo / name
        path.write_text(path.read_text() + "\n## [1.0.0 rc 1] — 2026-01-05\n")
    tracking.render(reg, repo / "tracking")
    reasons = release_check.check("1.0.0-rc.1", repo, reg)
    assert any("BUG-0001" in r and "open High" in r for r in reasons)
    assert any("BUG-0002" in r and "not verified" in r for r in reasons)


def test_a_stable_version_follows_a_published_rc_with_no_fix_of_its_own(repo: Path) -> None:
    reg = Registers(bugs=[], fixes=[], releases=[_release("1.0.0-beta.1", "Superseded"),
                                                 _release("1.0.0", "Stable", tracking.PENDING)])
    reasons = release_check.blocking_bugs(reg, "1.0.0")
    assert reasons == []
    (repo / "src" / "rockforge" / "__init__.py").write_text('__version__ = "1.0.0"\n')
    (repo / "installer.iss").write_text('#define MyAppVersion "1.0.0"\n')
    for name in ("CHANGELOG.md", "CHANGELOG.en.md"):
        path = repo / name
        path.write_text(path.read_text() + "\n## [1.0.0] — 2026-01-09\n")
    tracking.render(reg, repo / "tracking")
    assert any("follows a published 1.0.0-rc.N" in r
               for r in release_check.check("1.0.0", repo, reg))
    reg.releases.insert(1, _release("1.0.0-rc.1", "RC"))
    tracking.render(reg, repo / "tracking")
    assert release_check.check("1.0.0", repo, reg) == []


def test_a_development_version_is_never_published(repo: Path) -> None:
    assert "never published" in release_check.check("1.1.0-dev.1", repo)[0]


def test_the_bump_writes_every_copy_and_assigns_the_fixes(repo: Path) -> None:
    reasons = bump_version.bump("1.0.0-beta.3", goal="invented", root=repo, today="2026-01-07")
    assert reasons == []
    assert '"1.0.0-beta.3"' in (repo / "src" / "rockforge" / "__init__.py").read_text()
    assert '"1.0.0-beta.3"' in (repo / "installer.iss").read_text()
    pt = (repo / "CHANGELOG.md").read_text()
    assert "## [Por lançar]\n\n## [1.0.0 beta 3] — 2026-01-07\n\n### Corrigido" in pt
    reg = tracking.load(repo / "tracking")
    assert reg.fixes[1]["version"] == "1.0.0-beta.3"
    new = reg.release("1.0.0-beta.3")
    assert new and new["status"] == "Beta" and new["published"] == tracking.PENDING
    assert new["features"] == ["Invented feature"]
    bump_version.record_published("1.0.0-beta.3", "2026-01-07", root=repo, commit="b" * 40)
    reg = tracking.load(repo / "tracking")
    assert [r["status"] for r in reg.releases] == ["Superseded", "Superseded", "Beta"]
    assert tracking.check_registers(reg) == []


def test_the_bump_refuses_a_number_that_may_not_come_next(repo: Path) -> None:
    before = {p: p.read_bytes() for p in repo.rglob("*") if p.is_file()}
    with pytest.raises(SystemExit, match="cannot follow"):
        bump_version.bump("1.0.0-beta.5", goal="x", root=repo)
    assert {p: p.read_bytes() for p in repo.rglob("*") if p.is_file()} == before


def test_the_real_registers_parse_as_plain_json() -> None:
    for name in ("bugs.json", "fixes.json", "releases.json"):
        data = json.loads((ROOT / "tracking" / name).read_text(encoding="utf-8"))
        assert isinstance(data["items"], list)
    copy.deepcopy(tracking.load())  # plain data, nothing that cannot be copied
    assert shutil.which("git") or not (ROOT / ".git").exists()


def test_a_fix_said_to_be_in_a_version_it_is_not_in_is_caught(tmp_path: Path) -> None:
    """check_commits asks git: a fix committed AFTER a version's commit is not
    in that version, whatever the register says."""
    def git(*args: str) -> str:
        return subprocess.run(["git", "-C", str(tmp_path), *args], check=True,
                              capture_output=True, text=True).stdout.strip()

    git("init", "-q")
    git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty", "-m", "v1")
    release = git("rev-parse", "HEAD")
    git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty", "-m", "fix")
    later = git("rev-parse", "HEAD")
    reg = _registers()
    reg.releases[1]["commit"] = release
    reg.fixes[0]["commits"] = [release]
    reg.fixes[1]["commits"] = [later]
    assert tracking.check_commits(reg, tmp_path) == []
    reg.fixes[0]["commits"] = [later]  # FIX-0001 says it is in 1.0.0-beta.2
    problems = tracking.check_commits(reg, tmp_path)
    assert problems == [f"FIX-0001: commit {later} is not in 1.0.0-beta.2 "
                        f"(not an ancestor of {release})"]
    reg.fixes[0]["commits"] = ["0" * 40]
    assert "not in this repository" in tracking.check_commits(reg, tmp_path)[0]
