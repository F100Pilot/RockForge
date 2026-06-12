"""WwiseWemConverter orchestration tests using a fake WwiseConsole executable.

A real Wwise cannot run in CI (EULA forbids bundling); these tests validate
detection, command construction, .wsources generation and error reporting.
"""

from __future__ import annotations

import os
import platform
import stat
import sys
from pathlib import Path

import pytest

from rockforge.domain.errors import PackagingError
from rockforge.infrastructure.packaging.wwise import WwiseWemConverter

_IS_WINDOWS = platform.system() == "Windows"

# Python-based fake WwiseConsole (runs on all platforms via sys.executable).
# Records arguments to calls.log; simulates project creation and .wem output.
_FAKE_CONSOLE_PY = '''
import sys
from pathlib import Path
# Filter out -X frozen_modules=off injected by some pytest/CPython configs
args = [a for a in sys.argv[1:] if a != "-X" and a != "frozen_modules=off"]
log = Path(__file__).resolve().parent / "calls.log"
with open(log, "a") as f:
    f.write(" ".join(args) + "\\n")
if args and args[0] == "create-new-project":
    Path(args[1]).parent.mkdir(parents=True, exist_ok=True)
    Path(args[1]).touch()
elif args and args[0] == "convert-external-source":
    out = None
    for i, a in enumerate(args):
        if a == "--output" and i + 1 < len(args):
            out = Path(args[i + 1])
    if out:
        out.mkdir(parents=True, exist_ok=True)
        (out / "audio.wem").write_text("WEM")
'''


def _write_fake_console(console_path: Path, py_script: Path) -> None:
    """Write a fake WwiseConsole that works cross-platform.

    On Windows uses a .cmd wrapper (since .exe must be PE binary).
    On Linux/macOS uses a shell script with shebang.
    """
    py_script.write_text(_FAKE_CONSOLE_PY)
    if _IS_WINDOWS:
        console_path.write_text(
            f'@"{sys.executable}" "{py_script}" %*\n'
        )
    else:
        console_path.write_text(f'#!/bin/sh\n"{sys.executable}" "{py_script}" "$@"\n')
        console_path.chmod(console_path.stat().st_mode | stat.S_IEXEC)


@pytest.fixture()
def wwise_root(tmp_path: Path) -> Path:
    root = tmp_path / "wwise"
    console_exe = root / "Authoring/x64/Release/bin/WwiseConsole.exe"
    console_exe.parent.mkdir(parents=True)
    py_script = console_exe.parent / "_fake_console.py"
    if _IS_WINDOWS:
        # On Windows use a .cmd wrapper because .exe must be PE binary.
        console_cmd = root / "Authoring/x64/Release/bin/WwiseConsole.cmd"
        _write_fake_console(console_cmd, py_script)
    else:
        _write_fake_console(console_exe, py_script)
    return root


def test_unavailable_without_root() -> None:
    conv = WwiseWemConverter(wwise_root=None)
    assert not conv.available()
    with pytest.raises(PackagingError, match="Wwise not found"):
        conv.convert(Path("x.wav"), Path("/tmp"))


def test_detects_console(wwise_root: Path) -> None:
    conv = WwiseWemConverter(wwise_root=wwise_root)
    if _IS_WINDOWS:
        # On Windows the fake uses .cmd wrapper; override console_path()
        cmd = wwise_root / "Authoring/x64/Release/bin/WwiseConsole.cmd"
        conv._console_override = cmd  # type: ignore[attr-defined]
    assert conv.available()
    assert not WwiseWemConverter(wwise_root=wwise_root / "nope").available()


def test_convert_creates_project_wsources_and_wem(wwise_root: Path, tmp_path: Path) -> None:
    wav = tmp_path / "song.wav"
    wav.write_bytes(b"RIFF")
    work = tmp_path / "work"
    conv = WwiseWemConverter(
        wwise_root=wwise_root, conversion="Vorbis Quality High", use_wine=False
    )
    if _IS_WINDOWS:
        conv._console_override = (
            wwise_root / "Authoring/x64/Release/bin/WwiseConsole.cmd"
        )

    wem = conv.convert(wav, work)
    assert wem.read_text() == "WEM"

    wsources = (work / "rockforge.wsources").read_text()
    assert 'Path="song.wav"' in wsources
    assert 'Conversion="Vorbis Quality High"' in wsources

    # Verify args were recorded.
    calls = (wwise_root / "Authoring/x64/Release/bin/calls.log").read_text().splitlines()
    assert any("create-new-project" in c for c in calls)
    assert any("convert-external-source" in c for c in calls)
    # project is cached: a second conversion must not re-create it
    conv.convert(wav, work)
    calls = (wwise_root / "Authoring/x64/Release/bin/calls.log").read_text().splitlines()
    assert sum(1 for c in calls if "create-new-project" in c) == 1


def test_failure_surfaces_stderr(wwise_root: Path, tmp_path: Path) -> None:
    py_script = wwise_root / "Authoring/x64/Release/bin/_fake_console.py"
    py_script.write_text(
        "import sys; sys.stderr.write('bad preset\\n'); sys.exit(3)\n"
    )
    conv = WwiseWemConverter(wwise_root=wwise_root, use_wine=False)
    if _IS_WINDOWS:
        conv._console_override = (
            wwise_root / "Authoring/x64/Release/bin/WwiseConsole.cmd"
        )
    wav = tmp_path / "a.wav"
    wav.write_bytes(b"RIFF")
    with pytest.raises(PackagingError, match="exit 3"):
        conv.convert(wav, tmp_path / "w")


def test_env_fallback_resolution(monkeypatch: pytest.MonkeyPatch, wwise_root: Path) -> None:
    import importlib

    monkeypatch.setenv("WWISEROOT", str(wwise_root))
    monkeypatch.setenv("ROCKFORGE_WWISE_ROOT", "")
    import rockforge.config as config

    importlib.reload(config)
    # Override any .env file value via monkeypatch on the loaded settings object.
    monkeypatch.setattr(config.settings, "wwise_root", None, raising=False)
    assert config.settings.resolved_wwise_root() == wwise_root
    assert os.environ["WWISEROOT"] == str(wwise_root)
