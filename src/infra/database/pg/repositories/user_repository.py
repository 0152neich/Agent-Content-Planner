"""Abstract interface for User persistence. Implemented by UserRepositoryImpl."""

from __future__ import annotations

from abc import ABC
from abc import abstractmethod
from collections.abc import Sequence

from sqlalchemy.orm import Session

from ..schemas import User


class UserRepository(ABC):
    @abstractmethod
    def insert_user(self, session: Session, model: User) -> User:
        raise NotImplementedError

    @abstractmethod
    def update_user(self, session: Session, model: User) -> User | None:
        raise NotImplementedError

    @abstractmethod
    def delete_user(self, session: Session, id: str) -> User | None:
        raise NotImplementedError

    @abstractmethod
    def get_user_by_id(self, session: Session, id: str) -> User | None:
        raise NotImplementedError

    @abstractmethod
    def get_users(
        self,
        session: Session,
        filter: dict[str, object] | None = None,
        order_by: Sequence | None = None,
        limit: int | None = None,
    ) -> list[User] | None:
        raise NotImplementedError
