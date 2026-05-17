from __future__ import annotations

from datetime import datetime

from pydantic import AnyHttpUrl, Field, field_validator, model_validator

from infra.database.pg.schemas import Project
from shared.base import BaseModel


class ProjectAPIData(BaseModel):
    id: str
    owner_user_id: str
    name: str
    source_url: str | None = None
    description: str | None = None
    status: str
    last_active_at: datetime | None = None
    createdAt: datetime | None = None
    updatedAt: datetime | None = None

    @classmethod
    def from_domain(cls, project: Project) -> "ProjectAPIData":
        return cls(
            id=str(project.id),
            owner_user_id=project.owner_user_id,
            name=project.name,
            source_url=project.source_url,
            description=project.description,
            status=project.status,
            last_active_at=project.last_active_at,
            createdAt=project.createdAt,
            updatedAt=project.updatedAt,
        )


class ProjectCreateAPIInput(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    source_url: AnyHttpUrl | None = None
    description: str | None = None
    status: str = Field(default="active", max_length=32)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Project name must not be blank.")
        return normalized


class ProjectUpdateAPIInput(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=128)
    source_url: AnyHttpUrl | None = None
    description: str | None = None
    status: str | None = Field(None, max_length=32)

    @field_validator("name")
    @classmethod
    def validate_optional_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("Project name must not be blank.")
        return normalized

    @model_validator(mode="after")
    def validate_at_least_one_field(self) -> "ProjectUpdateAPIInput":
        has_payload = any(
            value is not None
            for value in [self.name, self.source_url, self.description, self.status]
        )
        if not has_payload:
            raise ValueError("At least one field must be provided for update.")
        return self


class ProjectListAPIData(BaseModel):
    projects: list[ProjectAPIData]

    @classmethod
    def from_domain(cls, projects: list[Project]) -> "ProjectListAPIData":
        return cls(
            projects=[ProjectAPIData.from_domain(project) for project in projects]
        )


class ProjectAPIOutput(BaseModel):
    success: bool
    data: ProjectAPIData | None = None
    error: str | None = None


class ProjectListAPIOutput(BaseModel):
    success: bool
    data: ProjectListAPIData | None = None
    error: str | None = None


class ProjectDeleteAPIData(BaseModel):
    id: str
    deleted: bool


class ProjectDeleteAPIOutput(BaseModel):
    success: bool
    data: ProjectDeleteAPIData | None = None
    error: str | None = None
