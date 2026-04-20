from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field


class Identified(BaseModel):
    id: str | None = None  # Optional on insert; backend sets UUID if missing


class Dated(BaseModel):
    createdAt: datetime | None = None
    updatedAt: datetime | None = None
    deletedAt: datetime | None = None


class DatabaseSchema(Identified, Dated):
    model_config = ConfigDict(
        from_attributes=True,
        arbitrary_types_allowed=True,
    )


class User(DatabaseSchema):
    """User schema: identity, profile, status. Omit password_hash when returning to client."""

    # Identity & login
    user_name: str = Field(..., min_length=1, max_length=64)
    email: str = Field(..., min_length=1, max_length=255)
    password_hash: str | None = None

    # Profile
    full_name: str | None = None
    phone: str | None = Field(None, max_length=32)
    avatar_url: str | None = Field(None, max_length=512)

    # Status & role
    is_active: bool = True
    email_verified: bool = False
    role: str = Field(default="user", max_length=32)


class UserIdentity(DatabaseSchema):
    user_id: str = Field(..., min_length=1, max_length=64)
    provider: str = Field(..., min_length=1, max_length=32)
    provider_sub: str = Field(..., min_length=1, max_length=255)
    email: str | None = Field(None, min_length=1, max_length=255)
    email_verified: bool = False
    picture_url: str | None = Field(None, max_length=512)


class RefreshToken(DatabaseSchema):
    user_id: str = Field(..., min_length=1, max_length=64)
    token_hash: str = Field(..., min_length=1, max_length=128)
    expires_at: datetime
    revoked_at: datetime | None = None
    replaced_by_jti: str | None = Field(None, max_length=64)
    ip: str | None = Field(None, max_length=64)
    user_agent: str | None = Field(None, max_length=512)


class PasswordResetOTP(DatabaseSchema):
    user_id: str = Field(..., min_length=1, max_length=64)
    email: str = Field(..., min_length=1, max_length=255)
    otp_hash: str = Field(..., min_length=1, max_length=128)
    expires_at: datetime
    consumed_at: datetime | None = None
    reset_at: datetime | None = None
    attempt_count: int = Field(default=0, ge=0)
    ip: str | None = Field(None, max_length=64)
    user_agent: str | None = Field(None, max_length=512)


class SocialConnection(DatabaseSchema):
    user_id: str = Field(..., min_length=1, max_length=64)
    provider: str = Field(..., min_length=1, max_length=32)
    access_token_encrypted: str = Field(..., min_length=1)
    refresh_token_encrypted: str | None = None
    token_expires_at: datetime | None = None
    provider_account_id: str | None = Field(None, max_length=255)
    provider_account_name: str | None = Field(None, max_length=255)
    revoked_at: datetime | None = None


class Project(DatabaseSchema):
    owner_user_id: str = Field(..., min_length=1, max_length=64)
    name: str = Field(..., min_length=1, max_length=128)
    source_url: str | None = Field(None, max_length=1024)
    description: str | None = None
    status: str = Field(default="active", max_length=32)
    last_active_at: datetime | None = None


class Conversation(DatabaseSchema):
    project_id: str = Field(..., min_length=1, max_length=64)
    title: str = Field(..., min_length=1, max_length=255)
    selected_model: str | None = Field(None, max_length=64)
    status: str = Field(default="active", max_length=32)
    message_count: int = Field(default=0, ge=0)
    last_message_at: datetime | None = None


class ConversationMessage(DatabaseSchema):
    conversation_id: str = Field(..., min_length=1, max_length=64)
    role: str = Field(..., min_length=1, max_length=16)
    content: str = Field(..., min_length=1)
    model: str | None = Field(None, max_length=64)
    input_tokens: int | None = Field(None, ge=0)
    output_tokens: int | None = Field(None, ge=0)
    latency_ms: int | None = Field(None, ge=0)
    error: str | None = None


class ConversationRun(DatabaseSchema):
    conversation_id: str = Field(..., min_length=1, max_length=64)
    project_id: str = Field(..., min_length=1, max_length=64)
    request_payload: dict = Field(default_factory=dict)
    response_payload: dict = Field(default_factory=dict)
    status: str = Field(default="completed", max_length=32)
    started_at: datetime
    finished_at: datetime | None = None
    source_url: str | None = Field(None, max_length=1024)
    platforms: list[str] = Field(default_factory=list)
