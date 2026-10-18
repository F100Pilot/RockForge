"""How many people use RockForge — counted only for those who agree.

GitHub shows downloads, not installs (a `git clone` or a re-download counts
the same as a new user), so the app can, with the user's word, say "this
install reached this version" once per version. Nothing is sent before the
user answers "yes" (Definições → Geral, or the one question on the home page),
and what is sent is:

- a random id this install made up (``uuid4``) — not derived from the machine,
  the account or anything else, and thrown away when the user says no;
- the RockForge version, how it was installed (exe / git / source) and the
  operating-system family (windows / macos / linux / other).

The server (``supabase/functions/install-ping``) keeps exactly that, no IP.
Turning it off asks the server to delete what this install sent. Every
failure — offline, the server gone — is silent and retried on the next start:
a counter must never be something the user notices.

The state lives in ``work_dir/install_counter.json``, not ``settings.json``,
which the Definições page rewrites whole on every save.
"""

from __future__ import annotations

import json
import logging
import platform
import threading
import urllib.request
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

from rockforge import __version__, config
from rockforge._atomic import write_text_atomic

logger = logging.getLogger(__name__)

TIMEOUT_S = 10.0
_USER_AGENT = f"RockForge/{__version__} (install counter)"
_lock = threading.Lock()

Sender = Callable[[str, dict[str, Any]], None]


def url() -> str:
    return (config.settings.install_counter_url or "").strip()


def _file() -> Path:
    return config.settings.work_dir / "install_counter.json"


def _load() -> dict[str, Any]:
    try:
        data = json.loads(_file().read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save(state: dict[str, Any]) -> None:
    write_text_atomic(_file(), json.dumps(state, indent=2))


def os_family() -> str:
    return {"Windows": "windows", "Darwin": "macos", "Linux": "linux"}.get(
        platform.system(), "other")


def status() -> dict[str, Any]:
    """``enabled``: True / False once the user answered, None before."""
    consent = _load().get("consent")
    return {
        "available": bool(url()),
        "enabled": consent if isinstance(consent, bool) else None,
    }


def _post(target: str, payload: dict[str, Any]) -> None:
    from rockforge.infrastructure._https import ssl_context

    request = urllib.request.Request(
        target, data=json.dumps(payload).encode("utf-8"), method="POST",
        headers={"Content-Type": "application/json", "User-Agent": _USER_AGENT},
    )
    with urllib.request.urlopen(request, timeout=TIMEOUT_S, context=ssl_context()):
        pass  # urlopen raises on 4xx/5xx


def payload() -> dict[str, Any]:
    from rockforge.infrastructure.update_check import install_kind

    state = _load()
    return {
        "install_id": str(state.get("install_id") or ""),
        "version": __version__,
        "kind": install_kind(),
        "os": os_family(),
    }


def send_if_due(*, sender: Sender | None = None) -> bool:
    """Send this version once, if the user agreed. True when it was sent now."""
    target = url()
    with _lock:
        state = _load()
        if state.get("consent") is not True or not target or not state.get("install_id"):
            return False
        if state.get("sent_version") == __version__:
            return False
        try:
            (sender or _post)(target, payload())
        except Exception as exc:  # noqa: BLE001 — offline / server gone: next start
            logger.info("install counter: not sent (%s)", type(exc).__name__)
            return False
        state = _load()
        if state.get("consent") is True:  # not turned off while it was sending
            _save({**state, "sent_version": __version__})
        return True


def set_enabled(enabled: bool, *, sender: Sender | None = None,
                background: bool = True) -> dict[str, Any]:
    """Record the user's answer. Yes: make an id and send this version. No:
    forget the id and ask the server to delete what it sent."""
    with _lock:
        state = _load()
        old_id = str(state.get("install_id") or "")
        if enabled:
            _save({"consent": True, "install_id": old_id or str(uuid.uuid4()),
                   "sent_version": state.get("sent_version") if old_id else None})
        else:
            _save({"consent": False})

    def work() -> None:
        if enabled:
            send_if_due(sender=sender)
        elif old_id and url():
            try:
                (sender or _post)(url(), {"action": "forget", "install_id": old_id})
            except Exception as exc:  # noqa: BLE001
                logger.info("install counter: forget not sent (%s)", type(exc).__name__)

    if background:
        threading.Thread(target=work, name="install-counter", daemon=True).start()
    else:
        work()
    return status()


def send_in_background() -> None:
    """At startup: send this version if the user agreed and it was not sent."""
    if _load().get("consent") is True and url():
        threading.Thread(target=send_if_due, name="install-counter", daemon=True).start()
