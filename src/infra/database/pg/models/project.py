"""Project ORM model."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.sql import text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Dated, Identified


class Project(Identified, Dated):
    __tablename__ = "project"

    owner_user_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="active", index=True
    )
    last_active_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )

    __table_args__ = (
        Index(
            "uq_project_owner_name_active",
            "owner_user_id",
            "name",
            unique=True,
            postgresql_where=text('"deletedAt" IS NULL'),
        ),
        Index("ix_project_owner_last_active", "owner_user_id", "last_active_at"),
    )
