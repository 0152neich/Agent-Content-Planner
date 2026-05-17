from __future__ import annotations

from pydantic import Field

from api.models.user import UserAPIData
from infra.database.pg.schemas import User
from shared.base import BaseModel


class LoginAPIInput(BaseModel):
    identifier: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=1, max_length=255)


class AuthTokenAPIData(BaseModel):
    access_token: str
    token_type: str
    expires_in: int
    user: UserAPIData

    @classmethod
    def from_service_payload(cls, payload: dict) -> "AuthTokenAPIData":
        user = payload.get("user")
        if not isinstance(user, User):
            raise ValueError("Invalid auth payload: user must be a User schema.")
        return cls(
            access_token=str(payload["access_token"]),
            token_type=str(payload["token_type"]),
            expires_in=int(payload["expires_in"]),
            user=UserAPIData.from_domain(user),
        )


class LoginAPIOutput(BaseModel):
    success: bool
    data: AuthTokenAPIData | None = None
    error: str | None = None


class RefreshAPIOutput(BaseModel):
    success: bool
    data: AuthTokenAPIData | None = None
    error: str | None = None


class LogoutAPIData(BaseModel):
    logged_out: bool


class LogoutAPIOutput(BaseModel):
    success: bool
    data: LogoutAPIData | None = None
    error: str | None = None


class MeAPIOutput(BaseModel):
    success: bool
    data: UserAPIData | None = None
    error: str | None = None


class ForgotPasswordSendOtpAPIInput(BaseModel):
    email: str = Field(..., min_length=1, max_length=255)


class ForgotPasswordSendOtpAPIData(BaseModel):
    sent: bool
    expires_in: int
    message: str


class ForgotPasswordSendOtpAPIOutput(BaseModel):
    success: bool
    data: ForgotPasswordSendOtpAPIData | None = None
    error: str | None = None


class ForgotPasswordVerifyOtpAPIInput(BaseModel):
    email: str = Field(..., min_length=1, max_length=255)
    otp: str = Field(..., min_length=4, max_length=8)


class ForgotPasswordVerifyOtpAPIData(BaseModel):
    verified: bool
    reset_token: str
    expires_in: int


class ForgotPasswordVerifyOtpAPIOutput(BaseModel):
    success: bool
    data: ForgotPasswordVerifyOtpAPIData | None = None
    error: str | None = None


class ForgotPasswordResetAPIInput(BaseModel):
    reset_token: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8, max_length=255)


class ForgotPasswordResetAPIData(BaseModel):
    reset: bool


class ForgotPasswordResetAPIOutput(BaseModel):
    success: bool
    data: ForgotPasswordResetAPIData | None = None
    error: str | None = None
