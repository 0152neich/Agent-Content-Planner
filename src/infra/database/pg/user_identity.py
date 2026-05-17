"""User identity repository implementation."""

from __future__ import annotations

from collections.abc import Sequence
from functools import partial
from typing import cast

from sqlalchemy.orm import Session

from shared.logging import get_logger

from .models import UserIdentity as UserIdentityModel
from .repositories import UserIdentityRepository
from .schemas import UserIdentity
from .utils import _get_data, _get_data_by_id, _insert, _update

logger = get_logger(__name__)

_insert_user_identity = partial(_insert, logger, UserIdentityModel, UserIdentity)
_update_user_identity = partial(_update, logger, UserIdentityModel, UserIdentity)
_get_user_identity_by_id = partial(
    _get_data_by_id, logger, UserIdentityModel, UserIdentity
)
_get_user_identities = partial(_get_data, logger, UserIdentityModel, UserIdentity)


class UserIdentityRepositoryImpl(UserIdentityRepository):
    def insert_user_identity(
        self, session: Session, model: UserIdentity
    ) -> UserIdentity:
        return cast(UserIdentity, _insert_user_identity(session, model))

    def update_user_identity(
        self, session: Session, model: UserIdentity
    ) -> UserIdentity | None:
        result = _update_user_identity(session, model)
        return cast(UserIdentity, result) if result else None

    def get_user_identity_by_id(self, session: Session, id: str) -> UserIdentity | None:
        result = _get_user_identity_by_id(session, id)
        return cast(UserIdentity, result) if result else None

    def get_user_identities(
        self,
        session: Session,
        filter: dict[str, object] | None = None,
        order_by: Sequence | None = None,
        limit: int | None = None,
    ) -> list[UserIdentity] | None:
        result = _get_user_identities(session, filter, order_by, limit)
        return cast(list[UserIdentity], result) if result else None
