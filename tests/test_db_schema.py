"""The startup schema check.

There is no migration tool here, and ``create_all`` creates missing TABLES but
never ALTERs an existing one. That is survivable by design — everything that
changes lives in the ``params`` JSON column, so the ``jobs`` schema is
effectively frozen — but if a column ever is added, every query against an older
database dies with a bare "no such column" on request after request, with
nothing saying why or what to do about it.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from rockforge.infrastructure.db.models import SchemaOutOfDateError, make_session_factory


def test_a_fresh_database_is_created_and_accepted(tmp_path: Path) -> None:
    make_session_factory(f"sqlite:///{tmp_path}/fresh.db")  # must not raise


def test_a_database_missing_a_column_fails_loudly_and_says_what_to_do(
    tmp_path: Path,
) -> None:
    db = tmp_path / "old.db"
    make_session_factory(f"sqlite:///{db}")
    # Simulate a database written by an older version, before a column existed.
    con = sqlite3.connect(db)
    con.execute("ALTER TABLE jobs DROP COLUMN psarc_path")
    con.commit()
    con.close()

    with pytest.raises(SchemaOutOfDateError) as exc:
        make_session_factory(f"sqlite:///{db}")
    message = str(exc.value)
    assert "psarc_path" in message, "the message must name the drifting column"
    assert "migration" in message, "and tell the user what to do about it"


def test_the_check_never_becomes_the_thing_that_breaks_startup(tmp_path: Path) -> None:
    """Detect-only, and defensive: a database the inspector cannot read must
    still start. A schema check that itself blocks the app is worse than the
    problem it reports."""
    import rockforge.infrastructure.db.models as models

    def _boom(_engine: object) -> None:
        raise RuntimeError("inspector unavailable on this dialect")

    original = models.inspect
    models.inspect = _boom  # type: ignore[assignment]
    try:
        make_session_factory(f"sqlite:///{tmp_path}/x.db")  # must not raise
    finally:
        models.inspect = original  # type: ignore[assignment]
