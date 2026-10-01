"""Build the RockForge standalone .exe via PyInstaller.

Usage:
    py -3.11 build_exe.py              # build the exe only
    py -3.11 build_exe.py --zip        # also create a portable .zip
    py -3.11 build_exe.py --installer  # also compile the Inno Setup installer

Prerequisites:
    pip install pyinstaller
    Place ffmpeg.exe inside a ffmpeg/ folder at the project root.
    (winget install ffmpeg, then copy ffmpeg.exe to ffmpeg/ffmpeg.exe)

Output:
    dist/rockforge/                    — the distributable folder
    dist/rockforge/rockforge.exe       — double-click to launch
    dist/RockForge_portable.zip        — portable zip (with --zip)
    Output/RockForge_Setup.exe         — installer (with --installer)
"""

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# Shipped next to rockforge.exe: the MIT licence and the third-party
# attributions it and the vendored code (Rocksmith2014.NET, three.js, …) require
# to travel with every copy, plus the legal notice (THIRD_PARTY_NOTICES.md).
LEGAL_FILES = ("LICENSE", "THIRD_PARTY_NOTICES.md", "LEGAL.md")


def check_ffmpeg() -> None:
    ffmpeg_dir = ROOT / "ffmpeg"
    ffmpeg_exe = ffmpeg_dir / "ffmpeg.exe"
    if not ffmpeg_exe.exists():
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


def check_desktop_window() -> None:
    """The .exe opens a native window via pywebview. Without it the build still
    works — the launcher falls back to the default browser — so this warns
    rather than failing, but a silent fallback would look like the window
    feature simply did not work."""
    try:
        import webview  # noqa: F401
    except ImportError:
        print(
            "WARNING: pywebview is not installed, so the .exe will open the\n"
            "  default BROWSER instead of a native window.\n"
            '  Install it with:  py -3.11 -m pip install -e ".[desktop]"'
        )


def build() -> None:
    check_ffmpeg()
    check_desktop_window()
    spec = ROOT / "rockforge.spec"
    if not spec.exists():
        print(f"ERROR: {spec} not found")
        sys.exit(1)
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", str(spec)]
    print(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True, cwd=str(ROOT))
    dist = ROOT / "dist" / "rockforge"
    copy_legal_files(dist)
    print(f"\nBuild complete: {dist}")
    print(f"  Launch: {dist / 'rockforge.exe'}")
    return dist


def copy_legal_files(dist: Path, root: Path = ROOT) -> None:
    """Put the licence, the third-party notices and the legal notice beside the
    .exe, so the portable zip and the installer (both built from ``dist``)
    carry them."""
    for name in LEGAL_FILES:
        shutil.copy2(root / name, dist / name)


def make_zip(dist: Path) -> None:
    """Create a portable .zip of the dist folder."""
    zip_path = ROOT / "dist" / "RockForge_portable"
    print("\nCreating portable ZIP...")
    shutil.make_archive(str(zip_path), "zip", str(dist.parent), dist.name)
    print(f"  ZIP: {zip_path}.zip")


def make_installer() -> None:
    """Compile the Inno Setup installer (.iss → .exe)."""
    iss = ROOT / "installer.iss"
    if not iss.exists():
        print(f"ERROR: {iss} not found")
        return
    iscc = shutil.which("ISCC")
    if not iscc:
        # Common install paths on Windows
        for candidate in [
            Path(r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"),
            Path(r"C:\Program Files\Inno Setup 6\ISCC.exe"),
        ]:
            if candidate.exists():
                iscc = str(candidate)
                break
    if not iscc:
        print(
            "ERROR: ISCC.exe (Inno Setup Compiler) not found.\n"
            "  Install Inno Setup 6 from https://jrsoftware.org/isinfo.php\n"
            "  or add ISCC.exe to your PATH."
        )
        return
    cmd = [iscc, str(iss)]
    print(f"\nCompiling installer: {' '.join(cmd)}")
    subprocess.run(cmd, check=True, cwd=str(ROOT))
    print(f"  Installer: {ROOT / 'Output' / 'RockForge_Setup.exe'}")


if __name__ == "__main__":
    dist = build()
    if "--zip" in sys.argv:
        make_zip(dist)
    if "--installer" in sys.argv:
        make_installer()
