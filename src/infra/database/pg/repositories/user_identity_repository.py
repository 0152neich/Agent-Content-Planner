"""Abstract interface for UserIdentity persistence."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from sqlalchemy.orm import Session

from ..schemas import UserIdentity


class UserIdentityRepository(ABC):
    @abstractmethod
    def insert_user_identity(
        self, session: Session, model: UserIdentity
    ) -> UserIdentity:
        raise NotImplementedError

    @abstractmethod
    def update_user_identity(
        self, session: Session, model: UserIdentity
    ) -> UserIdentity | None:
        raise NotImplementedError

    @abstractmethod
    def get_user_identity_by_id(self, session: Session, id: str) -> UserIdentity | None:
        raise NotImplementedError

    @abstractmethod
    def get_user_identities(
        self,
        session: Session,
        filter: dict[str, object] | None = None,
        order_by: Sequence | None = None,
        limit: int | None = None,
    ) -> list[UserIdentity] | None:
        raise NotImplementedError
