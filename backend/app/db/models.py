"""Persistence model.

`run_events` is append-only and is the single source of truth for progress.
The SSE endpoint replays it from seq 0 before tailing, so a browser that
reconnects mid-run sees the whole history rather than joining blind -- which
also means progress survives a page refresh.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


JsonB = JSON().with_variant(JSONB, "postgresql")


class RunStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    # Set at startup for runs still marked running: an in-process worker dies
    # with the process, and a silently stuck run is worse than a failed one.
    INTERRUPTED = "interrupted"


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), index=True)

    submission: Mapped[dict] = mapped_column(JsonB)
    status: Mapped[str] = mapped_column(String(20), default=RunStatus.QUEUED, index=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    score_total: Mapped[float | None] = mapped_column(Float, nullable=True)
    score_band: Mapped[str | None] = mapped_column(String(20), nullable=True)

    usage: Mapped[dict | None] = mapped_column(JsonB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    events: Mapped[list["RunEvent"]] = relationship(
        back_populates="run", cascade="all, delete-orphan", order_by="RunEvent.seq"
    )
    report: Mapped["Report | None"] = relationship(
        back_populates="run", cascade="all, delete-orphan", uselist=False
    )


class RunEvent(Base):
    """Append-only progress log. Never updated in place."""

    __tablename__ = "run_events"
    __table_args__ = (Index("ix_run_events_run_seq", "run_id", "seq", unique=True),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("runs.id", ondelete="CASCADE"), index=True
    )
    seq: Mapped[int] = mapped_column(Integer)

    node: Mapped[str] = mapped_column(String(64))
    phase: Mapped[str] = mapped_column(String(24))  # started | completed | failed
    payload: Mapped[dict | None] = mapped_column(JsonB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    run: Mapped["Run"] = relationship(back_populates="events")


class Evidence(Base):
    """Run-scoped claims, retained so a report's sources stay inspectable."""

    __tablename__ = "evidence"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("runs.id", ondelete="CASCADE"), index=True
    )
    claim: Mapped[dict] = mapped_column(JsonB)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    # False when the model cited a URL that search never actually retrieved.
    attribution_verified: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("runs.id", ondelete="CASCADE"), unique=True, index=True
    )
    content: Mapped[dict] = mapped_column(JsonB)
    score: Mapped[dict] = mapped_column(JsonB)
    markdown: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    run: Mapped["Run"] = relationship(back_populates="report")


class ResearchCache(Base):
    """Reusable research keyed by normalised industry/geo/competitor.

    Reuse is the largest single cost lever: repeated validations in the same
    industry re-ask the same questions, and each one is billed per search.
    """

    __tablename__ = "research_cache"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cache_key: Mapped[str] = mapped_column(String(512), unique=True, index=True)
    kind: Mapped[str] = mapped_column(String(32))
    payload: Mapped[dict] = mapped_column(JsonB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
