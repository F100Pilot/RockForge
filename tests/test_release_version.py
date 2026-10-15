"""The version is written in four places; they must name the same release.

pyproject.toml and rockforge.__version__ use PEP 440 ("0.10.0b2"), the
installer and the git tag the release workflow checks it against use
"0.10.0-beta.2", and each changelog has a section for every released version.
A release built with two of these out of step installs as one version and
reports another in the app's own corner.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

from rockforge import __version__

ROOT = Path(__file__).resolve().parents[1]


def _iss_version() -> str:
    m = re.search(r'#define MyAppVersion "([^"]+)"', (ROOT / "installer.iss").read_text())
    assert m
    return m.group(1)


def _as_pep440(release: str) -> str:
    """"0.10.0-beta.2" → "0.10.0b2"; "1.0.0" stays."""
    m = re.fullmatch(r"(\d+\.\d+\.\d+)(?:-(alpha|beta|rc)\.(\d+))?", release)
    assert m, f"installer.iss version {release!r} is not X.Y.Z or X.Y.Z-beta.N"
    base, kind, n = m.groups()
    return base + ({"alpha": "a", "beta": "b", "rc": "rc"}[kind] + n if kind else "")


def test_the_installer_the_package_and_the_app_name_the_same_version() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    assert _as_pep440(_iss_version()) == project == __version__


def test_both_changelogs_describe_the_released_version() -> None:
    m = re.fullmatch(r"(\d+\.\d+\.\d+)(?:-beta\.(\d+))?", _iss_version())
    assert m
    title = m.group(1) + (f" beta {m.group(2)}" if m.group(2) else "")
    for name in ("CHANGELOG.md", "CHANGELOG.en.md"):
        assert f"## [{title}]" in (ROOT / name).read_text(), name
