"""WwiseWemConverter orchestration tests using a fake WwiseConsole executable.

A real Wwise cannot run in CI (EULA forbids bundling); these tests validate
detection, template extraction, command construction, the Rocksmith header fix
and error reporting.
"""

from __future__ import annotations

import os
import platform
import stat
import struct
import sys
from pathlib import Path

import pytest

from rockforge.domain.errors import PackagingError
from rockforge.infrastructure.packaging.wwise import WwiseWemConverter

_IS_WINDOWS = platform.system() == "Windows"

# Python-based fake WwiseConsole (runs on all platforms via sys.executable).
# Records arguments to calls.log; simulates the generate-soundbank wem output.
_FAKE_CONSOLE_PY = '''
import sys
from pathlib import Path
# Filter out -X frozen_modules=off injected by some pytest/CPython configs
args = [a for a in sys.argv[1:] if a != "-X" and a != "frozen_modules=off"]
log = Path(__file__).resolve().parent / "calls.log"
with open(log, "a") as f:
    f.write(" ".join(args) + "\\n")
if args and args[0] == "generate-soundbank":
    template_dir = Path(args[1]).parent
    assert (template_dir / "Originals" / "SFX" / "Audio.wav").exists()
    cache = template_dir / ".cache" / "Windows" / "SFX"
    cache.mkdir(parents=True, exist_ok=True)
    (cache / "Audio.wem").write_bytes(b"\\x00" * 64)
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
    # Realistic install folder name — the converter detects the version from it.
    root = tmp_path / "Wwise 2023.1.3.8471"
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


def _converter(wwise_root: Path) -> WwiseWemConverter:
    conv = WwiseWemConverter(wwise_root=wwise_root, use_wine=False)
    if _IS_WINDOWS:
        conv._console_override = (  # type: ignore[attr-defined]
            wwise_root / "Authoring/x64/Release/bin/WwiseConsole.cmd"
        )
    return conv


def test_unavailable_without_root() -> None:
    conv = WwiseWemConverter(wwise_root=None)
    assert not conv.available()
    with pytest.raises(PackagingError, match="Wwise not found"):
        conv.convert(Path("x.wav"), Path("/tmp"))


def test_detects_console(wwise_root: Path) -> None:
    conv = _converter(wwise_root)
    assert conv.available()
    assert not WwiseWemConverter(wwise_root=wwise_root / "nope").available()


def test_convert_extracts_template_and_patches_header(wwise_root: Path, tmp_path: Path) -> None:
    wav = tmp_path / "song.wav"
    wav.write_bytes(b"RIFF")
    work = tmp_path / "work"
    conv = _converter(wwise_root)

    wem = conv.convert(wav, work)

    # Template project (Rocksmith conversion settings) was extracted.
    template_dir = work / "wwise_template"
    assert (template_dir / "Template.wproj").exists()
    assert (template_dir / "Originals" / "SFX" / "Audio.wav").read_bytes() == b"RIFF"
    # Rocksmith header fix: uint32 LE 3 at offset 40 (as DLC Builder applies).
    data = wem.read_bytes()
    assert struct.unpack_from("<I", data, 40)[0] == 3

    calls = (wwise_root / "Authoring/x64/Release/bin/calls.log").read_text().splitlines()
    assert any("generate-soundbank" in c and "--no-decode" in c for c in calls)


def test_unsupported_wwise_version_rejected(tmp_path: Path) -> None:
    root = tmp_path / "Wwise 2016.2.0"
    console = root / "Authoring/x64/Release/bin/WwiseConsole.exe"
    console.parent.mkdir(parents=True)
    console.touch()
    conv = WwiseWemConverter(wwise_root=root, use_wine=False)
    wav = tmp_path / "a.wav"
    wav.write_bytes(b"RIFF")
    with pytest.raises(PackagingError, match="supported versions"):
        conv.convert(wav, tmp_path / "w")


def test_failure_surfaces_stderr(wwise_root: Path, tmp_path: Path) -> None:
    py_script = wwise_root / "Authoring/x64/Release/bin/_fake_console.py"
    py_script.write_text(
        "import sys; sys.stderr.write('conversion error\\n'); sys.exit(3)\n"
    )
    conv = _converter(wwise_root)
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


def test_wwise_is_found_where_the_launcher_installs_it(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """A user of the .exe should not need an environment variable: the newest
    supported Wwise under Program Files' Audiokinetic folder is found."""
    from rockforge.infrastructure.packaging.wwise import detect_wwise_root

    base = tmp_path / "Audiokinetic"
    for name, console in (
        ("Wwise 2019.2.15.7667", True),
        ("Wwise2023.1.4.8496", True),
        ("Wwise2024.1.0.8669", True),  # no template for it: not supported
        ("Wwise2022.1.0.0", False),    # no console inside: an empty leftover
        ("Launcher", True),
    ):
        folder = base / name / "Authoring" / "x64" / "Release" / "bin"
        folder.mkdir(parents=True)
        if console:
            (folder / "WwiseConsole.exe").write_bytes(b"")
    assert detect_wwise_root([base]) == base / "Wwise2023.1.4.8496"
    assert detect_wwise_root([tmp_path / "nowhere"]) is None


def test_wwise_is_found_in_a_folder_of_the_users_choosing(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """The Launcher installs anywhere ("I:\\Rocksmith\\Wwise_2025.1.11.9262"):
    a drive is scanned two levels down, skipping the system folders."""
    from rockforge.infrastructure.packaging.wwise import find_wwise_installs, scan_drive

    for rel in ("Rocksmith/Wwise_2025.1.11.9262", "Rocksmith/Wwise_2023.1.4.8496",
                "Wwise2022.1.0.0", "Windows/Wwise2023.9", "Games/a/Wwise2021.1"):
        bin_ = tmp_path / rel / "Authoring" / "x64" / "Release" / "bin"
        bin_.mkdir(parents=True)
        (bin_ / "WwiseConsole.exe").write_bytes(b"")
    found = sorted(p.relative_to(tmp_path).as_posix() for p in scan_drive(tmp_path))
    assert found == ["Rocksmith/Wwise_2023.1.4.8496", "Rocksmith/Wwise_2025.1.11.9262",
                     "Wwise2022.1.0.0"]
    installs = find_wwise_installs([tmp_path / "Rocksmith"])
    assert [w.version for w in installs] == ["2025.1.11.9262", "2023.1.4.8496"]
    assert [w.supported for w in installs] == [False, True]
