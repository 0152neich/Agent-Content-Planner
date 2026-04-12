"""Conversation run repository implementation."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from functools import partial
from typing import cast

from shared.logging import get_logger
from sqlalchemy import and_, desc, or_, select
from sqlalchemy.orm import Session

from .models import ConversationRun as ConversationRunModel
from .repositories import ConversationRunRepository
from .schemas import ConversationRun
from .utils import _delete, _get_data, _get_data_by_id, _insert, _update

logger = get_logger(__name__)

_insert_conversation_run = partial(
    _insert, logger, ConversationRunModel, ConversationRun
)
_update_conversation_run = partial(
    _update, logger, ConversationRunModel, ConversationRun
)
_delete_conversation_run = partial(
    _delete, logger, ConversationRunModel, ConversationRun
)
_get_conversation_runs = partial(
    _get_data, logger, ConversationRunModel, ConversationRun
)
_get_conversation_run_by_id = partial(
    _get_data_by_id, logger, ConversationRunModel, ConversationRun
)


class ConversationRunRepositoryImpl(ConversationRunRepository):
    def insert_conversation_run(
        self, session: Session, model: ConversationRun
    ) -> ConversationRun:
        return cast(ConversationRun, _insert_conversation_run(session, model))

    def update_conversation_run(
        self, session: Session, model: ConversationRun
    ) -> ConversationRun | None:
        result = _update_conversation_run(session, model)
        return cast(ConversationRun, result) if result else None

    def delete_conversation_run(
        self, session: Session, id: str
    ) -> ConversationRun | None:
        result = _delete_conversation_run(session, id)
        return cast(ConversationRun, result) if result else None

    def get_conversation_run_by_id(
        self, session: Session, id: str
    ) -> ConversationRun | None:
        result = _get_conversation_run_by_id(session, id)
        return cast(ConversationRun, result) if result else None

    def get_conversation_runs(
        self,
        session: Session,
        filter: dict[str, object] | None = None,
        order_by: Sequence | None = None,
        limit: int | None = None,
    ) -> list[ConversationRun] | None:
        result = _get_conversation_runs(session, filter, order_by, limit)
        return cast(list[ConversationRun], result) if result else None

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
        statement = (
            select(ConversationRunModel)
            .where(
                ConversationRunModel.project_id == project_id,
                ConversationRunModel.deletedAt.is_(None),
            )
            .order_by(
                desc(ConversationRunModel.createdAt), desc(ConversationRunModel.id)
            )
            .limit(limit)
        )
        if status:
            statement = statement.where(ConversationRunModel.status == status)
        if cursor_created_at and cursor_id:
            statement = statement.where(
                or_(
                    ConversationRunModel.createdAt < cursor_created_at,
                    and_(
                        ConversationRunModel.createdAt == cursor_created_at,
                        ConversationRunModel.id < cursor_id,
                    ),
                )
            )

        rows = session.scalars(statement).all()
        return [ConversationRun.model_validate(row) for row in rows]
