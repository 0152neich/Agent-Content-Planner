"""Abstract interface for Conversation persistence."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from sqlalchemy.orm import Session

from ..schemas import Conversation


class ConversationRepository(ABC):
    @abstractmethod
    def insert_conversation(
        self, session: Session, model: Conversation
    ) -> Conversation:
        raise NotImplementedError

    @abstractmethod
    def update_conversation(
        self, session: Session, model: Conversation
    ) -> Conversation | None:
        raise NotImplementedError

    @abstractmethod
    def delete_conversation(self, session: Session, id: str) -> Conversation | None:
        raise NotImplementedError

    @abstractmethod
    def get_conversation_by_id(self, session: Session, id: str) -> Conversation | None:
        raise NotImplementedError

    @abstractmethod
    def get_conversations(
        self,
        session: Session,
        filter: dict[str, object] | None = None,
        order_by: Sequence | None = None,
        limit: int | None = None,
    ) -> list[Conversation] | None:
        raise NotImplementedError
