"""Conversation message repository implementation."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from functools import partial
from typing import cast

from shared.logging import get_logger
from sqlalchemy import and_, desc, or_, select
from sqlalchemy.orm import Session

from .models import ConversationMessage as ConversationMessageModel
from .repositories import ConversationMessageRepository
from .schemas import ConversationMessage
from .utils import _delete, _get_data, _get_data_by_id, _insert, _update

logger = get_logger(__name__)

_insert_conversation_message = partial(
    _insert, logger, ConversationMessageModel, ConversationMessage
)
_update_conversation_message = partial(
    _update, logger, ConversationMessageModel, ConversationMessage
)
_delete_conversation_message = partial(
    _delete, logger, ConversationMessageModel, ConversationMessage
)
_get_conversation_messages = partial(
    _get_data, logger, ConversationMessageModel, ConversationMessage
)
_get_conversation_message_by_id = partial(
    _get_data_by_id, logger, ConversationMessageModel, ConversationMessage
)


class ConversationMessageRepositoryImpl(ConversationMessageRepository):
    def insert_conversation_message(
        self, session: Session, model: ConversationMessage
    ) -> ConversationMessage:
        return cast(ConversationMessage, _insert_conversation_message(session, model))

    def update_conversation_message(
        self, session: Session, model: ConversationMessage
    ) -> ConversationMessage | None:
        result = _update_conversation_message(session, model)
        return cast(ConversationMessage, result) if result else None

    def delete_conversation_message(
        self, session: Session, id: str
    ) -> ConversationMessage | None:
        result = _delete_conversation_message(session, id)
        return cast(ConversationMessage, result) if result else None

    def get_conversation_message_by_id(
        self, session: Session, id: str
    ) -> ConversationMessage | None:
        result = _get_conversation_message_by_id(session, id)
        return cast(ConversationMessage, result) if result else None

    def get_conversation_messages(
        self,
        session: Session,
        filter: dict[str, object] | None = None,
        order_by: Sequence | None = None,
        limit: int | None = None,
    ) -> list[ConversationMessage] | None:
        result = _get_conversation_messages(session, filter, order_by, limit)
        return cast(list[ConversationMessage], result) if result else None

    def list_conversation_messages_by_cursor(
        self,
        session: Session,
        *,
        conversation_id: str,
        cursor_created_at: datetime | None,
        cursor_id: str | None,
        limit: int,
    ) -> list[ConversationMessage]:
        statement = (
            select(ConversationMessageModel)
            .where(
                ConversationMessageModel.conversation_id == conversation_id,
                ConversationMessageModel.deletedAt.is_(None),
            )
            .order_by(
                desc(ConversationMessageModel.createdAt),
                desc(ConversationMessageModel.id),
            )
            .limit(limit)
        )
        if cursor_created_at and cursor_id:
            statement = statement.where(
                or_(
                    ConversationMessageModel.createdAt < cursor_created_at,
                    and_(
                        ConversationMessageModel.createdAt == cursor_created_at,
                        ConversationMessageModel.id < cursor_id,
                    ),
                )
            )

        rows = session.scalars(statement).all()
        return [ConversationMessage.model_validate(row) for row in rows]
