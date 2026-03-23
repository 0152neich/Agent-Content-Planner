from __future__ import annotations

from pydantic import Field

from shared.base import BaseModel


class AuthSettings(BaseModel):
    jwt_secret_key: str = Field(
        default="change-me-in-production",
        description="JWT signing secret key. Override in production.",
    )
    jwt_algorithm: str = Field(default="HS256")
    access_token_ttl_minutes: int = Field(default=15, ge=1)
    refresh_token_ttl_days: int = Field(default=30, ge=1)
    refresh_cookie_name: str = Field(default="refresh_token")
    refresh_cookie_path: str = Field(default="/api/v1/auth")
    refresh_cookie_samesite: str = Field(default="strict")
    refresh_cookie_secure: bool = Field(default=True)
