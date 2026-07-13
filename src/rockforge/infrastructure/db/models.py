"""Persistence: job tracking with SQLAlchemy 2.x (SQLite dev / PostgreSQL prod)."""

from __future__ import annotations

import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, Enum, String, Text, create_engine
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


def make_session_factory(database_url: str) -> sessionmaker[Session]:
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(engine, expire_on_commit=False)
