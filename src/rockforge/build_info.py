"""Which build of RockForge is this: version, commit, build id and date.

The version names the release (features and fixes); the build names the code it
was made from. Two people on "0.10.0 beta 12" can be on different code — a git
checkout moves on after a release — and only the commit tells them apart, so it
goes wherever the version goes: the page's corner, Definições, the start of
every log, error reports.

- The ``.exe``: ``build_info.json``, written by ``rockforge.spec`` when the
  bundle is made (the commit, the CI run, the time).
- A git checkout (``start.bat``): asked of git, once.
- Anything else (a zip of the source): only the version is known, and it says so.

Never raises: a diagnostics line that cannot be read must not stop the app.
"""

from __future__ import annotations

import datetime as dt
import functools
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from rockforge import __version__, versioning

FILE_NAME = "build_info.json"
_REPO = Path(__file__).resolve().parents[2]


def _git(*args: str, repo: Path = _REPO) -> str | None:
    try:
        out = subprocess.run(
            ["git", "-C", str(repo), *args], stdin=subprocess.DEVNULL,
            capture_output=True, text=True, timeout=5, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def collect(repo: Path = _REPO, env: dict[str, str] | None = None) -> dict[str, Any]:
    """What a bundle records about itself, at build time (rockforge.spec)."""
    env = dict(os.environ) if env is None else env
    commit = _git("rev-parse", "HEAD", repo=repo) or ""
    dirty = bool(_git("status", "--porcelain", "--untracked-files=no", repo=repo))
    run = env.get("GITHUB_RUN_NUMBER", "")
    return {
        "version": __version__,
        "commit": commit,
        "dirty": dirty and bool(commit),
        "build_id": f"ci.{run}" if run else "local",
        "built_at": dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "ci_run_url": (
            f"{env.get('GITHUB_SERVER_URL', 'https://github.com')}/"
            f"{env['GITHUB_REPOSITORY']}/actions/runs/{env['GITHUB_RUN_ID']}"
            if env.get("GITHUB_REPOSITORY") and env.get("GITHUB_RUN_ID") else ""
        ),
    }


def _bundled_file() -> Path | None:
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return Path(base) / "rockforge" / FILE_NAME
    here = Path(__file__).resolve().parent / FILE_NAME
    return here if here.exists() else None


@functools.cache
def build_info() -> dict[str, Any]:
    try:
        return _build_info()
    except Exception:  # noqa: BLE001 — never let identification break the app
        return {"version": __version__, "display": __version__, "full": __version__,
                "commit": "", "commit_short": "", "dirty": False, "build_id": "",
                "built_at": "", "source": "unknown", "ci_run_url": ""}


def _build_info() -> dict[str, Any]:
    info: dict[str, Any] = {"commit": "", "dirty": False, "build_id": "", "built_at": "",
                            "ci_run_url": ""}
    bundled = _bundled_file()
    if bundled is not None and bundled.exists():
        data = json.loads(bundled.read_text(encoding="utf-8"))
        info.update({k: data.get(k, info[k]) for k in info})
        info["source"] = "exe" if getattr(sys, "frozen", False) else "bundle"
    elif (_REPO / ".git").exists() and (commit := _git("rev-parse", "HEAD")):
        info["commit"] = commit
        info["dirty"] = bool(_git("status", "--porcelain", "--untracked-files=no"))
        info["built_at"] = _git("log", "-1", "--format=%cI") or ""
        info["build_id"] = "git"
        info["source"] = "git"
    else:
        info["source"] = "source"
    short = str(info["commit"])[:10]
    parts = [p for p in (
        str(info["build_id"]) if info["build_id"] not in ("", "git") else "",
        short, "dirty" if info["dirty"] else "",
    ) if p]
    v = versioning.parse(__version__)
    full = str(v) + ("+" + ".".join(parts) if parts else "")
    return {"version": __version__, "display": versioning.display(v), "full": full,
            "commit_short": short, **info}


def summary() -> str:
    """One line for the top of a log or an error report."""
    b = build_info()
    bits = [f"RockForge {b['full']}", f"source {b['source']}"]
    if b["built_at"]:
        bits.append(f"{'committed' if b['source'] == 'git' else 'built'} {b['built_at']}")
    return ", ".join(bits)
