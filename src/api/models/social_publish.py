from __future__ import annotations

from datetime import datetime

from pydantic import Field, field_validator, model_validator

from shared.base import BaseModel


class SocialPublishAPIInput(BaseModel):
    platform: str = Field(..., description="Target platform: linkedin or facebook.")
    content: str = Field(..., min_length=1, description="Post text to publish.")
    page_id: str | None = Field(
        default=None,
        description="Facebook page id. Required when platform=facebook.",
    )

    @field_validator("platform")
    @classmethod
    def validate_platform(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"linkedin", "facebook"}:
            raise ValueError("Unsupported platform. Allowed: linkedin, facebook.")
        return normalized

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Content must not be blank.")
        return normalized

    @field_validator("page_id")
    @classmethod
    def validate_page_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @model_validator(mode="after")
    def validate_platform_requirements(self) -> SocialPublishAPIInput:
        if self.platform == "facebook" and not self.page_id:
            raise ValueError("page_id is required when platform=facebook.")
        return self


class SocialPublishAPIData(BaseModel):
    platform: str
    provider_post_id: str
    view_url: str


class SocialPublishAPIOutput(BaseModel):
    success: bool
    data: SocialPublishAPIData | None = None
    error: str | None = None
    code: str | None = None


class LinkedInConnectionStatusAPIData(BaseModel):
    connected: bool
    provider: str = "linkedin"
    display_name: str | None = None
    member_urn: str | None = None
    expires_at: datetime | None = None


class LinkedInConnectionStatusAPIOutput(BaseModel):
    success: bool
    data: LinkedInConnectionStatusAPIData | None = None
    error: str | None = None
    code: str | None = None


class LinkedInConnectStartAPIData(BaseModel):
    authorize_url: str


class LinkedInConnectStartAPIOutput(BaseModel):
    success: bool
    data: LinkedInConnectStartAPIData | None = None
    error: str | None = None
    code: str | None = None


class LinkedInDisconnectAPIData(BaseModel):
    disconnected: bool


class LinkedInDisconnectAPIOutput(BaseModel):
    success: bool
    data: LinkedInDisconnectAPIData | None = None
    error: str | None = None
    code: str | None = None


class FacebookConnectionStatusAPIData(BaseModel):
    connected: bool
    provider: str = "facebook"
    display_name: str | None = None
    account_id: str | None = None
    expires_at: datetime | None = None


class FacebookConnectionStatusAPIOutput(BaseModel):
    success: bool
    data: FacebookConnectionStatusAPIData | None = None
    error: str | None = None
    code: str | None = None


class FacebookConnectStartAPIData(BaseModel):
    authorize_url: str


class FacebookConnectStartAPIOutput(BaseModel):
    success: bool
    data: FacebookConnectStartAPIData | None = None
    error: str | None = None
    code: str | None = None


class FacebookDisconnectAPIData(BaseModel):
    disconnected: bool


class FacebookDisconnectAPIOutput(BaseModel):
    success: bool
    data: FacebookDisconnectAPIData | None = None
    error: str | None = None
    code: str | None = None


class FacebookPageAPIData(BaseModel):
    id: str
    name: str
    tasks: list[str] = Field(default_factory=list)
    perms: list[str] = Field(default_factory=list)


class FacebookPagesListAPIOutput(BaseModel):
    success: bool
    data: list[FacebookPageAPIData] | None = None
    error: str | None = None
    code: str | None = None
