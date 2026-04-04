from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from infra.database.pg import SQLDatabase
from infra.database.pg.schemas import Project
from sqlalchemy.exc import IntegrityError
from shared.base import BaseModel
from shared.logging import get_logger, redact_message
from shared.settings.models import PostgresSettings

logger = get_logger(__name__)


class ProjectServiceOutput(BaseModel):
    status: bool
    data: Any | None = None
    error: str | None = None
    code: int = 200


class ListProjectsInput(BaseModel):
    owner_user_id: str
    limit: int = 20


class CreateProjectInput(BaseModel):
    owner_user_id: str
    name: str
    source_url: str | None = None
    description: str | None = None
    status: str = "active"


class GetProjectInput(BaseModel):
    owner_user_id: str
    project_id: str


class UpdateProjectInput(BaseModel):
    owner_user_id: str
    project_id: str
    name: str | None = None
    source_url: str | None = None
    description: str | None = None
    status: str | None = None


class DeleteProjectInput(BaseModel):
    owner_user_id: str
    project_id: str


class ProjectService(BaseModel):
    def __init__(self, **data: Any) -> None:
        super().__init__(**data)
        self._db = SQLDatabase(config=PostgresSettings())

    @staticmethod
    def _now_utc() -> datetime:
        return datetime.now(timezone.utc)

    def list_projects(self, inputs: ListProjectsInput) -> ProjectServiceOutput:
        try:
            with self._db.get_session() as session:
                projects = (
                    self._db.get_projects(
                        session=session,
                        filter={"owner_user_id": inputs.owner_user_id},
                        limit=inputs.limit,
                    )
                    or []
                )
                projects.sort(
                    key=lambda p: p.last_active_at or p.createdAt or self._now_utc(),
                    reverse=True,
                )
                return ProjectServiceOutput(
                    status=True, data=projects, error=None, code=200
                )
        except Exception as exc:
            logger.exception(
                "Failed to list projects",
                error=str(exc),
                owner_user_id=inputs.owner_user_id,
            )
            return ProjectServiceOutput(
                status=False,
                data=None,
                error="Unexpected error while listing projects.",
                code=500,
            )

    def create_project(self, inputs: CreateProjectInput) -> ProjectServiceOutput:
        try:
            normalized_name = inputs.name.strip()
            if not normalized_name:
                return ProjectServiceOutput(
                    status=False,
                    data=None,
                    error="Project name must not be blank.",
                    code=400,
                )
            with self._db.get_session() as session:
                existed = self._db.get_projects(
                    session=session,
                    filter={
                        "owner_user_id": inputs.owner_user_id,
                        "name": normalized_name,
                    },
                    limit=1,
                )
                if existed:
                    return ProjectServiceOutput(
                        status=False,
                        data=None,
                        error=f"Project name '{normalized_name}' already exists.",
                        code=409,
                    )

                model = Project(
                    owner_user_id=inputs.owner_user_id,
                    name=normalized_name,
                    source_url=inputs.source_url,
                    description=inputs.description,
                    status=inputs.status,
                    last_active_at=self._now_utc(),
                )
                project = self._db.insert_project(session=session, model=model)
                return ProjectServiceOutput(
                    status=True, data=project, error=None, code=201
                )
        except IntegrityError as exc:
            logger.warning(
                "Project unique constraint hit while creating project.",
                error=str(exc),
                owner_user_id=inputs.owner_user_id,
            )
            return ProjectServiceOutput(
                status=False,
                data=None,
                error=f"Project name '{inputs.name.strip()}' already exists.",
                code=409,
            )
        except Exception as exc:
            logger.exception(
                "Failed to create project",
                error=str(exc),
                owner_user_id=inputs.owner_user_id,
            )
            return ProjectServiceOutput(
                status=False,
                data=None,
                error=f"Unexpected error while creating project: {redact_message(str(exc))}",
                code=500,
            )

    def get_project(self, inputs: GetProjectInput) -> ProjectServiceOutput:
        try:
            with self._db.get_session() as session:
                project = self._db.get_project_by_id(
                    session=session, id=inputs.project_id
                )
                if project is None:
                    return ProjectServiceOutput(
                        status=False,
                        data=None,
                        error=f"Project with id '{inputs.project_id}' not found.",
                        code=404,
                    )
                if project.owner_user_id != inputs.owner_user_id:
                    return ProjectServiceOutput(
                        status=False,
                        data=None,
                        error="Forbidden project access.",
                        code=403,
                    )
                return ProjectServiceOutput(
                    status=True, data=project, error=None, code=200
                )
        except Exception as exc:
            logger.exception(
                "Failed to get project", error=str(exc), project_id=inputs.project_id
            )
            return ProjectServiceOutput(
                status=False,
                data=None,
                error="Unexpected error while getting project.",
                code=500,
            )

    def update_project(self, inputs: UpdateProjectInput) -> ProjectServiceOutput:
        try:
            with self._db.get_session() as session:
                project = self._db.get_project_by_id(
                    session=session, id=inputs.project_id
                )
                if project is None:
                    return ProjectServiceOutput(
                        status=False,
                        data=None,
                        error=f"Project with id '{inputs.project_id}' not found.",
                        code=404,
                    )
                if project.owner_user_id != inputs.owner_user_id:
                    return ProjectServiceOutput(
                        status=False,
                        data=None,
                        error="Forbidden project access.",
                        code=403,
                    )

                next_name = project.name
                if inputs.name is not None:
                    next_name = inputs.name.strip()
                    if not next_name:
                        return ProjectServiceOutput(
                            status=False,
                            data=None,
                            error="Project name must not be blank.",
                            code=400,
                        )
                if next_name != project.name:
                    existed = self._db.get_projects(
                        session=session,
                        filter={
                            "owner_user_id": inputs.owner_user_id,
                            "name": next_name,
                        },
                        limit=1,
                    )
                    if existed and existed[0].id != project.id:
                        return ProjectServiceOutput(
                            status=False,
                            data=None,
                            error=f"Project name '{next_name}' already exists.",
                            code=409,
                        )

                updated_model = Project(
                    id=project.id,
                    owner_user_id=project.owner_user_id,
                    name=next_name,
                    source_url=inputs.source_url
                    if inputs.source_url is not None
                    else project.source_url,
                    description=inputs.description
                    if inputs.description is not None
                    else project.description,
                    status=inputs.status
                    if inputs.status is not None
                    else project.status,
                    last_active_at=self._now_utc(),
                )
                updated_project = self._db.update_project(
                    session=session, model=updated_model
                )
                if updated_project is None:
                    return ProjectServiceOutput(
                        status=False,
                        data=None,
                        error=f"Project with id '{inputs.project_id}' not found.",
                        code=404,
                    )
                return ProjectServiceOutput(
                    status=True, data=updated_project, error=None, code=200
                )
        except IntegrityError as exc:
            logger.warning(
                "Project unique constraint hit while updating project.",
                error=str(exc),
                owner_user_id=inputs.owner_user_id,
                project_id=inputs.project_id,
            )
            next_name = inputs.name.strip() if inputs.name else "unknown"
            return ProjectServiceOutput(
                status=False,
                data=None,
                error=f"Project name '{next_name}' already exists.",
                code=409,
            )
        except Exception as exc:
            logger.exception(
                "Failed to update project", error=str(exc), project_id=inputs.project_id
            )
            return ProjectServiceOutput(
                status=False,
                data=None,
                error=f"Unexpected error while updating project: {redact_message(str(exc))}",
                code=500,
            )

    def delete_project(self, inputs: DeleteProjectInput) -> ProjectServiceOutput:
        try:
            with self._db.get_session() as session:
                project = self._db.get_project_by_id(
                    session=session, id=inputs.project_id
                )
                if project is None:
                    return ProjectServiceOutput(
                        status=False,
                        data=None,
                        error=f"Project with id '{inputs.project_id}' not found.",
                        code=404,
                    )
                if project.owner_user_id != inputs.owner_user_id:
                    return ProjectServiceOutput(
                        status=False,
                        data=None,
                        error="Forbidden project access.",
                        code=403,
                    )
                deleted_project = self._db.delete_project(
                    session=session, id=inputs.project_id
                )
                if deleted_project is None:
                    return ProjectServiceOutput(
                        status=False,
                        data=None,
                        error=f"Project with id '{inputs.project_id}' not found.",
                        code=404,
                    )
                return ProjectServiceOutput(
                    status=True, data=deleted_project, error=None, code=200
                )
        except Exception as exc:
            logger.exception(
                "Failed to delete project", error=str(exc), project_id=inputs.project_id
            )
            return ProjectServiceOutput(
                status=False,
                data=None,
                error=f"Unexpected error while deleting project: {redact_message(str(exc))}",
                code=500,
            )
