"""PostgreSQL database connection and session. Uses PostgresSettings for config."""

from __future__ import annotations

from contextlib import contextmanager
from functools import cached_property
from collections.abc import Iterator
from urllib.parse import quote_plus

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker

from shared.settings.models import PostgresSettings

from .models import Base
from .conversation import ConversationRepositoryImpl
from .conversation_message import ConversationMessageRepositoryImpl
from .conversation_run import ConversationRunRepositoryImpl
from .project import ProjectRepositoryImpl
from .refresh_token import RefreshTokenRepositoryImpl
from .user import UserRepositoryImpl


class SQLDatabase(
    UserRepositoryImpl,
    RefreshTokenRepositoryImpl,
    ProjectRepositoryImpl,
    ConversationRepositoryImpl,
    ConversationMessageRepositoryImpl,
    ConversationRunRepositoryImpl,
):
    """PostgreSQL-backed database: session factory + User repository implementation.

    Pass a PostgresSettings instance (e.g. from Settings().postgres or PostgresSettings()).
    """

    def __init__(self, config: PostgresSettings) -> None:
        self._config = config

    @cached_property
    def engine(self) -> Engine:
        url = (
            f"postgresql+psycopg://{quote_plus(self._config.user)}:"
            f"{quote_plus(self._config.password)}@{self._config.host}:{self._config.port}/{self._config.db}"
        )
        engine = create_engine(
            url,
            pool_size=self._config.pool_size,
            max_overflow=self._config.max_overflow,
            pool_timeout=self._config.pool_timeout,
            pool_recycle=self._config.pool_recycle,
            pool_pre_ping=True,
        )
        if self._config.create_tables:
            Base.metadata.create_all(engine)
        return engine

    @cached_property
    def sessionmaker(self) -> sessionmaker[Session]:
        return sessionmaker(bind=self.engine, autoflush=False, class_=Session)

    @contextmanager
    def get_session(self) -> Iterator[Session]:
        session: Session = self.sessionmaker()
        try:
            yield session
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
