"""Social connection repository implementation."""

from __future__ import annotations

from collections.abc import Sequence
from functools import partial
from typing import cast

from sqlalchemy.orm import Session

from shared.logging import get_logger

from .models import SocialConnection as SocialConnectionModel
from .repositories import SocialConnectionRepository
from .schemas import SocialConnection
from .utils import _get_data, _get_data_by_id, _insert, _update

logger = get_logger(__name__)

_insert_social_connection = partial(
    _insert, logger, SocialConnectionModel, SocialConnection
)
_update_social_connection = partial(
    _update, logger, SocialConnectionModel, SocialConnection
)
_get_social_connection_by_id = partial(
    _get_data_by_id, logger, SocialConnectionModel, SocialConnection
)
_get_social_connections = partial(
    _get_data, logger, SocialConnectionModel, SocialConnection
)


class SocialConnectionRepositoryImpl(SocialConnectionRepository):
    def insert_social_connection(
        self, session: Session, model: SocialConnection
    ) -> SocialConnection:
        return cast(SocialConnection, _insert_social_connection(session, model))

    def update_social_connection(
        self, session: Session, model: SocialConnection
    ) -> SocialConnection | None:
        result = _update_social_connection(session, model)
        return cast(SocialConnection, result) if result else None

    def get_social_connection_by_id(
        self, session: Session, id: str
    ) -> SocialConnection | None:
        result = _get_social_connection_by_id(session, id)
        return cast(SocialConnection, result) if result else None

    def get_social_connections(
        self,
        session: Session,
        filter: dict[str, object] | None = None,
        order_by: Sequence | None = None,
        limit: int | None = None,
    ) -> list[SocialConnection] | None:
        result = _get_social_connections(session, filter, order_by, limit)
        return cast(list[SocialConnection], result) if result else None
