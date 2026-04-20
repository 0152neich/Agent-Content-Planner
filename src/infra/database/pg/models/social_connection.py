"""Per-user social OAuth connection and encrypted token storage."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import Dated, Identified


class SocialConnection(Identified, Dated):
    __tablename__ = "social_connection"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "provider", name="uq_social_connection_user_provider"
        ),
    )

    user_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    access_token_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    refresh_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    provider_account_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    provider_account_name: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
