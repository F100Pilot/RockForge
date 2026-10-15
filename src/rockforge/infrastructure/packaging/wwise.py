"""Automatic .wem conversion by driving a locally installed Wwise (never bundled).

The Audiokinetic EULA forbids redistributing the authoring tool/WwiseConsole
(docs/research/04-wwise-songsterr-cdlcai.md §1), so RockForge only *invokes* a
Wwise installation provided by the user, the same approach as DLC Builder:

1. locate WwiseConsole via ROCKFORGE_WWISE_ROOT or the WWISEROOT env var;
2. extract the bundled template project matching the installed Wwise version
   (wwise_templates/, taken from DLC Builder, MIT) — it carries the
   Rocksmith-compatible conversion settings (Vorbis WITH seek table; a blank
   project's presets lack it and the game plays silence and aborts);
3. drop the WAV at Originals/SFX/Audio.wav and run
   `WwiseConsole generate-soundbank`;
4. collect the .wem from .cache/Windows/SFX and patch the header word at
   offset 40 to 3, exactly as DLC Builder does.

On non-Windows hosts the .exe is run through Wine (as DLC Builder does on
Linux).
"""

from __future__ import annotations

import os
import platform
import re
import shutil
import struct
import subprocess
import sys
import zipfile
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

from rockforge.domain.errors import PackagingError

_CONSOLE_RELATIVE_CANDIDATES = (
    "Authoring/x64/Release/bin/WwiseConsole.exe",
    "Authoring/Win32/Release/bin/WwiseConsole.exe",
)

# Template projects exist for these Wwise major versions (same set DLC Builder supports).
_SUPPORTED_VERSIONS = ("2019", "2021", "2022", "2023")


@dataclass(frozen=True)
class WwiseInstall:
    """A Wwise folder found on disk, usable or not — so a failed detection can
    say WHAT it found (a 2024/2025, or a version without its console) instead
    of "not set"."""

    path: Path
    version: str  # "2023.1.4.8496", or just "2023"
    console: Path | None

    @property
    def major(self) -> str:
        return self.version[:4]

    @property
    def supported(self) -> bool:
        return self.major in _SUPPORTED_VERSIONS and self.console is not None


def _search_bases() -> list[Path]:
    """Where the Audiokinetic Launcher installs by default (``Program Files
    (x86)/Audiokinetic``) and its ``Audiokinetic`` folder on any drive."""
    roots = [os.environ.get("PROGRAMFILES(X86)"), os.environ.get("PROGRAMFILES")]
    roots += [str(d) for d in _drives()]
    roots += [str(d / sub) for d in _drives() for sub in ("Program Files (x86)", "Program Files")]
    out: list[Path] = []
    for r in roots:
        if r and (p := Path(r) / "Audiokinetic") not in out:
            out.append(p)
    return out


def _drives() -> list[Path]:
    if sys.platform != "win32":
        return []
    return [d for d in (Path(f"{c}:/") for c in "CDEFGHIJKLMNOPQRSTUVWXYZ") if d.exists()]


# Folders at a drive's root that never hold a Wwise the user installed.
_SKIP_AT_ROOT = {"windows", "$recycle.bin", "system volume information", "programdata",
                 "recovery", "perflogs", "$windows.~bt", "$windows.~ws", "msocache"}
_SCAN_BUDGET = 3000  # folders listed per drive, so a huge disk cannot stall the page
_SCAN_TTL_S = 300.0
_scan_cache: tuple[float, list[Path]] | None = None


def scan_drive(root: Path, budget: int = _SCAN_BUDGET) -> list[Path]:
    """``Wwise…`` folders at most two levels under ``root`` (``I:/Wwise2023…``,
    ``I:/Rocksmith/Wwise_2023…``): the Launcher lets the user install anywhere,
    and that is where people put it."""
    found: list[Path] = []
    try:
        top = [c for c in root.iterdir() if c.is_dir()]
    except OSError:
        return found
    for child in top:
        name = child.name.lower()
        if name in _SKIP_AT_ROOT or name.startswith("."):
            continue
        if name.startswith("wwise"):
            found.append(child)
            continue
        if budget <= 0:
            break
        budget -= 1
        try:
            found += [
                g for g in child.iterdir() if g.name.lower().startswith("wwise") and g.is_dir()
            ]
        except OSError:
            continue
    return found


def _scan_drives() -> list[Path]:
    """Every drive scanned, remembered for a few minutes (the Settings page
    and every build ask)."""
    global _scan_cache
    import time

    now = time.monotonic()
    if _scan_cache is None or now - _scan_cache[0] > _SCAN_TTL_S:
        _scan_cache = (now, [p for d in _drives() for p in scan_drive(d)])
    return _scan_cache[1]


def _registry_wwiseroot() -> Path | None:
    """``WWISEROOT`` as the Wwise installer wrote it to the registry — a
    process started before the install (or from a shell that never got the
    change) does not have it in its environment."""
    if sys.platform != "win32":
        return None
    import winreg

    keys = (
        (winreg.HKEY_CURRENT_USER, "Environment"),
        (winreg.HKEY_LOCAL_MACHINE,
         r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"),
    )
    for hive, sub in keys:
        try:
            with winreg.OpenKey(hive, sub) as key:
                value, _ = winreg.QueryValueEx(key, "WWISEROOT")
        except OSError:
            continue
        if value:
            return Path(os.path.expandvars(str(value)))
    return None


def _console_in(folder: Path) -> Path | None:
    for rel in _CONSOLE_RELATIVE_CANDIDATES:
        if (folder / rel).exists():
            return folder / rel
    return None


def find_wwise_installs(bases: list[Path] | None = None) -> list[WwiseInstall]:
    """Every ``Wwise <year>…`` folder under the Audiokinetic folders (and the
    one the registry's ``WWISEROOT`` names), newest first."""
    extra: list[Path] = []
    if bases is None:
        bases = _search_bases()
        reg = _registry_wwiseroot()
        if reg is not None:
            extra.append(reg)
        extra += _scan_drives()
    candidates: list[Path] = list(extra)
    for base in bases:
        try:
            candidates += [c for c in base.iterdir() if c.is_dir()]
        except OSError:
            continue
    found: list[WwiseInstall] = []
    seen: set[str] = set()
    for child in candidates:
        m = re.search(r"20\d\d(?:\.\d+)*", child.name)
        if not (m and child.name.lower().startswith("wwise")) or str(child).lower() in seen:
            continue
        seen.add(str(child).lower())
        found.append(WwiseInstall(child, m.group(0), _console_in(child)))
    return sorted(
        found, key=lambda w: [int(x) for x in w.version.split(".") if x.isdigit()], reverse=True
    )


def detect_wwise_root(bases: list[Path] | None = None) -> Path | None:
    """A supported Wwise where the Audiokinetic Launcher installs it
    (``Program Files (x86)/Audiokinetic/Wwise <version>``), newest first — so a
    user of the `.exe` does not have to set an environment variable."""
    return next((w.path for w in find_wwise_installs(bases) if w.supported), None)


def _fix_wem_header(wem: Path) -> None:
    """Patch the format word at offset 40 to 3 (Rocksmith expects it; DLC
    Builder applies the identical fix after conversion)."""
    with wem.open("r+b") as fh:
        fh.seek(40)
        fh.write(struct.pack("<I", 3))


class WwiseWemConverter:
    def __init__(self, wwise_root: Path | None, use_wine: bool | None = None) -> None:
        self._root = wwise_root
        self._use_wine = use_wine if use_wine is not None else platform.system() != "Windows"

    def console_path(self) -> Path | None:
        if self._root is None:
            return None
        # Allow tests to inject a fake console path.
        override = getattr(self, "_console_override", None)
        if override is not None:
            return Path(override) if override.exists() else None
        for rel in _CONSOLE_RELATIVE_CANDIDATES:
            p = self._root / rel
            if p.exists():
                return p
        return None

    def available(self) -> bool:
        return self.console_path() is not None

    def _run(self, args: list[str]) -> None:
        console = self.console_path()
        if console is None:
            raise PackagingError(
                "Wwise not found: set ROCKFORGE_WWISE_ROOT (or WWISEROOT) to the "
                "Wwise installation root containing Authoring/x64/Release/bin"
            )
        cmd = ([str(console)] if not self._use_wine else ["wine", str(console)]) + args
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        except FileNotFoundError as exc:  # wine missing on Linux, etc.
            raise PackagingError(f"could not execute Wwise console: {exc}") from exc
        if proc.returncode != 0:
            raise PackagingError(
                f"WwiseConsole failed (exit {proc.returncode}): "
                f"{(proc.stderr or proc.stdout)[-2000:]}"
            )

    def version(self) -> str | None:
        """The supported major version the folder names, else None — the
        template is chosen by it, so a 2024/2025 has nothing to convert with."""
        match = re.search(r"20(?:19|21|22|23)", str(self._root))
        return match.group(0) if match else None

    def _detect_version(self) -> str:
        version = self.version()
        if version is None:
            raise PackagingError(
                f"could not determine the Wwise version from '{self._root}' — "
                f"supported versions: {', '.join(_SUPPORTED_VERSIONS)} (point "
                "ROCKFORGE_WWISE_ROOT at a folder containing the version, e.g. "
                "'C:/Program Files (x86)/Audiokinetic/Wwise 2023.1.x')"
            )
        return version

    def _ensure_template(self, workdir: Path) -> Path:
        """Extract the version-matched template project; returns the .wproj path."""
        template_dir = workdir / "wwise_template"
        wproj = template_dir / "Template.wproj"
        if not wproj.exists():
            version = self._detect_version()
            zip_res = (
                resources.files("rockforge.infrastructure.packaging")
                / "wwise_templates"
                / f"wwise{version}.zip"
            )
            with resources.as_file(zip_res) as zip_path, zipfile.ZipFile(zip_path) as zf:
                zf.extractall(template_dir)
            if not wproj.exists():
                raise PackagingError(f"template wwise{version}.zip is missing Template.wproj")
        return wproj

    def convert(self, wav: Path, workdir: Path) -> Path:
        """Convert a WAV to a Rocksmith-playable .wem; returns the produced file."""
        if self.console_path() is None:
            raise PackagingError(
                "Wwise not found: set ROCKFORGE_WWISE_ROOT (or WWISEROOT) to the "
                "Wwise installation root containing Authoring/x64/Release/bin"
            )
        wproj = self._ensure_template(workdir)
        template_dir = wproj.parent

        source = template_dir / "Originals" / "SFX" / "Audio.wav"
        source.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(wav, source)

        cache_dir = template_dir / ".cache" / "Windows" / "SFX"
        shutil.rmtree(cache_dir, ignore_errors=True)  # stale wems from earlier runs

        self._run(
            [
                "generate-soundbank",
                str(wproj),
                "--platform", "Windows",
                "--language", "English(US)",
                "--no-decode",
                "--quiet",
            ]
        )
        wems = sorted(cache_dir.rglob("*.wem"))
        if not wems:
            raise PackagingError(
                "Wwise conversion produced no .wem in .cache/Windows/SFX — "
                "check the WwiseConsole output and the installed Wwise version "
                f"(supported: {', '.join(_SUPPORTED_VERSIONS)})"
            )
        _fix_wem_header(wems[0])
        return wems[0]
