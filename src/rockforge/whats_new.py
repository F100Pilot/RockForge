"""What changed since the version a user last saw — read from the changelogs
(``CHANGELOG.md`` in Portuguese, ``CHANGELOG.en.md`` in English), the same
entries the releases are made from, so the app never says something the
changelog does not.

The files sit at the repository root in a source install and at the bundle's
root in the ``.exe`` (``rockforge.spec`` ships them there). An install that
has neither (a plain ``pip install`` of the package) has nothing to show and
says so (``available`` false) rather than inventing it.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from rockforge import versioning

MAX_VERSIONS = 30   # a user coming from far back sees the most recent ones

_FILES = {"pt": "CHANGELOG.md", "en": "CHANGELOG.en.md"}
_HEADING = re.compile(r"^## \[([^\]]+)\](?:\s*[—-]\s*(\S+))?\s*$")


@dataclass
class Group:
    title: str
    items: list[str] = field(default_factory=list)


@dataclass
class Release:
    version: str        # the project's form, "0.10.0-beta.14"
    display: str        # "0.10.0 beta 14"
    date: str
    groups: list[Group] = field(default_factory=list)


def changelog_path(lang: str) -> Path | None:
    """The changelog in ``lang`` (English for any language it is not written in)."""
    name = _FILES.get(lang, _FILES["en"])
    roots = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        roots.append(Path(meipass))
    roots.append(Path(__file__).resolve().parents[2])
    for root in roots:
        if (root / name).is_file():
            return root / name
    return None


def _version_of(title: str) -> versioning.Version | None:
    return versioning.parse_loose(re.sub(r"\s+", "", title))


def parse_changelog(text: str) -> list[Release]:
    """Every released section, newest first as written; "Por lançar"/"Unreleased"
    and anything that is not a version are skipped. Items keep their Markdown
    (bold, code), joined onto one line."""
    releases: list[Release] = []
    current: Release | None = None
    group: Group | None = None
    item: list[str] | None = None

    def close_item() -> None:
        nonlocal item
        if item is not None and group is not None:
            group.items.append(" ".join(part.strip() for part in item).strip())
        item = None

    for line in text.splitlines():
        if line.startswith("## "):
            close_item()
            m = _HEADING.match(line)
            v = _version_of(m.group(1)) if m else None
            current = None
            group = None
            if m and v is not None:
                current = Release(version=str(v), display=versioning.display(v),
                                  date=m.group(2) or "")
                releases.append(current)
        elif current is None:
            continue
        elif line.startswith("### "):
            close_item()
            group = Group(line[4:].strip())
            current.groups.append(group)
        elif line.startswith("- "):
            close_item()
            if group is None:
                group = Group("")
                current.groups.append(group)
            item = [line[2:]]
        elif item is not None and line.startswith("  ") and line.strip():
            item.append(line)
        elif not line.strip():
            close_item()
    close_item()
    return releases


def since(seen: str | None, current: str, lang: str) -> tuple[bool, list[Release]]:
    """(the changelog was found, the releases after ``seen`` up to ``current``,
    newest first). With no ``seen``, just ``current``'s own section."""
    path = changelog_path(lang)
    if path is None:
        return False, []
    now = versioning.parse_loose(current)
    if now is None:
        return True, []
    after = versioning.parse_loose(seen) if seen else None
    out = []
    for rel in parse_changelog(path.read_text(encoding="utf-8")):
        v = versioning.parse(rel.version)
        if v.key > now.without_build().key:
            continue
        if after is None:
            if v.key == now.without_build().key:
                out.append(rel)
            continue
        if v.key > after.without_build().key:
            out.append(rel)
    return True, out[:MAX_VERSIONS]
