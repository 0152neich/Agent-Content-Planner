"""Autopost job repository implementation."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from functools import partial
from typing import cast

from shared.logging import get_logger
from sqlalchemy import asc, desc, select, update
from sqlalchemy.orm import Session

from .models import AutopostJob as AutopostJobModel
from .repositories import AutopostJobRepository
from .schemas import AutopostJob
from .utils import _delete, _get_data, _get_data_by_id, _insert, _update

logger = get_logger(__name__)

_insert_autopost_job = partial(_insert, logger, AutopostJobModel, AutopostJob)
_update_autopost_job = partial(_update, logger, AutopostJobModel, AutopostJob)
_delete_autopost_job = partial(_delete, logger, AutopostJobModel, AutopostJob)
_get_autopost_jobs = partial(_get_data, logger, AutopostJobModel, AutopostJob)
_get_autopost_job_by_id = partial(
    _get_data_by_id, logger, AutopostJobModel, AutopostJob
)


class AutopostJobRepositoryImpl(AutopostJobRepository):
    def insert_autopost_job(self, session: Session, model: AutopostJob) -> AutopostJob:
        return cast(AutopostJob, _insert_autopost_job(session, model))

    def update_autopost_job(
        self, session: Session, model: AutopostJob
    ) -> AutopostJob | None:
        result = _update_autopost_job(session, model)
        return cast(AutopostJob, result) if result else None

    def update_autopost_job_with_guard(
        self,
        session: Session,
        *,
        job_id: str,
        expected_job_version: int | None,
        expected_statuses: list[str] | None,
        updates: dict[str, object],
    ) -> AutopostJob | None:
        guarded_updates = dict(updates)
        statement = update(AutopostJobModel).where(
            AutopostJobModel.id == job_id,
            AutopostJobModel.deletedAt.is_(None),
        )
        if expected_job_version is not None:
            statement = statement.where(
                AutopostJobModel.job_version == expected_job_version
            )
            guarded_updates["job_version"] = expected_job_version + 1
        if expected_statuses:
            statement = statement.where(AutopostJobModel.status.in_(expected_statuses))

        result = session.execute(
            statement.values(**guarded_updates),
            execution_options={"synchronize_session": False},
        )
        if result.rowcount != 1:
            session.rollback()
            return None
        session.commit()
        obj = session.get(AutopostJobModel, job_id)
        if obj is None:
            return None
        return AutopostJob.model_validate(obj)

    def delete_autopost_job(self, session: Session, id: str) -> AutopostJob | None:
        result = _delete_autopost_job(session, id)
        return cast(AutopostJob, result) if result else None

    def get_autopost_job_by_id(self, session: Session, id: str) -> AutopostJob | None:
        result = _get_autopost_job_by_id(session, id)
        return cast(AutopostJob, result) if result else None

    def get_autopost_jobs(
        self,
        session: Session,
        filter: dict[str, object] | None = None,
        order_by: Sequence | None = None,
        limit: int | None = None,
    ) -> list[AutopostJob] | None:
        result = _get_autopost_jobs(session, filter, order_by, limit)
        return cast(list[AutopostJob], result) if result else None

    def list_autopost_jobs(
        self,
        session: Session,
        *,
        project_id: str,
        user_id: str,
        status: str | None,
        limit: int,
    ) -> list[AutopostJob]:
        statement = (
            select(AutopostJobModel)
            .where(
                AutopostJobModel.project_id == project_id,
                AutopostJobModel.user_id == user_id,
                AutopostJobModel.deletedAt.is_(None),
            )
            .order_by(
                desc(AutopostJobModel.scheduled_at),
                desc(AutopostJobModel.createdAt),
            )
            .limit(limit)
        )
        if status:
            statement = statement.where(AutopostJobModel.status == status)
        rows = session.scalars(statement).all()
        return [AutopostJob.model_validate(row) for row in rows]

    def list_due_linkedin_jobs(
        self,
        session: Session,
        *,
        now_utc: datetime,
        limit: int,
    ) -> list[AutopostJob]:
        statement = (
            select(AutopostJobModel)
            .where(
                AutopostJobModel.platform == "linkedin",
                AutopostJobModel.status == "SCHEDULED",
                AutopostJobModel.scheduled_at <= now_utc,
                AutopostJobModel.deletedAt.is_(None),
            )
            .order_by(asc(AutopostJobModel.scheduled_at))
            .limit(limit)
        )
        rows = session.scalars(statement).all()
        return [AutopostJob.model_validate(row) for row in rows]
