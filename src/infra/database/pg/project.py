"""Project repository implementation."""

from __future__ import annotations

from collections.abc import Sequence
from functools import partial
from typing import cast

from shared.logging import get_logger
from sqlalchemy.orm import Session

from .models import Project as ProjectModel
from .repositories import ProjectRepository
from .schemas import Project
from .utils import _delete, _get_data, _get_data_by_id, _insert, _update

logger = get_logger(__name__)

_insert_project = partial(_insert, logger, ProjectModel, Project)
_update_project = partial(_update, logger, ProjectModel, Project)
_delete_project = partial(_delete, logger, ProjectModel, Project)
_get_projects = partial(_get_data, logger, ProjectModel, Project)
_get_project_by_id = partial(_get_data_by_id, logger, ProjectModel, Project)


class ProjectRepositoryImpl(ProjectRepository):
    def insert_project(self, session: Session, model: Project) -> Project:
        return cast(Project, _insert_project(session, model))

    def update_project(self, session: Session, model: Project) -> Project | None:
        result = _update_project(session, model)
        return cast(Project, result) if result else None

    def delete_project(self, session: Session, id: str) -> Project | None:
        result = _delete_project(session, id)
        return cast(Project, result) if result else None

    def get_project_by_id(self, session: Session, id: str) -> Project | None:
        result = _get_project_by_id(session, id)
        return cast(Project, result) if result else None

    def get_projects(
        self,
        session: Session,
        filter: dict[str, object] | None = None,
        order_by: Sequence | None = None,
        limit: int | None = None,
    ) -> list[Project] | None:
        result = _get_projects(session, filter, order_by, limit)
        return cast(list[Project], result) if result else None
