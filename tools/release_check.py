"""May this version be published? (docs/RELEASE_PROCESS.md)

    python -m tools.release_check 0.10.0-beta.13

The release workflow runs it before it builds anything (``decide``), so a
version that fails here is never published — a red run, nothing on the Releases
page. Exit 0 = may be published, 1 = blocked (each reason printed).

Every version needs: the version written the same everywhere, its section in
both changelogs, release notes, its entry in tracking/releases.json, every
committed fix assigned to it or an earlier version, and registers that pass
every rule. Then, by stage:

- **dev** — never published.
- **beta** — no open Critical bug that affects it.
- **rc** — no open Critical or High bug and no open P1 that affects it, and
  every Critical/High bug fixed in its line verified (Fixed is not enough).
- **stable** — what an rc needs; it follows a published RC of the same number
  with no fix of its own (a change after the RC is a new RC); and every bug
  fixed in its line is Verified or Closed.

A bug can be let through only by an exception written in the version's entry
(``exceptions``: the bug, why, the risk, who approved it, when).
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

from tools import tracking
from tools.tracking import ACTIVE, DONE, PENDING, UNRELEASED, Registers

ROOT = tracking.ROOT
from rockforge import versioning  # noqa: E402


def _iss_version(root: Path) -> str:
    m = re.search(r'#define MyAppVersion "([^"]+)"', (root / "installer.iss").read_text())
    return m.group(1) if m else ""


def _init_version(root: Path) -> str:
    m = re.search(r'^__version__ = "([^"]+)"$',
                  (root / "src" / "rockforge" / "__init__.py").read_text(), re.M)
    return m.group(1) if m else ""


def _affects(bug: dict[str, Any], version: str) -> bool:
    found = tracking._key(str(bug.get("found_in_version")))
    return found is None or found <= (tracking._key(version) or (0,))


def blocking_bugs(reg: Registers, version: str) -> list[str]:
    """Why the bugs in the registers stop this version (empty = they do not)."""
    v = versioning.parse(version)
    rel = reg.release(version) or {}
    excepted = {str(e.get("bug")) for e in rel.get("exceptions") or []}
    reasons = []

    def block(b: dict[str, Any], why: str) -> None:
        if b["id"] not in excepted:
            reasons.append(f"{b['id']} ({b['severity']}, {b['priority']}, {b['status']}): "
                           f"{b['title']} — {why}")

    line = [b for b in reg.bugs
            if (fv := tracking.fixed_in(reg, b))
            and versioning.parse(fv).core == v.core]
    for b in reg.bugs:
        if b["status"] in ACTIVE and _affects(b, version):
            if b["severity"] == "Critical":
                block(b, "an open Critical bug")
            elif v.stage in ("rc", None) and b["severity"] == "High":
                block(b, "an open High bug (an RC or a stable version may not carry one)")
            elif v.stage in ("rc", None) and b["priority"] == "P1":
                block(b, "an open P1 bug")
    if v.stage in ("rc", None):
        for b in line:
            if b["status"] not in DONE and b["severity"] in ("Critical", "High"):
                block(b, "fixed in this line but not verified")
    if v.stage is None:
        for b in line:
            if b["status"] not in DONE:
                block(b, "fixed in this line but not verified (a stable version needs every "
                         "fix verified)")
    return reasons


def check(version: str, root: Path = ROOT, reg: Registers | None = None) -> list[str]:
    reasons: list[str] = []
    try:
        v = versioning.parse(version)
    except ValueError as exc:
        return [str(exc)]
    if v.build:
        reasons.append("a version is published without its build part")
    if v.stage == "dev":
        return [f"{version} is a development version: those are never published"]
    reg = reg or tracking.load(root / "tracking")
    for where, written in (("rockforge/__init__.py", _init_version(root)),
                           ("installer.iss", _iss_version(root))):
        if written != version:
            reasons.append(f"{where} says {written!r}, not {version}")
    title = versioning.changelog_title(v)
    for name in ("CHANGELOG.md", "CHANGELOG.en.md"):
        text = (root / name).read_text(encoding="utf-8")
        if not re.search(rf"^## \[{re.escape(title)}\] — \d{{4}}-\d{{2}}-\d{{2}}$", text, re.M):
            reasons.append(f"{name} has no '## [{title}] — <date>' section")
    notes = root / "docs" / "RELEASE_NOTES.md"
    if not notes.exists() or not notes.read_text(encoding="utf-8").strip():
        reasons.append("docs/RELEASE_NOTES.md is empty")
    reasons += tracking.check_registers(reg, version)
    if (root / ".git").exists():
        reasons += tracking.check_commits(reg, root)
    reasons += [f"{n} is out of date: python -m tools.tracking render"
                for n in tracking.stale_logs(reg, root / "tracking")]
    rel = reg.release(version)
    if rel is None:
        return reasons
    if rel["status"] in ("Superseded", "Withdrawn", "Not published"):
        reasons.append(f"{version} is {rel['status']} in the release register")
    loose = [fx["id"] for fx in reg.fixes if fx["version"] == UNRELEASED]
    if loose:
        reasons.append(f"fixes not assigned to a version: {', '.join(loose)} "
                       "(tools/bump_version.py assigns them)")
    if v.stage is None:
        earlier = [r for r in reg.releases
                   if (tracking._key(r["version"]) or (0,)) < v.key
                   and r["status"] != "Not published"]
        prev = earlier[-1] if earlier else None
        pv = versioning.parse(prev["version"]) if prev else None
        if pv is None or pv.core != v.core or pv.stage != "rc" or not tracking._published(prev):
            reasons.append(f"a stable version follows a published {v.core}-rc.N "
                           f"(the version before it is {prev['version'] if prev else 'none'})")
        own = [fx["id"] for fx in reg.fixes if fx["version"] == version]
        if own:
            reasons.append(f"fixes made after the RC ({', '.join(own)}): publish a new RC first")
    if rel["approved_by"] == PENDING:
        reasons.append("nobody is recorded as approving it (approved_by)")
    reasons += blocking_bugs(reg, version)
    return reasons


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m tools.release_check")
    ap.add_argument("version")
    args = ap.parse_args(argv)
    reasons = check(args.version.removeprefix("v"))
    for r in reasons:
        print(f"BLOCKED: {r}")
    print(f"{args.version}: " + ("may be published" if not reasons else
                                 f"{len(reasons)} reason(s) not to publish it"))
    return 1 if reasons else 0


if __name__ == "__main__":
    sys.exit(main())
