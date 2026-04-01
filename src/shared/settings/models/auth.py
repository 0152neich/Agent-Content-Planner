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

    google_enabled: bool = Field(default=False)
    google_client_id: str = Field(default="")
    google_client_secret: str = Field(default="")
    google_redirect_uri: str = Field(
        default="http://localhost:8000/api/v1/auth/google/callback"
    )
    google_fe_success_redirect: str = Field(
        default="http://localhost:5173/login/google-callback"
    )
    google_fe_error_redirect: str = Field(default="http://localhost:5173/login")
    google_state_ttl_seconds: int = Field(default=300, ge=60)
    google_state_cookie_name: str = Field(default="google_oauth_state")
    google_state_cookie_path: str = Field(default="/api/v1/auth/google")
    google_state_cookie_samesite: str = Field(default="lax")
    google_state_cookie_secure: bool = Field(default=True)

    forgot_password_enabled: bool = Field(default=True)
    forgot_password_otp_length: int = Field(default=6, ge=4, le=8)
    forgot_password_otp_ttl_minutes: int = Field(default=10, ge=1, le=60)
    forgot_password_otp_max_attempts: int = Field(default=5, ge=1, le=20)
    forgot_password_otp_max_requests_per_hour: int = Field(default=5, ge=1, le=100)
    forgot_password_reset_token_ttl_minutes: int = Field(default=15, ge=1, le=120)

    smtp_host: str = Field(default="")
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_username: str = Field(default="")
    smtp_password: str = Field(default="")
    smtp_from_email: str = Field(default="")
    smtp_from_name: str = Field(default="AI Content Planner")
    smtp_use_tls: bool = Field(default=True)
    smtp_use_ssl: bool = Field(default=False)
    smtp_timeout_seconds: int = Field(default=20, ge=1, le=120)
    forgot_password_allow_console_otp_fallback: bool = Field(default=True)
