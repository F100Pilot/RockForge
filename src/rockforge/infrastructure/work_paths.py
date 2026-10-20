"""Paths stored in the database that point into an earlier work dir.

Every file a job uses lives under the work dir (``<work>/<job id>/bundle``,
``<work>/uploads/…``, ``<work>/gp/…``), but the database keeps them as absolute
paths. Move the work dir — to a bigger disk, another machine, a restored
backup — and every earlier job points at the old place (issue #6). A path that
no longer exists is looked for under the current work dir by its tail, and
taken when the file is there; one that still exists, or is found nowhere, is
left as it is.
"""

from __future__ import annotations

import re
from pathlib import Path, PurePath, PurePosixPath, PureWindowsPath

# A Windows path read on another system: a drive letter, or a backslash.
_WINDOWS = re.compile(r"^[A-Za-z]:[\\/]|\\")
# The tail must keep at least this many parts ("<job id>/bundle", "gp/<file>"),
# so a bare file name never lands on an unrelated file at the work dir's root.
_MIN_TAIL = 2


def _parts(stored: str) -> tuple[str, ...]:
    path: PurePath = PureWindowsPath(stored) if _WINDOWS.search(stored) else PurePosixPath(stored)
    return path.parts


def rebase(stored: str, work_dir: Path) -> str | None:
    """Where ``stored`` sits now under ``work_dir``, or None when it needs no
    change (it exists, or nothing under ``work_dir`` matches its tail). The
    longest matching tail wins, so the most specific place is taken."""
    if not stored or Path(stored).exists():
        return None
    parts = _parts(stored)
    for start in range(1, len(parts) - _MIN_TAIL + 1):
        candidate = work_dir.joinpath(*parts[start:])
        if candidate.exists():
            return str(candidate)
    return None
