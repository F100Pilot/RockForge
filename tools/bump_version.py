"""Move RockForge to its next version (docs/RELEASE_PROCESS.md).

    python -m tools.bump_version 0.10.0-beta.13 --goal "Fixes for testers"

Refuses a number that may not follow the current one (rockforge.versioning
``allowed_next``). Then, in one go:

- writes the version in ``rockforge/__init__.py`` and ``installer.iss``;
- turns each changelog's unreleased section into the version's own section,
  dated today, and opens an empty one above it;
- in tracking/: assigns every fix still "unreleased" to it, marks the release
  before it Superseded once that one was published, and adds its entry
  (``published`` stays "pending" until ``python -m tools.bump_version
  --published <version>`` records what the release workflow did);
- renders the logs and runs tools/release_check.

On ``main`` a new version number IS a publication: CI passing on the commit
starts the release workflow. The maintainer's rule: after every change, decide
the bump by docs/VERSIONING.md and run this in the same push, unless told not to.
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from tools import release_check, tracking
from tools.tracking import PENDING, UNRELEASED

ROOT = tracking.ROOT
from rockforge import versioning  # noqa: E402

UNRELEASED_HEADINGS = {"CHANGELOG.md": "## [Por lançar]", "CHANGELOG.en.md": "## [Unreleased]"}


def _changelog_items(root: Path, title: str) -> tuple[list[str], list[str]]:
    """New and Changed items of a version's English section (their bold lead)."""
    text = (root / "CHANGELOG.en.md").read_text(encoding="utf-8")
    m = re.search(rf"^## \[{re.escape(title)}\][^\n]*\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    if not m:
        return [], []
    found: dict[str, list[str]] = {}
    for sec in re.finditer(r"^### ([^\n]+)\n(.*?)(?=^### |\Z)", m.group(1), re.M | re.S):
        items = re.findall(r"^- (.*?)(?=^- |\Z)", sec.group(2), re.M | re.S)
        out = []
        for it in items:
            it = " ".join(it.split())
            bold = re.match(r"\*\*(.+?)\*\*", it)
            out.append((bold.group(1) if bold else re.split(r"(?<=[.])\s", it)[0]).rstrip(":. "))
        found[sec.group(1)] = out
    return found.get("New", []) + found.get("Added", []), found.get("Changed", [])


def bump(new: str, *, goal: str, root: Path = ROOT, today: str | None = None) -> list[str]:
    """Do it; returns release_check's reasons (empty = may be published)."""
    today = today or dt.date.today().isoformat()
    init = root / "src" / "rockforge" / "__init__.py"
    current = release_check._init_version(root)
    why = versioning.allowed_next(current, new)
    if why:
        raise SystemExit(f"{new} cannot follow {current}: {why}")
    v = versioning.parse(new)
    init.write_text(re.sub(r'^__version__ = "[^"]+"$', f'__version__ = "{new}"',
                           init.read_text(encoding="utf-8"), flags=re.M), encoding="utf-8")
    iss = root / "installer.iss"
    iss.write_text(re.sub(r'#define MyAppVersion "[^"]+"', f'#define MyAppVersion "{new}"',
                          iss.read_text(encoding="utf-8")), encoding="utf-8")
    title = versioning.changelog_title(v)
    if v.stage != "dev":
        for name, heading in UNRELEASED_HEADINGS.items():
            path = root / name
            text = path.read_text(encoding="utf-8")
            if heading not in text:
                raise SystemExit(f"{name} has no {heading} section to release")
            text = text.replace(heading, f"{heading}\n\n## [{title}] — {today}", 1)
            path.write_text(text, encoding="utf-8")

    reg = tracking.load(root / "tracking")
    if v.stage != "dev":
        for fx in reg.fixes:
            if fx["version"] == UNRELEASED:
                fx["version"] = new
        features, improvements = _changelog_items(root, title)
        entry: dict[str, Any] = {
            "version": new, "status": tracking.STAGE_STATUS[v.stage], "created": today,
            "published": PENDING, "commit": PENDING,
            "build": "GitHub Actions release workflow", "artifacts": [], "goal": goal,
            "features": features, "improvements": improvements, "breaking": [],
            "tests": "CI (ruff, mypy, pytest, ESLint, Docker build) on the release commit, "
                     "tools/release_check, and the frozen .exe smoke test of the release workflow",
            "approved_by": "the maintainer (asked for the release)",
            "upgrade": "Install the new version over it (installer) or replace the folder "
                       "(portable zip); start.bat pulls by itself. To go back, install an earlier "
                       "release from the Releases page.",
            "exceptions": [],
        }
        reg.releases.append(entry)
    tracking.save(reg, root / "tracking")
    tracking.render(reg, root / "tracking")
    return release_check.check(new, root) if v.stage != "dev" else []


def record_published(version: str, date: str, *, root: Path = ROOT,
                     commit: str | None = None) -> None:
    """The release workflow published ``version`` on ``date``: record it, with the
    tag's commit, and mark the release before it Superseded."""
    reg = tracking.load(root / "tracking")
    rel = reg.release(version)
    if rel is None:
        raise SystemExit(f"{version} is not in the release register")
    if commit is None:
        out = subprocess.run(["git", "-C", str(root), "rev-parse", f"v{version}^{{commit}}"],
                             capture_output=True, text=True, stdin=subprocess.DEVNULL)
        commit = out.stdout.strip() if out.returncode == 0 else PENDING
    rel["published"] = date
    rel["commit"] = commit
    rel["artifacts"] = [f"https://github.com/F100Pilot/RockForge/releases/tag/v{version}"]
    for other in reg.releases:
        if other is not rel and tracking._published(other) and other["status"] in (
                "Beta", "RC", "Stable"):
            other["status"] = "Superseded"
    tracking.save(reg, root / "tracking")
    tracking.render(reg, root / "tracking")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m tools.bump_version")
    ap.add_argument("version")
    ap.add_argument("--goal", help="what the release is for (release register)")
    ap.add_argument("--published", metavar="DATE",
                    help="record that VERSION was published on DATE (YYYY-MM-DD)")
    args = ap.parse_args(argv)
    if args.published:
        record_published(args.version, args.published)
        return 0
    if not args.goal:
        ap.error("--goal is required")
    reasons = bump(args.version, goal=args.goal)
    for r in reasons:
        print(f"BLOCKED: {r}")
    print(f"{args.version}: written. " + (
        "release_check passes — write docs/RELEASE_NOTES.md, commit and push to publish."
        if not reasons else f"release_check: {len(reasons)} reason(s) not to publish it yet."))
    return 1 if reasons else 0


if __name__ == "__main__":
    sys.exit(main())
