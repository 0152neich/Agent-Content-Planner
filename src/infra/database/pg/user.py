"""User repository implementation: CRUD for User using shared utils."""

from __future__ import annotations

from collections.abc import Sequence
from functools import partial
from typing import cast

from shared.logging import get_logger
from sqlalchemy.orm import Session

from .models import User as UserModel
from .repositories import UserRepository
from .schemas import User
from .utils import _delete
from .utils import _get_data
from .utils import _get_data_by_id
from .utils import _insert
from .utils import _update

logger = get_logger(__name__)

_insert_user = partial(_insert, logger, UserModel, User)
_update_user = partial(_update, logger, UserModel, User)
_delete_user = partial(_delete, logger, UserModel, User)
_get_users = partial(_get_data, logger, UserModel, User)
_get_user_by_id = partial(_get_data_by_id, logger, UserModel, User)


class UserRepositoryImpl(UserRepository):
    def insert_user(self, session: Session, model: User) -> User:
        return cast(User, _insert_user(session, model))

    def update_user(self, session: Session, model: User) -> User | None:
        result = _update_user(session, model)
        return cast(User, result) if result else None

    def delete_user(self, session: Session, id: str) -> User | None:
        result = _delete_user(session, id)
        return cast(User, result) if result else None

    def get_users(
        self,
        session: Session,
        filter: dict[str, object] | None = None,
        order_by: Sequence | None = None,
        limit: int | None = None,
    ) -> list[User] | None:
        result = _get_users(session, filter, order_by, limit)
        return cast(list[User], result) if result else None

    def get_user_by_id(self, session: Session, id: str) -> User | None:
        result = _get_user_by_id(session, id)
        return cast(User, result) if result else None
