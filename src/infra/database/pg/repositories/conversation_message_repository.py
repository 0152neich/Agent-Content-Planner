"""Abstract interface for ConversationMessage persistence."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy.orm import Session

from ..schemas import ConversationMessage


class ConversationMessageRepository(ABC):
    @abstractmethod
    def insert_conversation_message(
        self, session: Session, model: ConversationMessage
    ) -> ConversationMessage:
        raise NotImplementedError

    @abstractmethod
    def update_conversation_message(
        self, session: Session, model: ConversationMessage
    ) -> ConversationMessage | None:
        raise NotImplementedError

    @abstractmethod
    def delete_conversation_message(
        self, session: Session, id: str
    ) -> ConversationMessage | None:
        raise NotImplementedError

    @abstractmethod
    def get_conversation_message_by_id(
        self, session: Session, id: str
    ) -> ConversationMessage | None:
        raise NotImplementedError

    @abstractmethod
    def get_conversation_messages(
        self,
        session: Session,
        filter: dict[str, object] | None = None,
        order_by: Sequence | None = None,
        limit: int | None = None,
    ) -> list[ConversationMessage] | None:
        raise NotImplementedError

    @abstractmethod
    def list_conversation_messages_by_cursor(
        self,
        session: Session,
        *,
        conversation_id: str,
        cursor_created_at: datetime | None,
        cursor_id: str | None,
        limit: int,
    ) -> list[ConversationMessage]:
        raise NotImplementedError
