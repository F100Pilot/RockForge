"""Persistence: job tracking with SQLAlchemy 2.x (SQLite dev / PostgreSQL prod)."""

from __future__ import annotations

import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, Enum, String, Text, create_engine, inspect
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker


class JobStatus(enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class Base(DeclarativeBase):
    pass


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    # Indexed: list_jobs sorts by created_at.desc() on every /jobs poll (the web
    # UI polls every ~5s per open tab). status is indexed too for the common
    # "still-running" scans. Cheap on SQLite, matters once job history grows on
    # Postgres. (create_all adds these for a fresh DB; an existing SQLite file
    # keeps working unindexed — it just doesn't gain the index retroactively.)
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus), default=JobStatus.PENDING, index=True
    )
    source: Mapped[str] = mapped_column(Text)
    source_type: Mapped[str] = mapped_column(String(16))  # "gp" (only type created today)
    title: Mapped[str] = mapped_column(String(255))
    artist: Mapped[str] = mapped_column(String(255))
    album: Mapped[str] = mapped_column(String(255), default="")
    year: Mapped[int | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True
    )
    stage: Mapped[str | None] = mapped_column(String(32), nullable=True)  # current pipeline stage
    params: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)  # rebuild/GP overrides
    warnings: Mapped[list[str]] = mapped_column(JSON, default=list)
    note_counts: Mapped[dict[str, int]] = mapped_column(JSON, default=dict)
    bundle_dir: Mapped[str | None] = mapped_column(Text, nullable=True)
    psarc_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class SchemaOutOfDateError(RuntimeError):
    """An existing database predates a column the code now requires."""


def _check_schema(engine: Engine) -> None:
    """Fail LOUDLY, once, when an existing table is missing a column.

    There is no migration tool here, and ``create_all`` creates missing TABLES
    but never ALTERs an existing one. That is survivable by design — everything
    that changes lives in the ``params`` JSON column, so the ``jobs`` schema is
    effectively frozen — but if a column ever is added, every query against an
    older database dies with a bare ``no such column`` on request after request,
    with nothing saying why or what to do. Naming the drift at startup turns
    that into one actionable message. Deliberately detect-only: hand-rolled
    auto-ALTER is a migration system in disguise, and this app has no need of
    one. Never blocks startup for any other reason (an inspector that cannot
    read the dialect just yields nothing).
    """
    try:
        inspector = inspect(engine)
        if not inspector.has_table(Job.__tablename__):
            return  # fresh database; create_all built it correctly
        present = {c["name"] for c in inspector.get_columns(Job.__tablename__)}
    except Exception:  # noqa: BLE001 — a schema check must not be the thing that breaks
        return
    missing = sorted(c.name for c in Job.__table__.columns if c.name not in present)
    if missing:
        raise SchemaOutOfDateError(
            f"the '{Job.__tablename__}' table is missing column(s) {missing}: this "
            "database predates the current version of RockForge. There is no "
            "migration tool — delete the database file (jobs are rebuildable from "
            "their Guitar Pro file and recording) or add the columns by hand."
        )


def make_session_factory(database_url: str) -> sessionmaker[Session]:
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)
    _check_schema(engine)
    return sessionmaker(engine, expire_on_commit=False)
