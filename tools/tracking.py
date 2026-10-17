"""The bug, fix and release registers (tracking/*.json) — rules, checks and logs.

The JSON files are the record; ``tracking/BUG_LOG.md``, ``FIX_LOG.md`` and
``RELEASE_LOG.md`` are generated from them (``python -m tools.tracking render``)
and a test fails when they are out of date, so the two can never disagree.
What a release fixed and which bugs it still carried are DERIVED from the bugs
and fixes, never written twice. docs/VERSIONING.md and docs/RELEASE_PROCESS.md
describe the process; this file enforces it.

    python -m tools.tracking check            # every rule; exit 1 on a problem
    python -m tools.tracking render           # rewrite the three logs
    python -m tools.tracking new-bug "title" --module psarc --severity High --priority P2
    python -m tools.tracking status BUG-0042 Fixed "note"   # one step of its history
    python -m tools.tracking notes 0.10.0-beta.13           # the fixes of a version, as a list

Standard library only, like the rest of the release tools.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from rockforge import versioning  # noqa: E402

TRACKING = ROOT / "tracking"
PENDING = "pending"
UNRELEASED = "unreleased"
# A bug found during the development before the first numbered version.
BEFORE_FIRST = "before 0.10.0-beta.1"

SEVERITIES = ("Critical", "High", "Medium", "Low")
PRIORITIES = ("P1", "P2", "P3", "P4")
STATUSES = ("Open", "Triaged", "In Progress", "Fixed", "Verified", "Closed",
            "Reopened", "Deferred", "Duplicate", "Cannot Reproduce")
# Still to be dealt with (Fixed is not done: it is not verified yet).
ACTIVE = ("Open", "Triaged", "In Progress", "Reopened")
DONE = ("Verified", "Closed")
TRANSITIONS: dict[str, tuple[str, ...]] = {
    "Open": ("Triaged", "In Progress", "Fixed", "Deferred", "Duplicate", "Cannot Reproduce"),
    "Triaged": ("In Progress", "Fixed", "Deferred", "Duplicate", "Cannot Reproduce"),
    "In Progress": ("Fixed", "Deferred", "Triaged"),
    "Fixed": ("Verified", "Reopened"),
    "Verified": ("Closed", "Reopened"),
    "Closed": ("Reopened",),
    "Reopened": ("Triaged", "In Progress", "Fixed", "Deferred"),
    "Deferred": ("Triaged", "In Progress", "Open"),
    "Duplicate": ("Reopened",),
    "Cannot Reproduce": ("Reopened", "Triaged"),
}
MODULES = {
    "import": "Creating a project: Guitar Pro, Songsterr, PDF, recording, wizard",
    "sync": "Synchronisation tools on the score",
    "editor": "Note, section and fret-hand-position editing",
    "viewer": "The score, fretboard, 3D highway and playback",
    "tones": "Tones: editor, detection, suggestions, presets",
    "lyrics": "Lyrics: GP, LRCLIB, detection, editor",
    "audio": "Audio: loudness, Wwise, stems, ML stages",
    "psarc": "The native .psarc: SNG, manifest, container, verification",
    "dlc-builder": "The DLC Builder bundle: XML, .rs2dlc",
    "export": "Export back to Guitar Pro",
    "game": "Installing in the game",
    "app": "API, settings, projects, the web UI shell",
    "exe": "The Windows .exe, installer and extra components",
    "security": "Security",
    "release": "Building and publishing releases",
}
FIX_RESULTS = ("passed", "failed", "not run", PENDING)
VALIDATIONS = ("automated", "manual", "confirmed by user", "failed", PENDING)
RELEASE_STATUSES = ("Development", "Beta", "RC", "Stable", "Superseded", "Withdrawn",
                    "Not published")
STAGE_STATUS = {"dev": "Development", "alpha": "Beta", "beta": "Beta", "rc": "RC", None: "Stable"}

_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2})?$")
_SHA = re.compile(r"^[0-9a-f]{7,40}$")
BUG_KEYS = (
    "id", "title", "detected", "reported_by", "found_in_version", "found_in_build", "module",
    "description", "steps", "expected", "observed", "severity", "priority", "status",
    "root_cause", "fixes", "verified_by", "verification", "evidence", "resolved", "closed",
    "history",
)
OPTIONAL_BUG_KEYS = ("duplicate_of", "note", "links")
FIX_KEYS = (
    "id", "bugs", "date", "author", "root_cause", "solution", "components", "commits",
    "version", "tests", "manual_checks", "test_result", "regression_risk", "validation",
)
RELEASE_KEYS = (
    "version", "status", "created", "published", "commit", "build", "artifacts", "goal",
    "features", "improvements", "breaking", "tests", "approved_by", "upgrade", "exceptions",
)


@dataclass
class Registers:
    bugs: list[dict[str, Any]] = field(default_factory=list)
    fixes: list[dict[str, Any]] = field(default_factory=list)
    releases: list[dict[str, Any]] = field(default_factory=list)

    def bug(self, bid: str) -> dict[str, Any] | None:
        return next((b for b in self.bugs if b.get("id") == bid), None)

    def fix(self, fid: str) -> dict[str, Any] | None:
        return next((f for f in self.fixes if f.get("id") == fid), None)

    def release(self, version: str) -> dict[str, Any] | None:
        return next((r for r in self.releases if r.get("version") == version), None)


def load(folder: Path = TRACKING) -> Registers:
    def read(name: str) -> list[dict[str, Any]]:
        data = json.loads((folder / name).read_text(encoding="utf-8"))
        items = data.get("items") if isinstance(data, dict) else None
        if not isinstance(items, list):
            raise ValueError(f"{name}: expected {{\"items\": [...]}}")
        return items

    return Registers(read("bugs.json"), read("fixes.json"), read("releases.json"))


def save(reg: Registers, folder: Path = TRACKING) -> None:
    for name, items, what in (("bugs.json", reg.bugs, "bugs"), ("fixes.json", reg.fixes, "fixes"),
                              ("releases.json", reg.releases, "releases")):
        body = {"about": f"The {what} register. Rules: tools/tracking.py; process: "
                         "docs/VERSIONING.md. Never delete an entry or reuse an id.",
                "items": items}
        (folder / name).write_text(json.dumps(body, ensure_ascii=False, indent=2) + "\n",
                                   encoding="utf-8")


def _key(version: str) -> tuple[int, ...] | None:
    """Order of a version a bug or fix names; the time before the first
    numbered version sorts first."""
    if version == BEFORE_FIRST:
        return (-1,)
    try:
        return versioning.parse(version).key
    except ValueError:
        return None


def _published(rel: dict[str, Any]) -> bool:
    """Out for people to download (a publication still "pending" is not)."""
    return rel.get("status") in ("Beta", "RC", "Stable", "Superseded", "Withdrawn") and rel.get(
        "published") not in (None, PENDING)


def fix_versions(reg: Registers, bug: dict[str, Any]) -> list[str]:
    out = []
    for fid in bug.get("fixes") or []:
        fx = reg.fix(fid)
        if fx:
            out.append(str(fx.get("version")))
    return out


def fixed_in(reg: Registers, bug: dict[str, Any]) -> str | None:
    """The first release holding every fix of a bug that is fixed (None while
    any fix is unreleased or the bug is not fixed)."""
    if bug.get("status") not in ("Fixed", "Verified", "Closed"):
        return None
    versions = fix_versions(reg, bug)
    if not versions or any(v == UNRELEASED for v in versions):
        return None
    return max(versions, key=lambda v: _key(v) or (0,))


def bugs_fixed_in(reg: Registers, version: str) -> list[dict[str, Any]]:
    return [b for b in reg.bugs if fixed_in(reg, b) == version]


def known_open_at(reg: Registers, version: str) -> list[dict[str, Any]]:
    """Bugs the version carried: found at or before it, and not fixed in it or
    in an earlier one (Deferred and Cannot Reproduce included — they are known)."""
    vkey = _key(version)
    if vkey is None:
        return []
    out = []
    for b in reg.bugs:
        if b.get("status") == "Duplicate":
            continue
        found = _key(str(b.get("found_in_version")))
        if found is None or found > vkey:
            continue
        fixed = fixed_in(reg, b)
        if fixed is not None and (_key(fixed) or (0,)) <= vkey:
            continue
        out.append(b)
    return out


# ── checks ────────────────────────────────────────────────────────────────


def _is_text(v: Any) -> bool:
    return isinstance(v, str) and bool(v.strip())


def _date_or_pending(v: Any) -> bool:
    return v == PENDING or (isinstance(v, str) and bool(_DATE.match(v)))


def _list_of_text(v: Any, *, may_be_empty: bool = True) -> bool:
    return isinstance(v, list) and (may_be_empty or bool(v)) and all(_is_text(x) for x in v)


def _check_ids(items: list[dict[str, Any]], prefix: str, what: str) -> list[str]:
    problems = []
    ids = [str(it.get("id")) for it in items]
    for n, iid in enumerate(ids, start=1):
        want = f"{prefix}-{n:04d}"
        if iid != want:
            problems.append(f"{what} #{n} is {iid!r}, expected {want}: ids run from "
                            f"{prefix}-0001 with none missing, reused or out of order")
            break
    return problems


def check_bug(reg: Registers, b: dict[str, Any]) -> list[str]:
    bid = b.get("id", "?")
    p: list[str] = []

    def bad(msg: str) -> None:
        p.append(f"{bid}: {msg}")

    missing = [k for k in BUG_KEYS if k not in b]
    extra = [k for k in b if k not in BUG_KEYS and k not in OPTIONAL_BUG_KEYS]
    if missing:
        bad(f"missing fields {missing}")
        return p
    if extra:
        bad(f"unknown fields {extra}")
    for k in ("title", "description", "reported_by"):
        if not _is_text(b[k]) or b[k] == PENDING:
            bad(f"{k} must be written (never pending)")
    for k in ("detected", "resolved", "closed"):
        if not _date_or_pending(b[k]):
            bad(f"{k} is a date (YYYY-MM-DD[THH:MM]) or 'pending'")
    v = b["found_in_version"]
    if v not in (PENDING, UNRELEASED, BEFORE_FIRST) and _key(v) is None:
        bad(f"found_in_version {v!r} is not a version, '{BEFORE_FIRST}', "
            f"'{UNRELEASED}' or 'pending'")
    if v not in (PENDING, UNRELEASED, BEFORE_FIRST) and reg.release(v) is None:
        bad(f"found_in_version {v} is not in the release register")
    build = b["found_in_build"]
    if build != PENDING and not (isinstance(build, str) and _SHA.match(build)):
        bad("found_in_build is a commit or 'pending'")
    if b["module"] not in MODULES:
        bad(f"module {b['module']!r} is not one of {sorted(MODULES)}")
    if not (b["steps"] == PENDING or _list_of_text(b["steps"], may_be_empty=False)):
        bad("steps is a list of steps or 'pending'")
    for k in ("expected", "observed", "root_cause", "verified_by", "verification"):
        if not _is_text(b[k]):
            bad(f"{k} is text or 'pending'")
    if b["severity"] not in SEVERITIES:
        bad(f"severity must be one of {SEVERITIES}")
    if b["priority"] not in PRIORITIES:
        bad(f"priority must be one of {PRIORITIES}")
    status = b["status"]
    if status not in STATUSES:
        bad(f"status must be one of {STATUSES}")
        return p
    if not _list_of_text(b["evidence"]):
        bad("evidence is a list of texts")
    if not isinstance(b["fixes"], list):
        bad("fixes is a list of FIX ids")
        return p
    fixes = []
    for fid in b["fixes"]:
        fx = reg.fix(fid)
        if fx is None:
            bad(f"names {fid}, which is not in the fix register")
        elif bid not in (fx.get("bugs") or []):
            bad(f"names {fid}, which does not name it back")
        else:
            fixes.append(fx)

    hist = b["history"]
    if not isinstance(hist, list) or not hist:
        bad("history has at least the entry that opened it")
        return p
    prev_status, prev_date = None, ""
    for n, h in enumerate(hist):
        if not isinstance(h, dict) or set(h) - {"date", "status", "note"} or "status" not in h:
            bad(f"history[{n}] is {{date, status, note}}")
            return p
        hs, hd = h.get("status"), h.get("date")
        if not _date_or_pending(hd):
            bad(f"history[{n}].date is a date or 'pending'")
        if hd != PENDING and prev_date and prev_date != PENDING and str(hd) < prev_date:
            bad(f"history[{n}] is dated before the step before it")
        if prev_status is None:
            if hs != "Open":
                bad("history starts with Open")
        elif hs not in TRANSITIONS.get(prev_status, ()):
            bad(f"history goes {prev_status} → {hs}, which is not allowed "
                f"(from {prev_status}: {', '.join(TRANSITIONS.get(prev_status, ()))})")
        prev_status, prev_date = hs, str(hd)
    if prev_status != status:
        bad(f"status is {status} but its history ends at {prev_status}")

    if status in ("Fixed", "Verified", "Closed"):
        if not fixes:
            bad(f"is {status} with no fix in the fix register")
        for fx in fixes:
            if not fx.get("commits"):
                bad(f"is {status} but {fx.get('id')} names no commit")
        if b["resolved"] == PENDING:
            bad(f"is {status} with no resolution date")
    if status in DONE:
        if b["verification"] == PENDING or b["verified_by"] == PENDING:
            bad(f"is {status} without saying how and by whom the fix was verified")
        if not any(fx.get("test_result") == "passed"
                   or fx.get("validation") in ("manual", "confirmed by user") for fx in fixes):
            bad(f"is {status} but no fix has a passed test or a manual/user verification")
    if status == "Closed":
        if b["closed"] == PENDING:
            bad("is Closed with no closing date")
        for fx in fixes:
            rel = reg.release(str(fx.get("version")))
            if rel is None or not _published(rel):
                bad(f"is Closed but {fx.get('id')} is not in a published release")
    elif b["closed"] != PENDING and status not in ("Reopened",):
        bad("has a closing date but is not Closed")
    if status == "Duplicate":
        other = reg.bug(str(b.get("duplicate_of")))
        if other is None or other is b or other.get("status") == "Duplicate":
            bad("is a Duplicate: duplicate_of names the main record (itself not a duplicate)")
    if status in ("Deferred", "Cannot Reproduce") and not _is_text(b.get("note")):
        bad(f"is {status}: note says why (and the conditions tried)")
    found = _key(str(v))
    for fx in fixes:
        fv = str(fx.get("version"))
        if found is not None and fv != UNRELEASED and (_key(fv) or (0,)) < found:
            bad(f"{fx.get('id')} is in {fv}, before the version the bug was found in ({v})")
    return p


def check_fix(reg: Registers, fx: dict[str, Any]) -> list[str]:
    fid = fx.get("id", "?")
    p: list[str] = []

    def bad(msg: str) -> None:
        p.append(f"{fid}: {msg}")

    missing = [k for k in FIX_KEYS if k not in fx]
    extra = [k for k in fx if k not in FIX_KEYS and k != "note"]
    if missing:
        bad(f"missing fields {missing}")
        return p
    if extra:
        bad(f"unknown fields {extra}")
    if not _list_of_text(fx["bugs"], may_be_empty=False):
        bad("bugs names at least one BUG id")
    for bid in fx["bugs"] or []:
        b = reg.bug(bid)
        if b is None:
            bad(f"names {bid}, which is not in the bug register")
        elif fid not in (b.get("fixes") or []):
            bad(f"names {bid}, which does not name it back")
    if not _date_or_pending(fx["date"]):
        bad("date is a date or 'pending'")
    for k in ("author", "root_cause", "solution", "regression_risk"):
        if not _is_text(fx[k]):
            bad(f"{k} is text or 'pending'")
    if fx["solution"] == PENDING:
        bad("solution says what was changed (never pending)")
    for k in ("components", "tests", "manual_checks"):
        if not _list_of_text(fx[k]):
            bad(f"{k} is a list of texts")
    if not isinstance(fx["commits"], list) or not all(
            isinstance(c, str) and _SHA.match(c) for c in fx["commits"]):
        bad("commits is a list of commit ids")
    version = fx["version"]
    if version != UNRELEASED and reg.release(str(version)) is None:
        bad(f"version {version!r} is '{UNRELEASED}' or a version in the release register")
    if fx["test_result"] not in FIX_RESULTS:
        bad(f"test_result must be one of {FIX_RESULTS}")
    if fx["validation"] not in VALIDATIONS:
        bad(f"validation must be one of {VALIDATIONS}")
    if fx["test_result"] == "passed" and not fx["tests"]:
        bad("test_result is passed but no test is named")
    return p


def check_release(reg: Registers, rel: dict[str, Any]) -> list[str]:
    ver = str(rel.get("version", "?"))
    p: list[str] = []

    def bad(msg: str) -> None:
        p.append(f"release {ver}: {msg}")

    missing = [k for k in RELEASE_KEYS if k not in rel]
    extra = [k for k in rel if k not in RELEASE_KEYS and k != "note"]
    if missing:
        bad(f"missing fields {missing}")
        return p
    if extra:
        bad(f"unknown fields {extra}")
    try:
        v = versioning.parse(ver)
    except ValueError as exc:
        bad(str(exc))
        return p
    if v.build:
        bad("a release is named without its build part")
    status = rel["status"]
    if status not in RELEASE_STATUSES:
        bad(f"status must be one of {RELEASE_STATUSES}")
    elif status in ("Development", "Beta", "RC", "Stable") and status != STAGE_STATUS[v.stage]:
        bad(f"is {status} but {ver} is a {STAGE_STATUS[v.stage]} version")
    if not _date_or_pending(rel["created"]):
        bad("created is a date or 'pending'")
    pub = rel["published"]
    if pub is not None and not _date_or_pending(pub):
        bad("published is a date, 'pending' or null (not published)")
    if status == "Not published" and pub is not None:
        bad("is Not published but has a publication date")
    if status in ("Beta", "RC", "Stable", "Superseded", "Withdrawn") and pub is None:
        bad(f"is {status} but was never published (published is null)")
    commit = rel["commit"]
    if commit != PENDING and not (isinstance(commit, str) and _SHA.match(commit)):
        bad("commit is a commit id or 'pending'")
    for k in ("build", "goal", "tests", "approved_by", "upgrade"):
        if not _is_text(rel[k]):
            bad(f"{k} is text or 'pending'")
    for k in ("artifacts", "features", "improvements", "breaking"):
        if not _list_of_text(rel[k]):
            bad(f"{k} is a list of texts")
    if not isinstance(rel["exceptions"], list):
        bad("exceptions is a list")
    else:
        for n, ex in enumerate(rel["exceptions"]):
            if not isinstance(ex, dict) or not all(
                    _is_text(ex.get(k)) for k in ("bug", "reason", "risk", "approved_by", "date")):
                bad(f"exceptions[{n}] says bug, reason, risk, approved_by and date")
            elif reg.bug(str(ex["bug"])) is None:
                bad(f"exceptions[{n}] names {ex['bug']}, which is not in the bug register")
    return p


def check_registers(reg: Registers, current_version: str | None = None) -> list[str]:
    p = _check_ids(reg.bugs, "BUG", "bug") + _check_ids(reg.fixes, "FIX", "fix")
    for b in reg.bugs:
        p += check_bug(reg, b)
    for fx in reg.fixes:
        p += check_fix(reg, fx)
    seen: set[str] = set()
    keys = []
    for rel in reg.releases:
        p += check_release(reg, rel)
        ver = str(rel.get("version"))
        if ver in seen:
            p.append(f"release {ver} is listed twice")
        seen.add(ver)
        keys.append(_key(ver) or (0,))
    if keys != sorted(keys):
        p.append("releases are listed oldest first")
    published = [r for r in reg.releases if _published(r)]
    for rel in published[:-1]:
        if rel.get("status") not in ("Superseded", "Withdrawn"):
            p.append(f"release {rel.get('version')} is {rel.get('status')} although a newer "
                     "one was published: it is Superseded (or Withdrawn)")
    if published and published[-1].get("status") == "Superseded":
        p.append(f"release {published[-1].get('version')} is the newest published: "
                 "it cannot be Superseded")
    if current_version is not None and reg.release(current_version) is None:
        p.append(f"the app's version {current_version} is not in the release register")
    return p


def check_commits(reg: Registers, repo: Path = ROOT) -> list[str]:
    """Each fix's commits exist, and a fix said to be in a release really is:
    its commits are ancestors of the release's commit (git)."""
    p = []

    def git(*args: str) -> bool:
        return subprocess.run(["git", "-C", str(repo), *args], stdin=subprocess.DEVNULL,
                              capture_output=True).returncode == 0

    for rel in reg.releases:
        c = rel.get("commit")
        if c and c != PENDING and not git("cat-file", "-e", f"{c}^{{commit}}"):
            p.append(f"release {rel.get('version')}: commit {c} is not in this repository")
    for fx in reg.fixes:
        rel = reg.release(str(fx.get("version")))
        for c in fx.get("commits") or []:
            if not git("cat-file", "-e", f"{c}^{{commit}}"):
                p.append(f"{fx.get('id')}: commit {c} is not in this repository")
            elif rel and rel.get("commit") not in (None, PENDING) and not git(
                    "merge-base", "--is-ancestor", c, str(rel["commit"])):
                p.append(f"{fx.get('id')}: commit {c} is not in {rel.get('version')} "
                         f"(not an ancestor of {rel['commit']})")
    return p


# ── logs ──────────────────────────────────────────────────────────────────


def _cell(text: Any) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def _val(v: Any) -> str:
    if v == PENDING:
        return "_pending_"
    if isinstance(v, list):
        return "; ".join(map(str, v)) if v else "—"
    return str(v) if v not in (None, "") else "—"


_HEAD = ("<!-- Generated from tracking/{src} by `python -m tools.tracking render`. "
         "Do not edit by hand: edit the JSON and render again. -->\n\n")


def bug_page(bug: dict[str, Any]) -> str:
    """Where a bug's full record is shown: one page per module, so no page grows
    too big to read (or for GitHub to render)."""
    return f"bugs/{bug.get('module', 'app')}.md"


def bug_link(reg: Registers, bid: str, base: str = "") -> str:
    bug = reg.bug(bid)
    page = bug_page(bug) if bug else "BUG_LOG.md"
    return f"[{bid}]({base}{page}#{bid.lower()})"


def render_bug_log(reg: Registers) -> str:
    out = [_HEAD.format(src="bugs.json"), "# Bug log\n\n",
           "Every bug found in RockForge, with a permanent id; the full record of each is on "
           "its module's page in [bugs/](bugs). Rules and states: "
           "[docs/VERSIONING.md](../docs/VERSIONING.md#bugs). "
           "Fixes: [FIX_LOG.md](FIX_LOG.md). Releases: [RELEASE_LOG.md](RELEASE_LOG.md).\n\n"]
    counts = {s: sum(1 for b in reg.bugs if b.get("status") == s) for s in STATUSES}
    out.append("| " + " | ".join(s for s in STATUSES if counts[s]) + " |\n")
    out.append("|" + "---|" * sum(1 for s in STATUSES if counts[s]) + "\n")
    out.append("| " + " | ".join(str(counts[s]) for s in STATUSES if counts[s]) + " |\n\n")
    out.append("| ID | Title | Module | Severity | Priority | Status | Found in | Fixed in |\n")
    out.append("|---|---|---|---|---|---|---|---|\n")
    for b in reg.bugs:
        out.append(f"| {bug_link(reg, b['id'])} | {_cell(b['title'])} | {b['module']} | "
                   f"{b['severity']} | {b['priority']} | {b['status']} | "
                   f"{_cell(b['found_in_version'])} | {_cell(fixed_in(reg, b) or '—')} |\n")
    return "".join(out)


def render_bug_pages(reg: Registers) -> dict[str, str]:
    pages: dict[str, list[str]] = {}
    for b in reg.bugs:
        page = bug_page(b)
        out = pages.setdefault(page, [
            _HEAD.format(src="bugs.json"),
            f"# Bugs: {b['module']}\n\n{MODULES.get(b['module'], '')}. "
            "Index: [BUG_LOG.md](../BUG_LOG.md).\n"])
        out.append(f"\n## {b['id']}\n\n**{_cell(b['title'])}**\n\n")
        rows = [
            ("Detected", b["detected"]), ("Reported by", b["reported_by"]),
            ("Found in", b["found_in_version"]), ("Build / commit", b["found_in_build"]),
            ("Severity", b["severity"]), ("Priority", b["priority"]), ("Status", b["status"]),
        ]
        if b.get("duplicate_of"):
            rows.append(("Duplicate of", b["duplicate_of"]))
        out.append("| | |\n|---|---|\n")
        out.extend(f"| {k} | {_cell(_val(v))} |\n" for k, v in rows)
        out.append(f"\n{b['description']}\n\n")
        steps = b["steps"]
        out.append("**Steps to reproduce:** " + ("_pending_\n" if steps == PENDING else "\n\n"
                   + "".join(f"{n}. {s}\n" for n, s in enumerate(steps, start=1))))
        out.append(f"\n**Expected:** {_val(b['expected'])}\n\n")
        out.append(f"**Observed:** {_val(b['observed'])}\n\n")
        out.append(f"**Root cause:** {_val(b['root_cause'])}\n\n")
        fixes = [reg.fix(f) for f in b["fixes"]]
        out.append("**Fixes:** " + (", ".join(
            f"[{fx['id']}](../FIX_LOG.md#{fx['id'].lower()}) ({_val(fx['version'])})"
            for fx in fixes if fx) or "—") + "\n\n")
        out.append(f"**Verified:** {_val(b['verification'])} (by {_val(b['verified_by'])})\n\n")
        out.append(f"**Resolved:** {_val(b['resolved'])} · **Closed:** {_val(b['closed'])}\n\n")
        if b.get("note"):
            out.append(f"**Note:** {b['note']}\n\n")
        if b["evidence"]:
            out.append("**Evidence:**\n\n" + "".join(f"- {e}\n" for e in b["evidence"]) + "\n")
        if b.get("links"):
            out.append("**Links:** " + ", ".join(b["links"]) + "\n\n")
        out.append("**History:**\n\n" + "".join(
            f"- {_val(h.get('date'))} — {h['status']}" + (f": {h['note']}" if h.get("note") else "")
            + "\n" for h in b["history"]))
    return {page: "".join(lines) for page, lines in pages.items()}


def render_fix_log(reg: Registers) -> str:
    out = [_HEAD.format(src="fixes.json"), "# Fix log\n\n",
           "Every change made to fix a bug. One fix may close several bugs and one bug may "
           "need several fixes. Bugs: [BUG_LOG.md](BUG_LOG.md).\n\n",
           "| ID | Bugs | Version | Tests | Validation |\n|---|---|---|---|---|\n"]
    for fx in reg.fixes:
        out.append(f"| [{fx['id']}](#{fx['id'].lower()}) | {', '.join(fx['bugs'])} | "
                   f"{_cell(fx['version'])} | {fx['test_result']} | {fx['validation']} |\n")
    for fx in reg.fixes:
        out.append(f"\n## {fx['id']}\n\n")
        out.append("**Bugs:** " + ", ".join(bug_link(reg, b) for b in fx["bugs"]) + "\n\n")
        out.append(f"**Root cause:** {_val(fx['root_cause'])}\n\n")
        out.append(f"**Solution:** {fx['solution']}\n\n")
        rows = [("Date", fx["date"]), ("By", fx["author"]), ("Version", fx["version"]),
                ("Commits", fx["commits"]), ("Components", fx["components"]),
                ("Tests", fx["tests"]), ("Manual checks", fx["manual_checks"]),
                ("Test result", fx["test_result"]), ("Validation", fx["validation"]),
                ("Regression risk", fx["regression_risk"])]
        out.append("| | |\n|---|---|\n")
        out.extend(f"| {k} | {_cell(_val(v))} |\n" for k, v in rows)
        if fx.get("note"):
            out.append(f"\n**Note:** {fx['note']}\n")
    return "".join(out)


def render_release_log(reg: Registers) -> str:
    out = [_HEAD.format(src="releases.json"), "# Release log\n\n",
           "Every version, newest first. What a version fixed and the bugs it still carried "
           "come from the bug and fix registers. Process: "
           "[docs/RELEASE_PROCESS.md](../docs/RELEASE_PROCESS.md).\n"]
    for rel in reversed(reg.releases):
        ver = rel["version"]
        out.append(f"\n## {ver}\n\n")
        rows = [("Status", rel["status"]), ("Created", rel["created"]),
                ("Published", "not published" if rel["published"] is None else rel["published"]),
                ("Commit", rel["commit"]), ("Build", rel["build"]),
                ("Artifacts", rel["artifacts"]), ("Tests", rel["tests"]),
                ("Approved by", rel["approved_by"])]
        out.append("| | |\n|---|---|\n")
        out.extend(f"| {k} | {_cell(_val(v))} |\n" for k, v in rows)
        out.append(f"\n**Goal:** {rel['goal']}\n\n")
        for title, key in (("New", "features"), ("Improved", "improvements"),
                           ("Breaking changes / migrations", "breaking")):
            if rel[key]:
                out.append(f"**{title}:**\n\n" + "".join(f"- {x}\n" for x in rel[key]) + "\n")
        fixed = bugs_fixed_in(reg, ver)
        out.append("**Bugs fixed:** " + ("—\n\n" if not fixed else "\n\n" + "".join(
            f"- {bug_link(reg, b['id'])} {b['title']}\n" for b in fixed) + "\n"))
        known = known_open_at(reg, ver)
        out.append("**Known bugs it carried:** " + ("—\n\n" if not known else "\n\n" + "".join(
            f"- {bug_link(reg, b['id'])} {b['title']} "
            f"({b['severity']}, now {b['status']})\n" for b in known) + "\n"))
        if rel["exceptions"]:
            out.append("**Approved exceptions:**\n\n" + "".join(
                f"- {e['bug']}: {e['reason']} Risk: {e['risk']} "
                f"(approved by {e['approved_by']}, {e['date']})\n" for e in rel["exceptions"])
                + "\n")
        out.append(f"**Update / rollback:** {_val(rel['upgrade'])}\n")
        if rel.get("note"):
            out.append(f"\n**Note:** {rel['note']}\n")
    return "".join(out)


def rendered(reg: Registers) -> dict[str, str]:
    """Every generated page, by its path under tracking/."""
    return {"BUG_LOG.md": render_bug_log(reg), **render_bug_pages(reg),
            "FIX_LOG.md": render_fix_log(reg), "RELEASE_LOG.md": render_release_log(reg)}


def render(reg: Registers, folder: Path = TRACKING) -> None:
    pages = rendered(reg)
    (folder / "bugs").mkdir(exist_ok=True)
    for old in (folder / "bugs").glob("*.md"):
        if f"bugs/{old.name}" not in pages:
            old.unlink()
    for name, text in pages.items():
        (folder / name).write_text(text, encoding="utf-8")


def stale_logs(reg: Registers, folder: Path = TRACKING) -> list[str]:
    pages = rendered(reg)
    stale = [name for name, text in pages.items()
             if not (folder / name).exists()
             or (folder / name).read_text(encoding="utf-8") != text]
    extra = [f"bugs/{p.name}" for p in (folder / "bugs").glob("*.md")
             if f"bugs/{p.name}" not in pages] if (folder / "bugs").exists() else []
    return stale + extra


# ── editing ───────────────────────────────────────────────────────────────


def today() -> str:
    return dt.date.today().isoformat()


def new_bug(reg: Registers, title: str, *, module: str, severity: str, priority: str,
            found_in: str, reported_by: str, description: str | None = None) -> dict[str, Any]:
    bug: dict[str, Any] = {
        "id": f"BUG-{len(reg.bugs) + 1:04d}", "title": title, "detected": today(),
        "reported_by": reported_by, "found_in_version": found_in, "found_in_build": PENDING,
        "module": module, "description": description or title, "steps": PENDING,
        "expected": PENDING, "observed": PENDING, "severity": severity, "priority": priority,
        "status": "Open", "root_cause": PENDING, "fixes": [], "verified_by": PENDING,
        "verification": PENDING, "evidence": [], "resolved": PENDING, "closed": PENDING,
        "history": [{"date": today(), "status": "Open", "note": "reported"}],
    }
    reg.bugs.append(bug)
    return bug


def set_status(bug: dict[str, Any], status: str, note: str = "", date: str | None = None) -> None:
    when = date or today()
    if status not in TRANSITIONS.get(bug["status"], ()):
        raise ValueError(f"{bug['id']}: {bug['status']} → {status} is not allowed")
    bug["history"].append({"date": when, "status": status, **({"note": note} if note else {})})
    bug["status"] = status
    if status == "Fixed" and bug["resolved"] == PENDING:
        bug["resolved"] = when
    if status == "Closed":
        bug["closed"] = when
    if status == "Reopened":
        bug["closed"] = PENDING


def main(argv: list[str] | None = None) -> int:
    from rockforge import __version__

    ap = argparse.ArgumentParser(prog="python -m tools.tracking")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check")
    sub.add_parser("render")
    nb = sub.add_parser("new-bug")
    nb.add_argument("title")
    nb.add_argument("--module", required=True, choices=sorted(MODULES))
    nb.add_argument("--severity", required=True, choices=SEVERITIES)
    nb.add_argument("--priority", required=True, choices=PRIORITIES)
    nb.add_argument("--found-in", default=__version__)
    nb.add_argument("--reported-by", default="maintainer")
    st = sub.add_parser("status")
    st.add_argument("bug")
    st.add_argument("status", choices=STATUSES)
    st.add_argument("note", nargs="?", default="")
    nt = sub.add_parser("notes")
    nt.add_argument("version")
    args = ap.parse_args(argv)

    reg = load()
    if args.cmd == "check":
        problems = check_registers(reg, __version__)
        in_ci = os.environ.get("CI") == "true"
        if (ROOT / ".git").exists() or in_ci:
            problems += check_commits(reg)
        problems += [f"{n} is out of date: python -m tools.tracking render"
                     for n in stale_logs(reg)]
        for line in problems:
            print(line)
        print(f"{len(reg.bugs)} bugs, {len(reg.fixes)} fixes, {len(reg.releases)} releases: "
              + ("OK" if not problems else f"{len(problems)} problem(s)"))
        return 1 if problems else 0
    if args.cmd == "render":
        render(reg)
        return 0
    if args.cmd == "new-bug":
        b = new_bug(reg, args.title, module=args.module, severity=args.severity,
                    priority=args.priority, found_in=args.found_in, reported_by=args.reported_by)
        save(reg)
        render(reg)
        print(b["id"])
        return 0
    if args.cmd == "status":
        b = reg.bug(args.bug)
        if b is None:
            print(f"no {args.bug}")
            return 1
        set_status(b, args.status, args.note)
        save(reg)
        render(reg)
        return 0
    if args.cmd == "notes":
        for b in bugs_fixed_in(reg, args.version):
            print(f"- {b['title']} ({b['id']})")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
