"""WwiseWemConverter orchestration tests using a fake WwiseConsole executable.

A real Wwise cannot run in CI (EULA forbids bundling); these tests validate
detection, command construction, .wsources generation and error reporting.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from rockforge.domain.errors import PackagingError
from rockforge.infrastructure.packaging.wwise import WwiseWemConverter

FAKE_CONSOLE = """#!/bin/sh
# fake WwiseConsole: records args, simulates project creation and wem output
echo "$@" >> "$(dirname "$0")/calls.log"
case "$1" in
  create-new-project) mkdir -p "$(dirname "$2")" && touch "$2" ;;
  convert-external-source)
    out=""
    while [ $# -gt 0 ]; do [ "$1" = "--output" ] && out="$2"; shift; done
    mkdir -p "$out" && printf 'WEM' > "$out/audio.wem" ;;
esac
"""


@pytest.fixture()
def wwise_root(tmp_path: Path) -> Path:
    root = tmp_path / "wwise"
    console = root / "Authoring/x64/Release/bin/WwiseConsole.exe"
    console.parent.mkdir(parents=True)
    console.write_text(FAKE_CONSOLE)
    console.chmod(console.stat().st_mode | stat.S_IEXEC)
    return root


def test_unavailable_without_root() -> None:
    conv = WwiseWemConverter(wwise_root=None)
    assert not conv.available()
    with pytest.raises(PackagingError, match="Wwise not found"):
        conv.convert(Path("x.wav"), Path("/tmp"))


def test_detects_console(wwise_root: Path) -> None:
    assert WwiseWemConverter(wwise_root=wwise_root).available()
    assert not WwiseWemConverter(wwise_root=wwise_root / "nope").available()


def test_convert_creates_project_wsources_and_wem(wwise_root: Path, tmp_path: Path) -> None:
    wav = tmp_path / "song.wav"
    wav.write_bytes(b"RIFF")
    work = tmp_path / "work"
    conv = WwiseWemConverter(
        wwise_root=wwise_root, conversion="Vorbis Quality High", use_wine=False
    )

    wem = conv.convert(wav, work)
    assert wem.read_text() == "WEM"

    wsources = (work / "rockforge.wsources").read_text()
    assert 'Path="song.wav"' in wsources
    assert 'Conversion="Vorbis Quality High"' in wsources

    calls = (wwise_root / "Authoring/x64/Release/bin/calls.log").read_text().splitlines()
    assert calls[0].startswith("create-new-project")
    assert calls[1].startswith("convert-external-source")
    # project is cached: a second conversion must not re-create it
    conv.convert(wav, work)
    calls = (wwise_root / "Authoring/x64/Release/bin/calls.log").read_text().splitlines()
    assert sum(1 for c in calls if c.startswith("create-new-project")) == 1


def test_failure_surfaces_stderr(wwise_root: Path, tmp_path: Path) -> None:
    console = wwise_root / "Authoring/x64/Release/bin/WwiseConsole.exe"
    console.write_text("#!/bin/sh\necho 'bad preset' >&2\nexit 3\n")
    console.chmod(console.stat().st_mode | stat.S_IEXEC)
    conv = WwiseWemConverter(wwise_root=wwise_root, use_wine=False)
    wav = tmp_path / "a.wav"
    wav.write_bytes(b"RIFF")
    with pytest.raises(PackagingError, match="exit 3"):
        conv.convert(wav, tmp_path / "w")


def test_env_fallback_resolution(monkeypatch: pytest.MonkeyPatch, wwise_root: Path) -> None:
    import importlib

    monkeypatch.setenv("WWISEROOT", str(wwise_root))
    monkeypatch.delenv("ROCKFORGE_WWISE_ROOT", raising=False)
    import rockforge.config as config

    importlib.reload(config)
    assert config.settings.resolved_wwise_root() == wwise_root
    assert os.environ["WWISEROOT"] == str(wwise_root)
