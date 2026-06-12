"""Automatic .wem conversion by driving a locally installed Wwise (never bundled).

The Audiokinetic EULA forbids redistributing the authoring tool/WwiseConsole
(docs/research/04-wwise-songsterr-cdlcai.md §1), so RockForge only *invokes* a
Wwise installation provided by the user, the same approach as DLC Builder and
the community sound2wem wrapper:

1. locate WwiseConsole via ROCKFORGE_WWISE_ROOT or the WWISEROOT env var;
2. create (and cache) a blank Wwise project (`create-new-project`);
3. write a .wsources external-source list referencing the WAV;
4. run `WwiseConsole convert-external-source` and collect the .wem.

On non-Windows hosts the .exe is run through Wine (as DLC Builder does on
Linux). The conversion preset name is configurable because a blank project's
available conversion settings vary by Wwise version — validate on your machine.
"""

from __future__ import annotations

import platform
import subprocess
from pathlib import Path

from rockforge.domain.errors import PackagingError

_CONSOLE_RELATIVE_CANDIDATES = (
    "Authoring/x64/Release/bin/WwiseConsole.exe",
    "Authoring/Win32/Release/bin/WwiseConsole.exe",
)


class WwiseWemConverter:
    def __init__(
        self,
        wwise_root: Path | None,
        conversion: str = "Vorbis Quality High",
        use_wine: bool | None = None,
    ) -> None:
        self._root = wwise_root
        self._conversion = conversion
        self._use_wine = use_wine if use_wine is not None else platform.system() != "Windows"

    def console_path(self) -> Path | None:
        if self._root is None:
            return None
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

    def _ensure_project(self, workdir: Path) -> Path:
        project = workdir / "wwise_project" / "rockforge.wproj"
        if not project.exists():
            self._run(["create-new-project", str(project), "--platform", "Windows"])
        if not project.exists():
            raise PackagingError("WwiseConsole reported success but no project was created")
        return project

    def convert(self, wav: Path, workdir: Path) -> Path:
        """Convert a WAV to .wem; returns the produced file path."""
        project = self._ensure_project(workdir)
        out_dir = workdir / "wem"
        out_dir.mkdir(parents=True, exist_ok=True)

        wsources = workdir / "rockforge.wsources"
        wsources.write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<ExternalSourcesList SchemaVersion="1" Root="{wav.parent}">\n'
            f'  <Source Path="{wav.name}" Conversion="{self._conversion}"/>\n'
            "</ExternalSourcesList>\n",
            encoding="utf-8",
        )
        self._run(
            [
                "convert-external-source",
                str(project),
                "--platform", "Windows",
                "--source-file", str(wsources),
                "--output", str(out_dir),
            ]
        )
        wems = sorted(out_dir.rglob("*.wem"))
        if not wems:
            raise PackagingError(
                "Wwise conversion produced no .wem — check the conversion preset "
                f"name ('{self._conversion}', ROCKFORGE_WWISE_CONVERSION) exists in "
                "your Wwise version"
            )
        return wems[0]
