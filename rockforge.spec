# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for RockForge standalone.

Produces a one-folder distribution (--onedir) containing:
  rockforge.exe          — the launcher
  _internal/             — Python runtime + all packages
  ffmpeg/ffmpeg.exe      — bundled ffmpeg (must be placed before building)
  web/index.html         — the UI

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
datas = [
    ("web/index.html", "web"),
]

# Wwise templates (MIT, from DLC Builder).
wwise_dir = pkg / "infrastructure" / "packaging" / "wwise_templates"
if wwise_dir.is_dir():
    for f in wwise_dir.iterdir():
        datas.append((str(f), "rockforge/infrastructure/packaging/wwise_templates"))

# Tone gear catalogue.
gear_file = pkg / "infrastructure" / "packaging" / "gear" / "tone_gear_data.json"
if gear_file.exists():
    datas.append((str(gear_file), "rockforge/infrastructure/packaging/gear"))

# Bundled ffmpeg (place ffmpeg/ffmpeg.exe in the project root before building).
ffmpeg_dir = Path("ffmpeg")
if ffmpeg_dir.is_dir():
    for f in ffmpeg_dir.iterdir():
        if f.is_file():
            datas.append((str(f), "ffmpeg"))

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
        "rockforge.application.pipeline",
        "rockforge.config",
        "uvicorn.logging",
        "uvicorn.loops.auto",
        "uvicorn.protocols.http.auto",
        "uvicorn.lifespan.on",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "torch", "torchaudio", "tensorflow", "demucs", "basic_pitch",
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
    console=True,
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
