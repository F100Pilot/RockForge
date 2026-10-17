"""Version numbers: Semantic Versioning, with its pre-releases (docs/VERSIONING.md).

``MAJOR.MINOR.PATCH[-PRERELEASE][+BUILD]`` with the pre-release one of
``dev.N``, ``alpha.N``, ``beta.N`` or ``rc.N``. ``rockforge.__version__`` is
written this way and is the one source of the version; Python's packaging reads
it as PEP 440 (``0.10.0-beta.12`` is ``0.10.0b12``, ``-dev.1`` is ``.dev1``),
so ``to_pep440`` says what pip and an older RockForge will call it.

``+BUILD`` names a build, never the version: two builds of one version carry the
same features and fixes, and compare equal.

No imports from the rest of RockForge, so the release tools can use it as is.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# dev < alpha < beta < rc < the release itself.
STAGES = ("dev", "alpha", "beta", "rc")
_FINAL = len(STAGES)
_PEP440 = {"dev": ".dev", "alpha": "a", "beta": "b", "rc": "rc"}
_NAMES = {"dev": "dev", "alpha": "alpha", "beta": "beta", "rc": "RC"}

_SEMVER = re.compile(
    r"^v?(\d+)\.(\d+)\.(\d+)(?:-(dev|alpha|beta|rc)\.(\d+))?(?:\+([0-9A-Za-z.-]+))?$"
)
# Also the forms already out there: PEP 440 ("0.10.0b3", "0.11.0.dev1",
# "1.0.0rc1") — what RockForge called itself before 0.10.0 beta 13 — and
# tags typed without the dot ("v0.10.0-beta4").
_LOOSE = re.compile(
    r"^v?(\d+)\.(\d+)\.(\d+)(?:[-.]?(dev|a|alpha|b|beta|rc)\.?(\d+))?$", re.IGNORECASE
)
_LOOSE_STAGE = {"dev": "dev", "a": "alpha", "alpha": "alpha", "b": "beta",
                "beta": "beta", "rc": "rc"}


@dataclass(frozen=True)
class Version:
    major: int
    minor: int
    patch: int
    stage: str | None = None  # None = the release itself
    number: int = 0
    build: str = ""

    @property
    def key(self) -> tuple[int, int, int, int, int]:
        """Sorts versions; the build is not part of it."""
        stage = _FINAL if self.stage is None else STAGES.index(self.stage)
        return (self.major, self.minor, self.patch, stage, self.number)

    @property
    def core(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"

    @property
    def is_prerelease(self) -> bool:
        return self.stage is not None

    def __str__(self) -> str:
        text = self.core + (f"-{self.stage}.{self.number}" if self.stage else "")
        return text + (f"+{self.build}" if self.build else "")

    def without_build(self) -> Version:
        return Version(self.major, self.minor, self.patch, self.stage, self.number)


def parse(text: str) -> Version:
    """A version in the project's form (a leading ``v`` allowed); ValueError
    for anything else."""
    m = _SEMVER.match(text.strip())
    if not m:
        raise ValueError(f"not a version (MAJOR.MINOR.PATCH[-dev|alpha|beta|rc.N]): {text!r}")
    major, minor, patch = (int(m.group(i)) for i in (1, 2, 3))
    stage = m.group(4)
    return Version(major, minor, patch, stage, int(m.group(5) or 0), m.group(6) or "")


def parse_loose(text: str) -> Version | None:
    """The project's form, or one of the older spellings; None for anything
    that is not a version (a tag like ``latest``)."""
    text = text.strip()
    try:
        return parse(text)
    except ValueError:
        pass
    m = _LOOSE.match(text)
    if not m:
        return None
    major, minor, patch = (int(m.group(i)) for i in (1, 2, 3))
    if m.group(4) is None:
        return Version(major, minor, patch)
    return Version(major, minor, patch, _LOOSE_STAGE[m.group(4).lower()], int(m.group(5)))


def to_pep440(version: Version | str) -> str:
    v = parse(version) if isinstance(version, str) else version
    return v.core + (f"{_PEP440[v.stage]}{v.number}" if v.stage else "")


def display(version: Version | str) -> str:
    """How the app shows it: "0.10.0 beta 12", "1.0.0 RC 1", "1.0.0"."""
    v = parse(version) if isinstance(version, str) else version
    return v.core + (f" {_NAMES[v.stage]} {v.number}" if v.stage else "")


def changelog_title(version: Version | str) -> str:
    """The changelogs' heading for a version, "0.10.0 beta 12" (the form they
    have always used), "1.0.0 rc 1", "1.0.0"."""
    v = parse(version) if isinstance(version, str) else version
    return v.core + (f" {v.stage} {v.number}" if v.stage else "")


def tag(version: Version | str) -> str:
    v = parse(version) if isinstance(version, str) else version
    return "v" + str(v.without_build())


def allowed_next(current: Version | str, new: Version | str) -> str | None:
    """Why ``new`` cannot follow ``current`` (None = it can).

    It must be newer; inside one MAJOR.MINOR.PATCH the pre-release only moves
    forward (dev → alpha → beta → rc → release) and its number counts up by one
    within a stage, starting at 1; a new MAJOR.MINOR.PATCH is the next PATCH,
    the next MINOR (PATCH 0) or the next MAJOR (MINOR and PATCH 0), and starts
    either as a pre-release numbered 1 or as the release itself."""
    cur = parse(current) if isinstance(current, str) else current
    nxt = parse(new) if isinstance(new, str) else new
    cur, nxt = cur.without_build(), nxt.without_build()
    if nxt.key <= cur.key:
        return f"{nxt} is not newer than {cur}"
    if nxt.stage is not None and nxt.number < 1:
        return "a pre-release is numbered from 1"
    if (nxt.major, nxt.minor, nxt.patch) == (cur.major, cur.minor, cur.patch):
        if cur.stage is None:
            return f"{cur} is already released; the next version has a new number"
        if nxt.stage == cur.stage and nxt.number != cur.number + 1:
            return f"after {cur} comes {cur.stage}.{cur.number + 1}"
        if nxt.stage is not None and nxt.stage != cur.stage and nxt.number != 1:
            return f"a new stage starts at 1 ({nxt.core}-{nxt.stage}.1)"
        return None
    steps = {
        (cur.major, cur.minor, cur.patch + 1),
        (cur.major, cur.minor + 1, 0),
        (cur.major + 1, 0, 0),
    }
    if (nxt.major, nxt.minor, nxt.patch) not in steps:
        return (f"{nxt.core} skips numbers after {cur.core} (next PATCH, MINOR or MAJOR: "
                + ", ".join(sorted(".".join(map(str, s)) for s in steps)) + ")")
    if nxt.stage is not None and nxt.number != 1:
        return f"a new version's first pre-release is {nxt.core}-{nxt.stage}.1"
    return None
