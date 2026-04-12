"""Abstract interface for ConversationRun persistence."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy.orm import Session

from ..schemas import ConversationRun


class ConversationRunRepository(ABC):
    @abstractmethod
    def insert_conversation_run(
        self, session: Session, model: ConversationRun
    ) -> ConversationRun:
        raise NotImplementedError

    @abstractmethod
    def update_conversation_run(
        self, session: Session, model: ConversationRun
    ) -> ConversationRun | None:
        raise NotImplementedError

    @abstractmethod
    def delete_conversation_run(
        self, session: Session, id: str
    ) -> ConversationRun | None:
        raise NotImplementedError

    @abstractmethod
    def get_conversation_run_by_id(
        self, session: Session, id: str
    ) -> ConversationRun | None:
        raise NotImplementedError

    @abstractmethod
    def get_conversation_runs(
        self,
        session: Session,
        filter: dict[str, object] | None = None,
        order_by: Sequence | None = None,
        limit: int | None = None,
    ) -> list[ConversationRun] | None:
        raise NotImplementedError

    @abstractmethod
    def list_project_runs_by_cursor(
        self,
        session: Session,
        *,
        project_id: str,
        status: str | None,
        cursor_created_at: datetime | None,
        cursor_id: str | None,
        limit: int,
    ) -> list[ConversationRun]:
        raise NotImplementedError
