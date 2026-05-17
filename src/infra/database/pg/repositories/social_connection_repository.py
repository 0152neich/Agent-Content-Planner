"""Abstract interface for SocialConnection persistence."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from sqlalchemy.orm import Session

from ..schemas import SocialConnection


class SocialConnectionRepository(ABC):
    @abstractmethod
    def insert_social_connection(
        self, session: Session, model: SocialConnection
    ) -> SocialConnection:
        raise NotImplementedError

    @abstractmethod
    def update_social_connection(
        self, session: Session, model: SocialConnection
    ) -> SocialConnection | None:
        raise NotImplementedError

    @abstractmethod
    def get_social_connection_by_id(
        self, session: Session, id: str
    ) -> SocialConnection | None:
        raise NotImplementedError

    @abstractmethod
    def get_social_connections(
        self,
        session: Session,
        filter: dict[str, object] | None = None,
        order_by: Sequence | None = None,
        limit: int | None = None,
    ) -> list[SocialConnection] | None:
        raise NotImplementedError
