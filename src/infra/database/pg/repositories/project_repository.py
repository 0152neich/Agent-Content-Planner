"""Abstract interface for Project persistence."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from sqlalchemy.orm import Session

from ..schemas import Project


class ProjectRepository(ABC):
    @abstractmethod
    def insert_project(self, session: Session, model: Project) -> Project:
        raise NotImplementedError

    @abstractmethod
    def update_project(self, session: Session, model: Project) -> Project | None:
        raise NotImplementedError

    @abstractmethod
    def delete_project(self, session: Session, id: str) -> Project | None:
        raise NotImplementedError

    @abstractmethod
    def get_project_by_id(self, session: Session, id: str) -> Project | None:
        raise NotImplementedError

    @abstractmethod
    def get_projects(
        self,
        session: Session,
        filter: dict[str, object] | None = None,
        order_by: Sequence | None = None,
        limit: int | None = None,
    ) -> list[Project] | None:
        raise NotImplementedError
