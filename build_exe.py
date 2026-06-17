"""Build the RockForge standalone .exe via PyInstaller.

Usage:
    py -3.11 build_exe.py

Prerequisites:
    pip install pyinstaller
    Place ffmpeg.exe inside a ffmpeg/ folder at the project root.
    (winget install ffmpeg, then copy ffmpeg.exe to ffmpeg/ffmpeg.exe)

Output:
    dist/rockforge/          — the distributable folder
    dist/rockforge/rockforge.exe  — double-click to launch
"""

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def check_ffmpeg() -> None:
    ffmpeg_dir = ROOT / "ffmpeg"
    ffmpeg_exe = ffmpeg_dir / "ffmpeg.exe"
    if not ffmpeg_exe.exists():
        # Try to locate ffmpeg on PATH and copy it
        found = shutil.which("ffmpeg")
        if found:
            ffmpeg_dir.mkdir(exist_ok=True)
            shutil.copy2(found, ffmpeg_exe)
            print(f"Copied ffmpeg from {found}")
        else:
            print(
                "WARNING: ffmpeg/ffmpeg.exe not found. The .exe will need "
                "ffmpeg on the user's PATH at runtime."
            )


def build() -> None:
    check_ffmpeg()
    spec = ROOT / "rockforge.spec"
    if not spec.exists():
        print(f"ERROR: {spec} not found")
        sys.exit(1)
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", str(spec)]
    print(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True, cwd=str(ROOT))
    dist = ROOT / "dist" / "rockforge"
    print(f"\nBuild complete: {dist}")
    print(f"  Launch: {dist / 'rockforge.exe'}")


if __name__ == "__main__":
    build()
