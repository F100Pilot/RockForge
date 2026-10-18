"""The opt-in install counter (``infrastructure/install_counter.py``): nothing
leaves before a yes, one ping per version, a no forgets."""

from __future__ import annotations

import importlib
import json
import uuid
from typing import Any

import pytest

from rockforge import __version__

URL = "https://counter.example/functions/v1/install-ping"


@pytest.fixture
def counter(tmp_path, monkeypatch):
    monkeypatch.setenv("ROCKFORGE_WORK_DIR", str(tmp_path))
    monkeypatch.setenv("ROCKFORGE_INSTALL_COUNTER_URL", URL)
    from rockforge import config

    importlib.reload(config)
    from rockforge.infrastructure import install_counter

    sent: list[tuple[str, dict[str, Any]]] = []

    def fail(*_a: Any, **_k: Any) -> None:
        raise AssertionError("the real network was reached")

    monkeypatch.setattr(install_counter, "_post", fail)
    return install_counter, sent, lambda target, body: sent.append((target, body))


def test_nothing_is_sent_before_the_user_answers(counter) -> None:
    ic, sent, sender = counter
    assert ic.status() == {"available": True, "enabled": None}
    assert ic.send_if_due(sender=sender) is False
    assert sent == []


def test_yes_sends_this_version_once_with_only_what_is_said(counter) -> None:
    ic, sent, sender = counter
    assert ic.set_enabled(True, sender=sender, background=False) == {
        "available": True, "enabled": True}
    assert len(sent) == 1
    target, body = sent[0]
    assert target == URL
    assert set(body) == {"install_id", "version", "kind", "os"}
    assert uuid.UUID(body["install_id"]).version == 4
    assert body["version"] == __version__
    assert body["kind"] in {"exe", "git", "source"}
    assert body["os"] in {"windows", "macos", "linux", "other"}
    # the next start, the same version: nothing more
    assert ic.send_if_due(sender=sender) is False
    assert len(sent) == 1


def test_a_new_version_is_sent_again_with_the_same_id(counter, monkeypatch) -> None:
    ic, sent, sender = counter
    ic.set_enabled(True, sender=sender, background=False)
    monkeypatch.setattr(ic, "__version__", "99.0.0")
    assert ic.send_if_due(sender=sender) is True
    assert [b["install_id"] for _, b in sent] == [sent[0][1]["install_id"]] * 2


def test_a_failed_send_is_retried_on_the_next_start(counter) -> None:
    ic, sent, sender = counter

    def offline(*_a: Any) -> None:
        raise OSError("offline")

    ic.set_enabled(True, sender=offline, background=False)
    assert ic.send_if_due(sender=sender) is True
    assert len(sent) == 1


def test_no_forgets_the_id_and_asks_the_server_to_delete_it(counter, tmp_path) -> None:
    ic, sent, sender = counter
    ic.set_enabled(True, sender=sender, background=False)
    first = sent[0][1]["install_id"]
    assert ic.set_enabled(False, sender=sender, background=False)["enabled"] is False
    assert sent[-1] == (URL, {"action": "forget", "install_id": first})
    assert json.loads((tmp_path / "install_counter.json").read_text()) == {"consent": False}
    assert ic.send_if_due(sender=sender) is False
    # yes again: a NEW id, sent again
    ic.set_enabled(True, sender=sender, background=False)
    assert sent[-1][1]["install_id"] not in (first, None)


def test_with_no_url_the_counter_is_off(counter, monkeypatch) -> None:
    ic, sent, sender = counter
    monkeypatch.setattr(ic.config.settings, "install_counter_url", "")
    ic.set_enabled(True, sender=sender, background=False)
    assert ic.status()["available"] is False
    assert sent == []


def test_the_api_asks_nothing_until_answered_and_records_the_answer(
    tmp_path, monkeypatch
) -> None:
    from fastapi.testclient import TestClient

    monkeypatch.setenv("ROCKFORGE_DATABASE_URL", f"sqlite:///{tmp_path}/test.db")
    monkeypatch.setenv("ROCKFORGE_WORK_DIR", str(tmp_path / "work"))
    monkeypatch.setenv("ROCKFORGE_INSTALL_COUNTER_URL", "")
    from rockforge import config

    importlib.reload(config)
    import rockforge.interfaces.api.app as app_module

    importlib.reload(app_module)
    from rockforge.infrastructure import install_counter

    calls: list[bool] = []
    monkeypatch.setattr(install_counter, "send_in_background", lambda: calls.append(True))
    with TestClient(app_module.app) as c:
        # off in this install (no URL): not offered, and a yes is refused
        assert c.get("/install-count").json() == {"available": False, "enabled": None}
        assert c.put("/install-count", json={"enabled": True}).status_code == 404
        monkeypatch.setattr(config.settings, "install_counter_url", URL)
        assert c.get("/install-count").json() == {"available": True, "enabled": None}
        answers: list[bool] = []
        monkeypatch.setattr(install_counter, "set_enabled",
                            lambda enabled: answers.append(enabled) or
                            {"available": True, "enabled": enabled})
        assert c.put("/install-count", json={"enabled": False}).json()["enabled"] is False
        assert c.put("/install-count", json={"enabled": "talvez"}).status_code == 422
        assert answers == [False]
    assert calls == [True]  # the startup send was asked for (it decides itself)
