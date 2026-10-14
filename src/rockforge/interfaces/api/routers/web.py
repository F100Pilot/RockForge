"""The web UI itself: the page, its scripts (cache-busted), the translation
dictionaries and the vendored three.js the 3D highway loads."""

from __future__ import annotations

import re
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, Response

from rockforge.interfaces.api import app as api

router = APIRouter()


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
def index() -> str:
    for ui in api._web_file_candidates("index.html"):
        if ui.exists():
            html = ui.read_text(encoding="utf-8")
            # Cache-bust app.js by its own mtime. index.html is generated per
            # request and never cached, but the browser happily keeps a stale
            # app.js — which leaves NEW markup wired to an OLD script, so a new
            # button exists and does nothing. That failure looks exactly like a
            # broken feature and has cost real debugging time.
            for name in WEB_SCRIPTS:
                for js in api._web_file_candidates(name):
                    if js.exists():
                        html = html.replace(
                            f'src="/{name}"', f'src="/{name}?v={int(js.stat().st_mtime)}"'
                        )
                        break
            dicts = _i18n_dictionaries()
            stamp = max((int(d.stat().st_mtime) for d in dicts), default=0)
            html = html.replace('src="/i18n-dicts.js"', f'src="/i18n-dicts.js?v={stamp}"')
            return html
    return "<h1>RockForge</h1><p>UI not bundled; see /docs for the API.</p>"


# The web UI's own scripts, served by name (never a client path): app.js (the UI)
# and highway3d.js (the 3D note highway, which loads three.js on first use).
WEB_SCRIPTS = ("i18n.js", "app.js", "highway3d.js")


# three.js, vendored so the app works offline: the module and the core it imports.
THREE_FILES = ("three.module.js", "three.core.js")


def _serve_web_js(relative: str) -> FileResponse:
    for js in api._web_file_candidates(relative):
        if js.exists():
            # Revalidate every load: the URL is mtime-stamped by index(), so a
            # changed file always wins, and an unchanged one still 304s.
            return FileResponse(
                js,
                media_type="text/javascript",
                headers={"Cache-Control": "no-cache"},
            )
    raise HTTPException(404, f"{relative} not bundled")


@router.get("/app.js", include_in_schema=False)
def app_js() -> FileResponse:
    """The web UI's JS, extracted out of index.html's inline <script> so it can
    be linted (ESLint has no way to check an inline block on its own)."""
    return _serve_web_js("app.js")


@router.get("/i18n.js", include_in_schema=False)
def i18n_js() -> FileResponse:
    """The UI's language switch and ``t()`` (loaded before app.js)."""
    return _serve_web_js("i18n.js")


def _i18n_dictionaries() -> list[Path]:
    """Every language the UI has besides Portuguese: one ``web/i18n-<code>.js``
    each, from the first web dir that has any (the same resolution as the
    other bundled files). Adding a language is adding that file."""
    for d in api._web_dirs():
        found = sorted(
            p for p in d.glob("i18n-*.js") if re.fullmatch(r"i18n-[a-z]{2,3}\.js", p.name)
        )
        if found:
            return found
    return []


@router.get("/i18n-dicts.js", include_in_schema=False)
def i18n_dicts_js() -> Response:
    """All the UI's dictionaries in one script (each registers itself in
    ``I18N_DICTS``), so a new ``web/i18n-<code>.js`` needs no markup change."""
    body = "\n".join(p.read_text(encoding="utf-8") for p in _i18n_dictionaries())
    return Response(
        body, media_type="text/javascript", headers={"Cache-Control": "no-cache"}
    )


@router.get("/highway3d.js", include_in_schema=False)
def highway3d_js() -> FileResponse:
    """The 3D note highway (Partitura → "Pista 3D")."""
    return _serve_web_js("highway3d.js")


@router.get("/vendor/three/{name}", include_in_schema=False)
def three_js(name: str) -> FileResponse:
    """three.js, only the two files it is made of — never an arbitrary path."""
    if name not in THREE_FILES:
        raise HTTPException(404, "not found")
    return _serve_web_js(f"vendor/three/{name}")
