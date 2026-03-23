"""Abstract interface for RefreshToken persistence."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from sqlalchemy.orm import Session

from ..schemas import RefreshToken


class RefreshTokenRepository(ABC):
    @abstractmethod
    def insert_refresh_token(
        self, session: Session, model: RefreshToken
    ) -> RefreshToken:
        raise NotImplementedError

    @abstractmethod
    def update_refresh_token(
        self, session: Session, model: RefreshToken
    ) -> RefreshToken | None:
        raise NotImplementedError

    @abstractmethod
    def get_refresh_token_by_id(self, session: Session, id: str) -> RefreshToken | None:
        raise NotImplementedError

    @abstractmethod
    def get_refresh_tokens(
        self,
        session: Session,
        filter: dict[str, object] | None = None,
        order_by: Sequence | None = None,
        limit: int | None = None,
    ) -> list[RefreshToken] | None:
        raise NotImplementedError
