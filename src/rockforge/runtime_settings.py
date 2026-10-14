"""Runtime-editable settings (set from the app's "Definições" UI), persisted to
``work_dir/settings.json`` so both the API and the Celery worker read the same
values without an env-var/restart. Any key not overridden here falls back to the
env-based :class:`Settings`.

Kept deliberately small: the stem-separator backend, the Banquet paths and the
ML interpreter for now
(the rest of `Settings` stays env-only). Writes are atomic (temp + os.replace)
so a worker reading mid-write never sees a truncated file.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from rockforge import config

_KEYS = (
    "stem_separator", "banquet_repo", "banquet_ckpt", "banquet_queries",
    "loudness_target", "whisperx_compute_type", "ml_python", "ui_language",
    "rocksmith_dlc_dir", "rocksmith_dir",
)

# The loudness (LUFS) the audio is normalized to AND the target the Wwise bus
# volume is calibrated to — one value so the .wem and the volume stay in step.
# -16 (broadcast/EBU R128) read too quiet next to retail Rocksmith DLC, which
# ships loud music masters (DLC Builder's "Calculate Volumes" lands around -3/-4
# dB of attenuation on such a master); -12 is a louder music-game level. Editable
# in the UI ("⚙️ Definições") — push toward -10/-9 if still quiet, back toward
# -14 if it pumps. Clamped to a sane window.
DEFAULT_LOUDNESS_TARGET = -12.0
_LOUDNESS_MIN, _LOUDNESS_MAX = -20.0, -6.0


def _file() -> Path:
    return config.settings.work_dir / "settings.json"


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
    # A UNIQUE temp name, not a fixed "<file>.tmp": the API and the worker both
    # write here, and with a shared name two concurrent writers interleave —
    # A creates it, B overwrites it, A renames it into place and publishes B's
    # content. os.replace is still what makes the swap atomic for readers.
    fd, tmp_name = tempfile.mkstemp(dir=f.parent, prefix=f.name + ".", suffix=".tmp")
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(data, indent=2))
        os.replace(tmp, f)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    return data


def _eff(key: str, env_default: Any) -> Any:
    val = load().get(key)
    return val if val not in (None, "") else env_default


def ui_language() -> str:
    """The language the user picked for the app ("pt" by default). The browser
    sends its own with every request (``X-RockForge-Lang``); this is what the
    worker and the desktop window use, where there is no request to read."""
    from rockforge import i18n

    val = load().get("ui_language")
    return val if isinstance(val, str) and i18n.valid(val) else i18n.DEFAULT


def stem_separator() -> str:
    return str(_eff("stem_separator", config.settings.stem_separator))


def whisperx_compute_type() -> str:
    """Effective ctranslate2 compute type for WhisperX ("" = pick by device).
    A runtime override (persisted automatically when the GPU escalation finds a
    working compute type, e.g. int8_float16 on a Turing GPU) wins over the env
    ``ROCKFORGE_WHISPERX_COMPUTE_TYPE``."""
    return str(_eff("whisperx_compute_type", config.settings.whisperx_compute_type or ""))


def loudness_target() -> float:
    """Effective loudness/volume target (LUFS), clamped to a safe window. Both
    the recording's linear gain and the Wwise volume calibration read this."""
    val = load().get("loudness_target")
    try:
        target = DEFAULT_LOUDNESS_TARGET if val in (None, "") else float(val)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        target = DEFAULT_LOUDNESS_TARGET
    return max(_LOUDNESS_MIN, min(_LOUDNESS_MAX, target))


def _path(key: str, env_default: Path | None) -> Path | None:
    val = _eff(key, str(env_default) if env_default else None)
    return Path(str(val)) if val else None


def banquet_paths() -> tuple[Path | None, Path | None, Path | None]:
    """Effective (repo, ckpt, queries) — runtime override, else env, else None."""
    return (
        _path("banquet_repo", config.settings.banquet_repo),
        _path("banquet_ckpt", config.settings.banquet_ckpt),
        _path("banquet_queries", config.settings.banquet_queries),
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


def ml_python() -> Path | None:
    """The interpreter the heavy ML stages run on, or None for "this one".

    Editable in the UI because the standalone `.exe` has no other way to reach
    an ML install: its own interpreter is the executable. See
    ``infrastructure/ml_python.py`` for why every stage can run out-of-process.
    """
    return _path("ml_python", config.settings.ml_python)


def ml_python_validation() -> dict[str, Any]:
    """Readiness of the ML interpreter, for the UI's per-extra ✓/✗.

    Reads ``ml_python.availability()`` — the same source the ⚙️ diagnostics
    rows use, so the two halves of the same modal cannot contradict each other,
    and so this never spawns a probe just to ask THIS process what it can
    import. It also never imports torch: when the answer does need another
    interpreter, that interpreter is asked in a subprocess.
    """
    from rockforge.infrastructure import ml_python as _mlpy

    found = _mlpy.availability()
    return {
        "path": str(found["interpreter"]) if found["external"] else "",
        "frozen": _mlpy.frozen(),
        # False for a path that is not a working interpreter at all, which is a
        # different fix from "it runs but has no demucs".
        "python_ok": bool(found["python"]),
        "ml_ok": bool(found["demucs"] and found["librosa"]),
        "lyrics_ok": bool(found["whisperx"]),
        "torch_ok": bool(found["torch"]),
    }
