"""Is there a newer RockForge than this one? (GitHub Releases)

`start.bat` updates a git checkout on every start (`git pull`), so only an
install that CANNOT update itself is told about a new version: the `.exe`
(installer or portable zip) and a source folder downloaded as a zip, which has
no `.git` for `start.bat` to pull into. A git checkout is never nagged.

One request to the GitHub API at most once a day (cached in
``work_dir/update_check.json``), nothing sent but the request itself, and the
user can turn it off in Definições. Every failure — offline, rate-limited, a
changed answer — is an empty result, never an error the user sees: an update
notice that breaks something would be worse than none.

Pre-releases are offered only to someone already on a pre-release: a beta
tester wants the next beta, someone on a final version does not.
"""

from __future__ import annotations

import json
import re
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from rockforge import __version__

REPO = "F100Pilot/RockForge"
RELEASES_API = f"https://api.github.com/repos/{REPO}/releases?per_page=20"
RELEASES_PAGE = f"https://github.com/{REPO}/releases"
CHECK_EVERY_S = 24 * 3600
RETRY_AFTER_FAILURE_S = 3600  # offline: do not spend a timeout on every page load
TIMEOUT_S = 8.0
_USER_AGENT = f"RockForge/{__version__} (update check)"

# "0.10.0b3" (PEP 440, __version__), "v0.10.0-beta.4" / "0.10.0-beta.4" (tags),
# "1.0.0rc1", "1.0.0".
_VERSION = re.compile(
    r"^v?(\d+)\.(\d+)\.(\d+)(?:[-.]?(a|alpha|b|beta|rc)\.?(\d+))?$", re.IGNORECASE
)
_STAGE = {"a": 0, "alpha": 0, "b": 1, "beta": 1, "rc": 2}


def parse_version(text: str) -> tuple[int, int, int, int, int] | None:
    """A sortable key, or None for anything that is not a version. A final
    release sorts after every pre-release of the same number."""
    m = _VERSION.match(text.strip())
    if not m:
        return None
    major, minor, patch = (int(m.group(i)) for i in (1, 2, 3))
    if m.group(4) is None:
        return (major, minor, patch, 3, 0)
    return (major, minor, patch, _STAGE[m.group(4).lower()], int(m.group(5)))


def is_prerelease(text: str) -> bool:
    key = parse_version(text)
    return key is not None and key[3] < 3


def install_kind(root: Path | None = None) -> str:
    """"exe", "git" (a checkout start.bat updates) or "source" (a folder with no
    git to update it)."""
    if getattr(sys, "frozen", False):
        return "exe"
    base = root if root is not None else Path(__file__).resolve().parents[3]
    return "git" if (base / ".git").exists() else "source"


@dataclass(frozen=True)
class UpdateInfo:
    current: str
    latest: str = ""
    newer: bool = False
    url: str = RELEASES_PAGE
    kind: str = "exe"
    checked_at: float = 0.0


def newest_release(releases: Any, current: str) -> tuple[str, str] | None:
    """(tag, page) of the newest release the user of ``current`` should be
    offered, from the GitHub API's list. Drafts and anything without a version
    tag are skipped; pre-releases only for someone on a pre-release."""
    if not isinstance(releases, list):
        return None
    allow_pre = is_prerelease(current)
    best: tuple[tuple[int, int, int, int, int], str, str] | None = None
    for rel in releases:
        if not isinstance(rel, dict) or rel.get("draft"):
            continue
        tag = str(rel.get("tag_name") or "")
        key = parse_version(tag)
        if key is None or (key[3] < 3 and not allow_pre):
            continue
        if best is None or key > best[0]:
            url = str(rel.get("html_url") or f"{RELEASES_PAGE}/tag/{tag}")
            best = (key, tag, url)
    return (best[1], best[2]) if best else None


def _fetch() -> Any:
    from rockforge.infrastructure._https import get_json

    return get_json(
        RELEASES_API, user_agent=_USER_AGENT, timeout=TIMEOUT_S,
        error=RuntimeError, service=("GitHub", "GitHub"),
    )


def _cache_file() -> Path:
    from rockforge import config

    return config.settings.work_dir / "update_check.json"


def check(*, fetch: Any = None, now: float | None = None, force: bool = False,
          kind: str | None = None) -> UpdateInfo:
    """What the UI shows. Cached for a day; a failure keeps the last answer."""
    current = __version__
    kind = kind or install_kind()
    now = time.time() if now is None else now
    cache: dict[str, Any] = {}
    try:
        loaded = json.loads(_cache_file().read_text(encoding="utf-8"))
        cache = loaded if isinstance(loaded, dict) else {}
    except (OSError, ValueError):
        cache = {}
    fresh = (
        cache.get("current") == current
        and now - float(cache.get("checked_at") or 0) < CHECK_EVERY_S
    )
    failed_at = cache.get("failed_at")
    backing_off = failed_at is not None and now - float(failed_at) < RETRY_AFTER_FAILURE_S
    if force or not (fresh or backing_off):
        try:
            found = newest_release((fetch or _fetch)(), current)
        except Exception:  # noqa: BLE001 — offline / rate-limited: keep what we had
            cache = {**cache, "failed_at": now}
        else:
            cache = {"current": current, "checked_at": now,
                     "latest": found[0] if found else "", "url": found[1] if found else ""}
        try:
            path = _cache_file()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(cache), encoding="utf-8")
        except OSError:
            pass
    latest = str(cache.get("latest") or "") if cache.get("current") == current else ""
    cur_key, new_key = parse_version(current), parse_version(latest)
    newer = bool(cur_key and new_key and new_key > cur_key)
    return UpdateInfo(
        current=current, latest=latest, newer=newer,
        url=str(cache.get("url") or RELEASES_PAGE) if newer else RELEASES_PAGE,
        kind=kind, checked_at=float(cache.get("checked_at") or 0),
    )


def as_dict(info: UpdateInfo) -> dict[str, Any]:
    return asdict(info)
