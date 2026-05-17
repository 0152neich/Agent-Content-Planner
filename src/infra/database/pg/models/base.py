"""SQLAlchemy declarative base and abstract mixins for ORM models."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column


class Base(DeclarativeBase):
    pass


class Dated(Base):
    """Mixin adding createdAt, updatedAt, deletedAt. Supports soft delete."""

    __abstract__ = True

    createdAt: Mapped[datetime] = mapped_column(insert_default=func.now())
    updatedAt: Mapped[datetime | None] = mapped_column(
        onupdate=func.now(),
        nullable=True,
    )
    deletedAt: Mapped[datetime | None] = mapped_column(nullable=True)


class Identified(Base):
    """Mixin adding string primary key id."""

    __abstract__ = True

    id: Mapped[str] = mapped_column(primary_key=True, index=True)
