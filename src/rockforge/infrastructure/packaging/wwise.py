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

import platform
import re
import shutil
import struct
import subprocess
import zipfile
from importlib import resources
from pathlib import Path

from rockforge.domain.errors import PackagingError

_CONSOLE_RELATIVE_CANDIDATES = (
    "Authoring/x64/Release/bin/WwiseConsole.exe",
    "Authoring/Win32/Release/bin/WwiseConsole.exe",
)

# Template projects exist for these Wwise major versions (same set DLC Builder supports).
_SUPPORTED_VERSIONS = ("2019", "2021", "2022", "2023")


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

    def _detect_version(self) -> str:
        match = re.search(r"20(?:19|21|22|23)", str(self._root))
        if match is None:
            raise PackagingError(
                f"could not determine the Wwise version from '{self._root}' — "
                f"supported versions: {', '.join(_SUPPORTED_VERSIONS)} (point "
                "ROCKFORGE_WWISE_ROOT at a folder containing the version, e.g. "
                "'C:/Program Files (x86)/Audiokinetic/Wwise 2023.1.x')"
            )
        return match.group(0)

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
