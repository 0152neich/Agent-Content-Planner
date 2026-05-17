"""Abstract interface for AutopostJob persistence."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy.orm import Session

from ..schemas import AutopostJob


class AutopostJobRepository(ABC):
    @abstractmethod
    def insert_autopost_job(self, session: Session, model: AutopostJob) -> AutopostJob:
        raise NotImplementedError

    @abstractmethod
    def update_autopost_job(
        self, session: Session, model: AutopostJob
    ) -> AutopostJob | None:
        raise NotImplementedError

    @abstractmethod
    def update_autopost_job_with_guard(
        self,
        session: Session,
        *,
        job_id: str,
        expected_job_version: int | None,
        expected_statuses: list[str] | None,
        updates: dict[str, object],
    ) -> AutopostJob | None:
        raise NotImplementedError

    @abstractmethod
    def delete_autopost_job(self, session: Session, id: str) -> AutopostJob | None:
        raise NotImplementedError

    @abstractmethod
    def get_autopost_job_by_id(self, session: Session, id: str) -> AutopostJob | None:
        raise NotImplementedError

    @abstractmethod
    def get_autopost_jobs(
        self,
        session: Session,
        filter: dict[str, object] | None = None,
        order_by: Sequence | None = None,
        limit: int | None = None,
    ) -> list[AutopostJob] | None:
        raise NotImplementedError

    @abstractmethod
    def list_autopost_jobs(
        self,
        session: Session,
        *,
        project_id: str,
        user_id: str,
        status: str | None,
        limit: int,
    ) -> list[AutopostJob]:
        raise NotImplementedError

    @abstractmethod
    def list_due_linkedin_jobs(
        self,
        session: Session,
        *,
        now_utc: datetime,
        limit: int,
    ) -> list[AutopostJob]:
        raise NotImplementedError
