"""User identity ORM model for social login providers."""

from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Dated, Identified


class UserIdentity(Identified, Dated):
    __tablename__ = "user_identity"
    __table_args__ = (
        Index(
            "uq_user_identity_provider_sub_active",
            "provider",
            "provider_sub",
            unique=True,
            postgresql_where=text('"deletedAt" IS NULL'),
        ),
        Index(
            "uq_user_identity_user_provider_active",
            "user_id",
            "provider",
            unique=True,
            postgresql_where=text('"deletedAt" IS NULL'),
        ),
    )

    user_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    provider_sub: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    picture_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
