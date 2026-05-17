"""Conversation run ORM model."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Dated, Identified


class ConversationRun(Identified, Dated):
    __tablename__ = "conversation_run"

    conversation_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("conversation.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    project_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("project.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    request_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    response_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="completed", index=True
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    source_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    platforms: Mapped[list | None] = mapped_column(JSON, nullable=True, default=list)

    __table_args__ = (
        Index("ix_conversation_run_project_created", "project_id", "createdAt"),
    )
