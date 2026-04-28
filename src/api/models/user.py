from __future__ import annotations

from datetime import datetime

from pydantic import Field, model_validator

from infra.database.pg.schemas import User
from shared.base import BaseModel


class UserAPIData(BaseModel):
    id: str
    user_name: str
    email: str
    full_name: str | None = None
    phone: str | None = None
    avatar_url: str | None = None
    timezone: str | None = None
    is_active: bool
    email_verified: bool
    role: str
    createdAt: datetime | None = None
    updatedAt: datetime | None = None

    @classmethod
    def from_domain(cls, user: User) -> "UserAPIData":
        return cls(
            id=str(user.id),
            user_name=user.user_name,
            email=user.email,
            full_name=user.full_name,
            phone=user.phone,
            avatar_url=user.avatar_url,
            timezone=user.timezone,
            is_active=user.is_active,
            email_verified=user.email_verified,
            role=user.role,
            createdAt=user.createdAt,
            updatedAt=user.updatedAt,
        )


class UserCreateAPIInput(BaseModel):
    user_name: str = Field(..., min_length=1, max_length=64)
    email: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=8, max_length=255)
    full_name: str | None = Field(None, max_length=128)
    phone: str | None = Field(None, max_length=32)
    avatar_url: str | None = Field(None, max_length=512)
    timezone: str | None = Field(None, max_length=64)
    is_active: bool = True
    email_verified: bool = False
    role: str = Field(default="user", max_length=32)


class UserUpdateAPIInput(BaseModel):
    user_name: str | None = Field(None, min_length=1, max_length=64)
    email: str | None = Field(None, min_length=1, max_length=255)
    password: str | None = Field(None, min_length=8, max_length=255)
    full_name: str | None = Field(None, max_length=128)
    phone: str | None = Field(None, max_length=32)
    avatar_url: str | None = Field(None, max_length=512)
    timezone: str | None = Field(None, max_length=64)
    is_active: bool | None = None
    email_verified: bool | None = None
    role: str | None = Field(None, max_length=32)

    @model_validator(mode="after")
    def validate_at_least_one_field(self) -> "UserUpdateAPIInput":
        has_payload = any(
            value is not None
            for value in [
                self.user_name,
                self.email,
                self.password,
                self.full_name,
                self.phone,
                self.avatar_url,
                self.timezone,
                self.is_active,
                self.email_verified,
                self.role,
            ]
        )
        if not has_payload:
            raise ValueError("At least one field must be provided for update.")
        return self


class UserListAPIData(BaseModel):
    users: list[UserAPIData]

    @classmethod
    def from_domain(cls, users: list[User]) -> "UserListAPIData":
        return cls(users=[UserAPIData.from_domain(user) for user in users])


class UserDeleteAPIData(BaseModel):
    id: str
    deleted: bool


class UserAPIOutput(BaseModel):
    success: bool
    data: UserAPIData | None = None
    error: str | None = None


class UserListAPIOutput(BaseModel):
    success: bool
    data: UserListAPIData | None = None
    error: str | None = None


class UserDeleteAPIOutput(BaseModel):
    success: bool
    data: UserDeleteAPIData | None = None
    error: str | None = None
