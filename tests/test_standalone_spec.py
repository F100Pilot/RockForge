"""The PyInstaller spec must bundle everything the standalone .exe serves.

This exists because it already went wrong once: the spec's data list was written
by hand as a single ``("web/index.html", "web")`` entry, and when 4107 lines of
JS were extracted out of index.html into web/app.js the list silently didn't
follow. The shipped .exe served an index.html whose ``<script src="/app.js">``
had nothing behind it, so the whole UI was inert — and nothing in CI could see
it, because nothing ever looked at the spec.

The spec is a plain Python file that only *calls* PyInstaller's builders at the
end, so it can be executed with stubs and its real ``datas`` list inspected.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
SPEC = REPO_ROOT / "rockforge.spec"


def _run_spec() -> list[tuple[str, str]]:
    """Execute rockforge.spec with the PyInstaller builders stubbed out, and
    return the ``datas`` list it actually hands to Analysis()."""
    captured: dict[str, Any] = {}

    def _analysis(*_args: Any, **kwargs: Any) -> SimpleNamespace:
        captured["datas"] = kwargs["datas"]
        return SimpleNamespace(pure=[], zipped_data=[], scripts=[], binaries=[], datas=[])

    namespace: dict[str, Any] = {
        "__file__": str(SPEC),
        "Analysis": _analysis,
        "PYZ": lambda *a, **k: None,
        "EXE": lambda *a, **k: None,
        "COLLECT": lambda *a, **k: None,
    }
    # The spec resolves its paths relative to the repo root (that is where
    # `pyinstaller rockforge.spec` runs), so evaluate it from there.
    import os

    cwd = os.getcwd()
    try:
        os.chdir(REPO_ROOT)
        exec(compile(SPEC.read_text(encoding="utf-8"), str(SPEC), "exec"), namespace)
    finally:
        os.chdir(cwd)
    return list(captured["datas"])


def test_spec_bundles_every_web_file() -> None:
    """Every file under web/ must reach the bundle — not just the ones someone
    remembered to list. Guards the exact regression above: adding a file to web/
    and forgetting the spec must be impossible, not merely unlikely."""
    datas = _run_spec()
    bundled = {Path(src).resolve() for src, _dest in datas}
    web = REPO_ROOT / "web"
    missing = sorted(
        str(f.relative_to(REPO_ROOT))
        for f in web.rglob("*")
        if f.is_file() and f.resolve() not in bundled
    )
    assert not missing, f"web files absent from the PyInstaller bundle: {missing}"


def test_spec_puts_web_files_where_the_server_looks_for_them() -> None:
    """The app resolves a bundled file as ``<_MEIPASS>/web/<name>``, so the spec's
    destination folders have to mirror web/'s own layout — a flat dump would put
    gear art where nothing reads it."""
    datas = _run_spec()
    dest_by_src = {Path(src).resolve(): dest for src, dest in datas}
    web = REPO_ROOT / "web"
    assert dest_by_src[(web / "index.html").resolve()] == "web"
    assert dest_by_src[(web / "app.js").resolve()] == "web"
    for art in (web / "gear_images").glob("*"):
        if art.is_file():
            assert dest_by_src[art.resolve()] == str(Path("web") / "gear_images")


def test_index_html_only_references_bundled_local_assets() -> None:
    """Anything index.html pulls from our own origin has to exist in web/ — the
    check that would have caught the missing app.js at its source."""
    import re

    html = (REPO_ROOT / "web" / "index.html").read_text(encoding="utf-8")
    refs = re.findall(r'(?:src|href)="/([^"?#]+)[^"]*"', html)
    local = [r for r in refs if not r.startswith(("jobs/", "gear-image/"))]
    assert local, "expected index.html to reference at least app.js"
    for ref in local:
        assert (REPO_ROOT / "web" / ref).is_file(), f"index.html references missing web/{ref}"
