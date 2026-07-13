"""DB model schema guards (MIN-3): the columns the hot query paths sort/scan on
must carry an index on a freshly-created database."""

from __future__ import annotations

from sqlalchemy import create_engine, inspect

from rockforge.infrastructure.db.models import make_session_factory


def test_jobs_table_indexes_created_at_and_status(tmp_path) -> None:
    """list_jobs sorts by created_at.desc() on every /jobs poll; both created_at
    and status must be indexed so the sort/scan doesn't degrade as job history
    grows (matters on Postgres). create_all builds the indexes for a fresh DB."""
    url = f"sqlite:///{tmp_path}/jobs.db"
    make_session_factory(url)  # runs Base.metadata.create_all

    engine = create_engine(url)
    indexed_columns = {
        col
        for index in inspect(engine).get_indexes("jobs")
        for col in index["column_names"]
    }
    assert "created_at" in indexed_columns
    assert "status" in indexed_columns
