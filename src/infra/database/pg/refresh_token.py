"""Refresh token repository implementation."""

from __future__ import annotations

from collections.abc import Sequence
from functools import partial
from typing import cast

from shared.logging import get_logger
from sqlalchemy.orm import Session

from .models import RefreshToken as RefreshTokenModel
from .repositories import RefreshTokenRepository
from .schemas import RefreshToken
from .utils import _get_data, _get_data_by_id, _insert, _update

logger = get_logger(__name__)

_insert_refresh_token = partial(_insert, logger, RefreshTokenModel, RefreshToken)
_update_refresh_token = partial(_update, logger, RefreshTokenModel, RefreshToken)
_get_refresh_token_by_id = partial(
    _get_data_by_id, logger, RefreshTokenModel, RefreshToken
)
_get_refresh_tokens = partial(_get_data, logger, RefreshTokenModel, RefreshToken)


class RefreshTokenRepositoryImpl(RefreshTokenRepository):
    def insert_refresh_token(
        self, session: Session, model: RefreshToken
    ) -> RefreshToken:
        return cast(RefreshToken, _insert_refresh_token(session, model))

    def update_refresh_token(
        self, session: Session, model: RefreshToken
    ) -> RefreshToken | None:
        result = _update_refresh_token(session, model)
        return cast(RefreshToken, result) if result else None

    def get_refresh_token_by_id(self, session: Session, id: str) -> RefreshToken | None:
        result = _get_refresh_token_by_id(session, id)
        return cast(RefreshToken, result) if result else None

    def get_refresh_tokens(
        self,
        session: Session,
        filter: dict[str, object] | None = None,
        order_by: Sequence | None = None,
        limit: int | None = None,
    ) -> list[RefreshToken] | None:
        result = _get_refresh_tokens(session, filter, order_by, limit)
        return cast(list[RefreshToken], result) if result else None
