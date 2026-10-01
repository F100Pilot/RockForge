"""The licence, the third-party notices and the legal notice exist, name every
vendored file, and travel with the standalone build — the MIT licences of the
vendored code (Rocksmith2014.NET, three.js) require their notice in every copy."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Files copied into the repo from other projects. Adding one here without
# naming it in THIRD_PARTY_NOTICES.md fails below.
VENDORED = (
    "src/rockforge/infrastructure/packaging/wwise_templates",
    "src/rockforge/infrastructure/packaging/gear/tone_gear_data.json",
    "src/rockforge/infrastructure/packaging/gear/default_tones",
    "src/rockforge/infrastructure/packaging/psarc/flatmodels",
    "src/rockforge/infrastructure/packaging/psarc/vocals_symbols.bin",
    "web/vendor/three",
)


def _build_exe():  # type: ignore[no-untyped-def]
    spec = importlib.util.spec_from_file_location("build_exe", ROOT / "build_exe.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_licence_notices_and_legal_notice_are_there() -> None:
    licence = (ROOT / "LICENSE").read_text(encoding="utf-8")
    assert licence.startswith("MIT License")
    notices = (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    assert "Copyright (c) 2020 Tapio Malmberg" in notices  # Rocksmith2014.NET's MIT notice
    legal = (ROOT / "LEGAL.md").read_text(encoding="utf-8")
    assert "Ubisoft" in legal and "## Português" in legal and "## English" in legal


def test_every_vendored_file_is_named_in_the_notices() -> None:
    notices = (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    for path in VENDORED:
        assert (ROOT / path).exists(), path
        assert path in notices, f"{path} is vendored but not in THIRD_PARTY_NOTICES.md"


def test_the_standalone_build_ships_them_beside_the_exe(tmp_path) -> None:
    build_exe = _build_exe()
    build_exe.copy_legal_files(tmp_path)
    for name in build_exe.LEGAL_FILES:
        assert (tmp_path / name).read_bytes() == (ROOT / name).read_bytes()
    assert set(build_exe.LEGAL_FILES) == {"LICENSE", "THIRD_PARTY_NOTICES.md", "LEGAL.md"}
