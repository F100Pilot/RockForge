"""The "what's new" banner: the changelogs' entries between the version a user
last saw and this one (``rockforge/whats_new.py``, ``GET /whats-new``)."""

from __future__ import annotations

from pathlib import Path

import pytest

from rockforge import whats_new

CHANGELOG = """# What's new

## [Unreleased]

### New
- **Not out yet:** must never show.

## [0.10.0 beta 3] — 2026-10-03

### New
- **Bend view:** the score draws
  bends as arrows, with `bend` in code.
- A second item.

### Fixed
- **Crash on load** fixed.

## [0.10.0 beta 2] — 2026-10-02

### Fixed
- Something from beta 2.

## [0.10.0 beta 1] — 2026-10-01

- An item before any group.
"""


@pytest.fixture
def changelog(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "CHANGELOG.en.md"
    path.write_text(CHANGELOG, encoding="utf-8")
    monkeypatch.setattr(whats_new, "changelog_path", lambda lang: path)
    return path


def test_the_changelog_is_read_section_by_section_without_the_unreleased_one() -> None:
    releases = whats_new.parse_changelog(CHANGELOG)
    assert [r.version for r in releases] == ["0.10.0-beta.3", "0.10.0-beta.2", "0.10.0-beta.1"]
    beta3 = releases[0]
    assert (beta3.display, beta3.date) == ("0.10.0 beta 3", "2026-10-03")
    assert [(g.title, len(g.items)) for g in beta3.groups] == [("New", 2), ("Fixed", 1)]
    # a wrapped item is one line, its Markdown kept for the page to render
    assert beta3.groups[0].items[0] == (
        "**Bend view:** the score draws bends as arrows, with `bend` in code.")
    assert releases[2].groups[0].title == "" and releases[2].groups[0].items == [
        "An item before any group."]


def test_every_version_after_the_one_last_seen_up_to_this_one(changelog: Path) -> None:
    ok, rel = whats_new.since("0.10.0-beta.1", "0.10.0-beta.3", "en")
    assert ok and [r.version for r in rel] == ["0.10.0-beta.3", "0.10.0-beta.2"]
    # the older spelling of a version is read, and a build part is ignored
    ok, rel = whats_new.since("0.10.0b2", "0.10.0-beta.3+ci.5.abc", "en")
    assert [r.version for r in rel] == ["0.10.0-beta.3"]
    # nothing newer than the running version, even if the changelog had it
    assert [r.version for r in whats_new.since("0.10.0-beta.1", "0.10.0-beta.2", "en")[1]] == [
        "0.10.0-beta.2"]
    # never seen: this version's own entries only
    assert [r.version for r in whats_new.since(None, "0.10.0-beta.3", "en")[1]] == [
        "0.10.0-beta.3"]
    # already seen, or a downgrade: nothing
    assert whats_new.since("0.10.0-beta.3", "0.10.0-beta.3", "en")[1] == []
    assert whats_new.since("0.10.0-beta.5", "0.10.0-beta.3", "en")[1] == []


def test_without_the_changelogs_there_is_nothing_to_show_and_it_says_so(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(whats_new, "changelog_path", lambda lang: None)
    assert whats_new.since("0.10.0-beta.1", "0.10.0-beta.3", "en") == (False, [])


def test_the_real_changelogs_carry_this_version_in_both_languages() -> None:
    from rockforge import __version__

    for lang in ("pt", "en"):
        ok, rel = whats_new.since(None, __version__, lang)
        assert ok and rel and rel[0].groups and rel[0].groups[0].items, lang
    pt = whats_new.since(None, __version__, "pt")[1][0].groups[0].title
    en = whats_new.since(None, __version__, "en")[1][0].groups[0].title
    assert pt != en  # each language its own file
