"""Autopost job ORM model."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Dated, Identified


class AutopostJob(Identified, Dated):
    __tablename__ = "autopost_job"

    project_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("project.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    platform: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    keyword: Mapped[str] = mapped_column(Text, nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC")
    scheduled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="QUEUED", index=True
    )
    page_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    draft_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    final_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider_post_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    provider_schedule_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    conversation_run_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    quality_score: Mapped[float | None] = mapped_column(nullable=True)
    quality_flags: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    next_action: Mapped[str | None] = mapped_column(String(32), nullable=True)
    job_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)

    __table_args__ = (
        Index("ix_autopost_job_project_created", "project_id", "createdAt"),
        Index("ix_autopost_job_status_scheduled", "status", "scheduled_at"),
        Index("ix_autopost_job_user_created", "user_id", "createdAt"),
    )
