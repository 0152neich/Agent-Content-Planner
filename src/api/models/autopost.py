from __future__ import annotations

from datetime import datetime, timezone

from pydantic import Field, field_validator, model_validator

from infra.database.pg.schemas import AutopostJob
from shared.base import BaseModel


ALLOWED_AUTPOST_STATUSES = {
    "QUEUED",
    "GENERATING",
    "READY",
    "SCHEDULED",
    "PUBLISHED",
    "FAILED",
    "NEEDS_RECONNECT",
    "CANCELLED",
}


class AutopostJobCreateAPIInput(BaseModel):
    project_id: str = Field(..., min_length=1, max_length=64)
    platform: str = Field(..., min_length=1, max_length=32)
    keyword: str = Field(..., min_length=1)
    scheduled_at: datetime
    publish_mode: str = Field(default="schedule", min_length=1, max_length=16)
    page_id: str | None = Field(default=None, max_length=128)

    @field_validator("platform")
    @classmethod
    def validate_platform(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"linkedin", "facebook"}:
            raise ValueError("Unsupported platform. Allowed: linkedin, facebook.")
        return normalized

    @field_validator("keyword")
    @classmethod
    def validate_keyword(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Keyword must not be blank.")
        return normalized

    @field_validator("page_id")
    @classmethod
    def validate_page_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("scheduled_at")
    @classmethod
    def validate_scheduled_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @field_validator("publish_mode")
    @classmethod
    def validate_publish_mode(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"now", "schedule"}:
            raise ValueError("Unsupported publish_mode. Allowed: now, schedule.")
        return normalized

    @model_validator(mode="after")
    def validate_platform_requirements(self) -> "AutopostJobCreateAPIInput":
        if self.platform == "facebook" and not self.page_id:
            raise ValueError("page_id is required for facebook scheduling.")
        return self


class AutopostJobAPIData(BaseModel):
    id: str
    project_id: str
    user_id: str
    platform: str
    keyword: str
    timezone: str
    scheduled_at: datetime
    status: str
    page_id: str | None = None
    draft_content: str | None = None
    final_content: str | None = None
    provider_post_id: str | None = None
    provider_schedule_id: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    retry_count: int
    conversation_run_id: str | None = None
    createdAt: datetime | None = None
    updatedAt: datetime | None = None

    @classmethod
    def from_domain(cls, job: AutopostJob) -> "AutopostJobAPIData":
        return cls(
            id=str(job.id),
            project_id=job.project_id,
            user_id=job.user_id,
            platform=job.platform,
            keyword=job.keyword,
            timezone=job.timezone,
            scheduled_at=job.scheduled_at,
            status=job.status,
            page_id=job.page_id,
            draft_content=job.draft_content,
            final_content=job.final_content,
            provider_post_id=job.provider_post_id,
            provider_schedule_id=job.provider_schedule_id,
            error_code=job.error_code,
            error_message=job.error_message,
            retry_count=job.retry_count,
            conversation_run_id=job.conversation_run_id,
            createdAt=job.createdAt,
            updatedAt=job.updatedAt,
        )


class AutopostJobCreateAPIData(BaseModel):
    id: str
    status: str


class AutopostJobListAPIData(BaseModel):
    jobs: list[AutopostJobAPIData]

    @classmethod
    def from_domain(cls, jobs: list[AutopostJob]) -> "AutopostJobListAPIData":
        return cls(jobs=[AutopostJobAPIData.from_domain(job) for job in jobs])


class AutopostJobListAPIOutput(BaseModel):
    success: bool
    data: AutopostJobListAPIData | None = None
    error: str | None = None


class AutopostJobAPIOutput(BaseModel):
    success: bool
    data: AutopostJobAPIData | None = None
    error: str | None = None


class AutopostJobCreateAPIOutput(BaseModel):
    success: bool
    data: AutopostJobCreateAPIData | None = None
    error: str | None = None


class AutopostJobActionAPIData(BaseModel):
    id: str
    status: str


class AutopostJobActionAPIOutput(BaseModel):
    success: bool
    data: AutopostJobActionAPIData | None = None
    error: str | None = None


class AutopostCalendarAPIData(BaseModel):
    jobs: list[AutopostJobAPIData]

    @classmethod
    def from_domain(cls, jobs: list[AutopostJob]) -> "AutopostCalendarAPIData":
        return cls(jobs=[AutopostJobAPIData.from_domain(job) for job in jobs])


class AutopostCalendarAPIOutput(BaseModel):
    success: bool
    data: AutopostCalendarAPIData | None = None
    error: str | None = None


class AutopostJobListFilterAPIInput(BaseModel):
    project_id: str = Field(..., min_length=1, max_length=64)
    status: str | None = Field(default=None, max_length=32)
    limit: int = Field(default=50, ge=1, le=200)

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().upper()
        if normalized not in ALLOWED_AUTPOST_STATUSES:
            raise ValueError("Unsupported status filter.")
        return normalized
