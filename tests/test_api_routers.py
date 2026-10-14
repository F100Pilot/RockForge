"""The endpoint groups in interfaces/api/routers/ read app.py's shared state
only as ``api.<name>``, looked up when a request runs.

The API tests reload app.py and replace its ``settings``, ``_session_factory``
and ``_enqueue*`` (``monkeypatch.setattr(app_module, …)``). A router that bound
one of those at import — ``from …api.app import _enqueue`` or
``from rockforge.config import settings`` — would keep the original, and a
patch that no longer intercepts does not fail: the test simply runs the real
code. So a router never imports a name from app.py or the settings object
directly; the models it needs come from schemas.py, which nothing reloads.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

API_DIR = Path(__file__).resolve().parents[1] / "src" / "rockforge" / "interfaces" / "api"
ROUTERS = sorted(p for p in (API_DIR / "routers").glob("*.py") if p.name != "__init__.py")


def test_there_are_routers_to_check() -> None:
    assert ROUTERS


@pytest.mark.parametrize("path", ROUTERS, ids=lambda p: p.name)
def test_a_router_reaches_app_state_only_through_the_app_module(path: Path) -> None:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert node.module != "rockforge.interfaces.api.app", (
                f"{path.name}:{node.lineno} imports names from app.py; use api.<name>"
            )
            if node.module == "rockforge.interfaces.api":
                assert [(a.name, a.asname) for a in node.names] == [("app", "api")], (
                    f"{path.name}:{node.lineno}: import the app module as api"
                )
            if node.module == "rockforge.config":
                assert "settings" not in {a.name for a in node.names}, (
                    f"{path.name}:{node.lineno} binds settings at import; use api.settings"
                )


def _endpoints(routes: list) -> set[object]:
    # FastAPI 0.14x keeps an included router as one entry; older ones copy its routes.
    out: set[object] = set()
    for r in routes:
        inner = getattr(r, "original_router", None)
        if inner is not None:
            out |= _endpoints(inner.routes)
        elif hasattr(r, "endpoint"):
            out.add(r.endpoint)
    return out


def test_every_router_is_part_of_the_app() -> None:
    import importlib

    import rockforge.interfaces.api.app as app_module

    served = _endpoints(app_module.app.routes)
    for path in ROUTERS:
        mod = importlib.import_module(f"rockforge.interfaces.api.routers.{path.stem}")
        missing = _endpoints(mod.router.routes) - served
        assert not missing, f"{path.name}: not served by the app: {missing}"
