# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for RockForge standalone.

Produces a one-folder distribution (--onedir) containing:
  rockforge.exe          — the launcher
  _internal/             — Python runtime + all packages
  ffmpeg/ffmpeg.exe      — bundled ffmpeg (must be placed before building)
  web/                   — the UI (index.html + app.js + gear art)

Build:
  pip install pyinstaller
  pyinstaller rockforge.spec

The output lands in dist/rockforge/. Zip that folder for distribution.
"""
import os
from pathlib import Path

block_cipher = None
src = Path("src")
pkg = src / "rockforge"

# Collect package data that setuptools.package-data normally handles.
datas = []

# The whole web UI — index.html, app.js and the bundled gear art. Walked, NOT
# listed by hand: the hand-written list said only ("web/index.html", "web"), and
# when app.js was extracted out of index.html's inline <script> the list silently
# didn't follow. The shipped .exe then served an index.html whose
# <script src="/app.js"> had nothing behind it, so the entire UI was inert.
# Walking the folder means any file added under web/ is bundled automatically.
web_dir = Path("web")
for f in sorted(web_dir.rglob("*")):
    if f.is_file():
        datas.append((str(f), str(Path("web") / f.relative_to(web_dir).parent)))

# Every data file inside the package (Wwise templates, the gear catalogue,
# DLC Builder's default tones, the RSEnumerable flat models, the lyric-font
# atlas, …), at its package path, which is where the code reads it from.
# Walked, not listed by hand: the list missed default_tones/*.json, and every
# .psarc of a project without tones of its own failed in the .exe — which only
# the release workflow's smoke test (a real build with the frozen app) caught.
for f in sorted(pkg.rglob("*")):
    if f.is_file() and f.suffix not in (".py", ".pyc") and "__pycache__" not in f.parts:
        datas.append((str(f), str(Path("rockforge") / f.relative_to(pkg).parent)))

# The standalone ML runners. These are executed as SCRIPTS by another Python
# (the one ROCKFORGE_ML_PYTHON points at — see infrastructure/ml_python.py), so
# unlike every other module they must exist as real .py FILES on disk: inside
# the bundle a package's modules live in the archive, where no other
# interpreter can run them. Shipped at their package path, which is where
# `ml_python.runner_path` looks. Walked, not listed by hand, for the same
# reason web/ is — a new runner must not need someone to remember this file.
for f in sorted(pkg.rglob("_*_runner.py")) + sorted(pkg.rglob("_demucs_patcher.py")):
    datas.append((str(f), str(Path("rockforge") / f.relative_to(pkg).parent)))

# What the extra components install (infrastructure/components.py): the exact
# requirement strings of the [ml], [lyrics], [youtube] and [pdf] extras, read
# from pyproject.toml now, because the frozen app has no pyproject to read.
import json
import sys

sys.path.insert(0, str(src))
from rockforge.infrastructure.components import (  # noqa: E402
    REQUIREMENTS_FILE,
    requirements_from_pyproject,
)

_components = Path("build") / REQUIREMENTS_FILE
_components.parent.mkdir(exist_ok=True)
_components.write_text(json.dumps(requirements_from_pyproject(Path("pyproject.toml"))))
datas.append((str(_components), "rockforge/infrastructure"))

# Bundled ffmpeg (place ffmpeg/ffmpeg.exe in the project root before building).
ffmpeg_dir = Path("ffmpeg")
if ffmpeg_dir.is_dir():
    for f in ffmpeg_dir.iterdir():
        if f.is_file():
            datas.append((str(f), "ffmpeg"))

# Celery imports some of its OWN modules by name when the app is created — its
# fixups and loaders ("celery.fixups.django:fixup") — so PyInstaller's static
# analysis never sees them. Without them the worker died on `import celery_app`
# before any job ran ("No module named 'celery.fixups'"), and every new project
# sat pending forever: the in-process worker still builds the Celery app even
# though it calls the tasks directly. Read from Celery's own tables, so an
# upgrade that adds or renames one follows by itself.
from celery.app.base import BUILTIN_FIXUPS
from celery.loaders import LOADER_ALIASES

celery_by_name = sorted(
    {ref.split(":")[0] for ref in (*BUILTIN_FIXUPS, *LOADER_ALIASES.values())}
)

a = Analysis(
    ["start_standalone.py"],
    pathex=[str(src)],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "rockforge.interfaces.api.app",
        "rockforge.interfaces.worker.celery_app",
        "rockforge.interfaces.worker.inprocess",
        "rockforge.infrastructure.packaging.psarc.container",
        "rockforge.infrastructure.packaging.psarc.crypto",
        "rockforge.infrastructure.packaging.psarc.manifest",
        "rockforge.infrastructure.packaging.psarc.packer",
        "rockforge.infrastructure.packaging.psarc.sng",
        "rockforge.infrastructure.packaging.dlcbuilder",
        "rockforge.infrastructure.packaging.rs2dlc",
        "rockforge.infrastructure.packaging.wwise",
        "rockforge.infrastructure.packaging.gear.gear_catalogue",
        "rockforge.infrastructure.rsxml.writer",
        "rockforge.infrastructure.rsxml.vocals",
        "rockforge.infrastructure.ingestion.sources",
        "rockforge.infrastructure.ingestion.tags",
        "rockforge.infrastructure.normalize.ffmpeg",
        "rockforge.infrastructure.db.models",
        "rockforge.application.gp_pipeline",
        "rockforge.config",
        "uvicorn.logging",
        "uvicorn.loops.auto",
        "uvicorn.protocols.http.auto",
        "uvicorn.lifespan.on",
        *celery_by_name,
    ],
    # pywebview (the native window) needs nothing here: its wheel declares a
    # `pyinstaller40` entry point pointing at its own hook directory, which
    # PyInstaller discovers automatically. Do not add its internals by hand.
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "torch", "torchaudio", "demucs",
        "librosa", "whisperx", "scipy", "numpy",
        "tkinter", "matplotlib", "notebook", "IPython",
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="rockforge",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    # No console window: the launcher opens a native window (pywebview), and a
    # black cmd box behind it reads as a bug. A windowed build has NO stdout or
    # stderr, so start_standalone.main() redirects both to a log file before
    # anything can write to them — see redirect_output_to_log.
    console=False,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="rockforge",
)
