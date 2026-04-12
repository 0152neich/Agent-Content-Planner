"""Conversation repository implementation."""

from __future__ import annotations

from collections.abc import Sequence
from functools import partial
from typing import cast

from shared.logging import get_logger
from sqlalchemy.orm import Session

from .models import Conversation as ConversationModel
from .repositories import ConversationRepository
from .schemas import Conversation
from .utils import _delete, _get_data, _get_data_by_id, _insert, _update

logger = get_logger(__name__)

_insert_conversation = partial(_insert, logger, ConversationModel, Conversation)
_update_conversation = partial(_update, logger, ConversationModel, Conversation)
_delete_conversation = partial(_delete, logger, ConversationModel, Conversation)
_get_conversations = partial(_get_data, logger, ConversationModel, Conversation)
_get_conversation_by_id = partial(
    _get_data_by_id, logger, ConversationModel, Conversation
)


class ConversationRepositoryImpl(ConversationRepository):
    def insert_conversation(
        self, session: Session, model: Conversation
    ) -> Conversation:
        return cast(Conversation, _insert_conversation(session, model))

    def update_conversation(
        self, session: Session, model: Conversation
    ) -> Conversation | None:
        result = _update_conversation(session, model)
        return cast(Conversation, result) if result else None

    def delete_conversation(self, session: Session, id: str) -> Conversation | None:
        result = _delete_conversation(session, id)
        return cast(Conversation, result) if result else None

    def get_conversation_by_id(self, session: Session, id: str) -> Conversation | None:
        result = _get_conversation_by_id(session, id)
        return cast(Conversation, result) if result else None

    def get_conversations(
        self,
        session: Session,
        filter: dict[str, object] | None = None,
        order_by: Sequence | None = None,
        limit: int | None = None,
    ) -> list[Conversation] | None:
        result = _get_conversations(session, filter, order_by, limit)
        return cast(list[Conversation], result) if result else None
