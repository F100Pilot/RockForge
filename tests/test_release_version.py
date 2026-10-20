"""The version is written once (rockforge.__version__, Semantic Versioning);
the copies that cannot read it must name the same release.

pyproject.toml reads it (dynamic version); the installer (installer.iss, read
by Inno Setup and by the release workflow) and the changelogs' headings are
copies, checked here and changed together by tools/bump_version.py. A release
built with two of these out of step installs as one version and reports another
in the app's own corner.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest

from rockforge import __version__, versioning

ROOT = Path(__file__).resolve().parents[1]


def _iss_version() -> str:
    m = re.search(r'#define MyAppVersion "([^"]+)"', (ROOT / "installer.iss").read_text())
    assert m
    return m.group(1)


def test_the_version_is_semantic_versioning_with_no_build_part() -> None:
    v = versioning.parse(__version__)
    assert str(v) == __version__
    assert not v.build  # the build is named at build time, never in the source


def test_pyproject_reads_the_version_instead_of_repeating_it() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert "version" not in pyproject["project"]
    assert "version" in pyproject["project"]["dynamic"]
    attr = pyproject["tool"]["setuptools"]["dynamic"]["version"]["attr"]
    assert attr == "rockforge.__version__"


def test_the_installer_names_the_same_version() -> None:
    assert _iss_version() == __version__


def test_both_changelogs_describe_the_released_version() -> None:
    title = versioning.changelog_title(__version__)
    for name in ("CHANGELOG.md", "CHANGELOG.en.md"):
        text = (ROOT / name).read_text()
        heading = rf"^## \[{re.escape(title)}\] — \d{{4}}-\d{{2}}-\d{{2}}$"
        assert re.search(heading, text, re.M), name


@pytest.mark.parametrize(
    ("text", "pep440", "shown", "heading"),
    [
        ("0.10.0-beta.12", "0.10.0b12", "0.10.0 beta 12", "0.10.0 beta 12"),
        ("2.0.0-dev.1", "2.0.0.dev1", "2.0.0 dev 1", "2.0.0 dev 1"),
        ("2.4.0-rc.1", "2.4.0rc1", "2.4.0 RC 1", "2.4.0 rc 1"),
        ("2.4.1", "2.4.1", "2.4.1", "2.4.1"),
    ],
)
def test_each_form_of_a_version(text: str, pep440: str, shown: str, heading: str) -> None:
    from packaging.version import Version

    v = versioning.parse(text)
    assert versioning.to_pep440(v) == pep440 == str(Version(text))
    assert versioning.display(v) == shown
    assert versioning.changelog_title(v) == heading
    assert versioning.tag(v) == "v" + text


def test_versions_sort_by_stage_and_ignore_the_build() -> None:
    order = ["2.0.0-dev.1", "2.0.0-dev.2", "2.0.0-alpha.1", "2.0.0-beta.1", "2.0.0-beta.10",
             "2.0.0-rc.1", "2.0.0", "2.0.1", "2.1.0", "10.0.0"]
    keys = [versioning.parse(v).key for v in order]
    assert keys == sorted(keys) and len(set(keys)) == len(keys)
    assert versioning.parse("1.0.0+ci.7.abc").key == versioning.parse("1.0.0").key


@pytest.mark.parametrize("bad", ["1.0", "1.0.0-beta", "1.0.0-preview.1", "01.0.0x", "1.0.0b1"])
def test_anything_else_is_not_a_version(bad: str) -> None:
    with pytest.raises(ValueError):
        versioning.parse(bad)


def test_the_older_spellings_still_read() -> None:
    assert versioning.parse_loose("0.10.0b3") == versioning.parse("0.10.0-beta.3")
    assert versioning.parse_loose("v0.10.0-beta4") == versioning.parse("0.10.0-beta.4")
    assert versioning.parse_loose("0.11.0.dev2") == versioning.parse("0.11.0-dev.2")
    assert versioning.parse_loose("latest") is None


@pytest.mark.parametrize(
    ("cur", "new"),
    [
        ("0.10.0-beta.12", "0.10.0-beta.13"),
        ("0.10.0-beta.13", "0.10.0-rc.1"),
        ("0.10.0-rc.2", "0.10.0"),
        ("0.10.0", "0.10.1"),
        ("0.10.0", "0.11.0-beta.1"),
        ("0.10.0", "1.0.0-dev.1"),
        ("0.10.0-beta.12", "0.11.0-beta.1"),
        ("1.2.3-dev.4", "1.2.3-beta.1"),
    ],
)
def test_what_may_come_next(cur: str, new: str) -> None:
    assert versioning.allowed_next(cur, new) is None


@pytest.mark.parametrize(
    ("cur", "new"),
    [
        ("0.10.0-beta.12", "0.10.0-beta.12"),  # the same number twice
        ("0.10.0-beta.12", "0.10.0-beta.14"),  # a skipped beta
        ("0.10.0-rc.1", "0.10.0-beta.13"),  # back a stage
        ("0.10.0-beta.12", "0.10.0-rc.2"),  # a stage not starting at 1
        ("0.10.0", "0.10.0-beta.1"),  # a pre-release of something released
        ("0.10.0", "0.12.0"),  # a skipped MINOR
        ("0.10.0", "0.10.1-beta.2"),
        ("0.10.0", "0.9.9"),
    ],
)
def test_what_may_not(cur: str, new: str) -> None:
    assert versioning.allowed_next(cur, new) is not None


def test_a_tag_with_or_without_the_leading_v_starts_the_release() -> None:
    """BUG-0267: the workflow listened to 'v*' only, so a release tagged
    '0.10.0b3' never built and was published with no files."""
    import fnmatch

    wf = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    m = re.search(r"^\s*tags:\s*(.*)$", wf, re.M)
    assert m, "release.yml listens to no tags"
    patterns = re.findall(r"[\"']([^\"']+)[\"']", m.group(1))
    for tag in ("v0.11.1-beta.1", "0.11.1-beta.1"):
        assert any(fnmatch.fnmatchcase(tag, p) for p in patterns), tag
    assert "TrimStart('v')" in wf  # compared with installer.iss without the v
