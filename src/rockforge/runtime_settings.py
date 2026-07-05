"""Runtime-editable settings (set from the app's "Definições" UI), persisted to
``work_dir/settings.json`` so both the API and the Celery worker read the same
values without an env-var/restart. Any key not overridden here falls back to the
env-based :class:`Settings`.

Kept deliberately small: only the stem-separator backend + Banquet paths for now
(the rest of `Settings` stays env-only). Writes are atomic (temp + os.replace)
so a worker reading mid-write never sees a truncated file.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from rockforge.config import settings

_KEYS = ("stem_separator", "banquet_repo", "banquet_ckpt", "banquet_queries")


def _file() -> Path:
    return settings.work_dir / "settings.json"


def load() -> dict[str, Any]:
    try:
        data = json.loads(_file().read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (FileNotFoundError, ValueError, OSError):
        return {}


def save(overrides: dict[str, Any]) -> dict[str, Any]:
    """Persist only the known keys (empty string / None clears an override,
    falling back to the env default). Returns the stored dict."""
    data = {
        k: overrides[k]
        for k in _KEYS
        if k in overrides and overrides[k] not in (None, "")
    }
    f = _file()
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_name(f.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.replace(tmp, f)
    return data


def _eff(key: str, env_default: Any) -> Any:
    val = load().get(key)
    return val if val not in (None, "") else env_default


def stem_separator() -> str:
    return str(_eff("stem_separator", settings.stem_separator))


def _path(key: str, env_default: Path | None) -> Path | None:
    val = _eff(key, str(env_default) if env_default else None)
    return Path(str(val)) if val else None


def banquet_paths() -> tuple[Path | None, Path | None, Path | None]:
    """Effective (repo, ckpt, queries) — runtime override, else env, else None."""
    return (
        _path("banquet_repo", settings.banquet_repo),
        _path("banquet_ckpt", settings.banquet_ckpt),
        _path("banquet_queries", settings.banquet_queries),
    )


def banquet_validation() -> dict[str, Any]:
    """Per-path readiness for the UI: does the repo have train.py, the ckpt
    exist, and the queries dir hold at least one <class>.wav?"""
    repo, ckpt, queries = banquet_paths()
    query_names = (
        sorted(p.stem for p in queries.glob("*.wav"))
        if queries and queries.is_dir()
        else []
    )
    repo_ok = bool(repo and (repo / "train.py").exists())
    ckpt_ok = bool(ckpt and ckpt.exists())
    return {
        "repo_ok": repo_ok,
        "ckpt_ok": ckpt_ok,
        "queries_ok": bool(query_names),
        "query_names": query_names,
        "ready": repo_ok and ckpt_ok and bool(query_names),
    }
