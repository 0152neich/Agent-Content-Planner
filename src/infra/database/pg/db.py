"""PostgreSQL database connection and session. Uses PostgresSettings for config."""

from __future__ import annotations

from collections.abc import Sequence
from contextlib import contextmanager
from collections.abc import Iterator
from functools import cached_property
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
from .password_reset_otp import PasswordResetOTPRepositoryImpl
from .project import ProjectRepositoryImpl
from .refresh_token import RefreshTokenRepositoryImpl
from .schemas import PasswordResetOTP
from .user import UserRepositoryImpl
from .user_identity import UserIdentityRepositoryImpl


class SQLDatabase(
    UserRepositoryImpl,
    UserIdentityRepositoryImpl,
    RefreshTokenRepositoryImpl,
    ProjectRepositoryImpl,
    ConversationRepositoryImpl,
    ConversationMessageRepositoryImpl,
    ConversationRunRepositoryImpl,
    PasswordResetOTPRepositoryImpl,
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

    # Re-expose OTP repository methods so static type-checkers can resolve
    # these attributes on SQLDatabase instances without relying on MRO inference.
    def insert_password_reset_otp(
        self, session: Session, model: PasswordResetOTP
    ) -> PasswordResetOTP:
        return PasswordResetOTPRepositoryImpl.insert_password_reset_otp(
            self, session=session, model=model
        )

    def update_password_reset_otp(
        self, session: Session, model: PasswordResetOTP
    ) -> PasswordResetOTP | None:
        return PasswordResetOTPRepositoryImpl.update_password_reset_otp(
            self, session=session, model=model
        )

    def get_password_reset_otp_by_id(
        self, session: Session, id: str
    ) -> PasswordResetOTP | None:
        return PasswordResetOTPRepositoryImpl.get_password_reset_otp_by_id(
            self, session=session, id=id
        )

    def get_password_reset_otps(
        self,
        session: Session,
        filter: dict[str, object] | None = None,
        order_by: Sequence | None = None,
        limit: int | None = None,
    ) -> list[PasswordResetOTP] | None:
        return PasswordResetOTPRepositoryImpl.get_password_reset_otps(
            self,
            session=session,
            filter=filter,
            order_by=order_by,
            limit=limit,
        )
