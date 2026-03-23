from __future__ import annotations

from typing import Any

from infra.database.pg import SQLDatabase
from infra.database.pg.schemas import User
from passlib.context import CryptContext
from shared.base import BaseModel
from shared.logging import get_logger, redact_message
from shared.settings.models import PostgresSettings

logger = get_logger(__name__)
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


class UserServiceOutput(BaseModel):
    status: bool
    data: Any | None = None
    error: str | None = None
    code: int = 200


class GetUserByIdInput(BaseModel):
    user_id: str


class CreateUserInput(BaseModel):
    user_name: str
    email: str
    password: str
    full_name: str | None = None
    phone: str | None = None
    avatar_url: str | None = None
    is_active: bool = True
    email_verified: bool = False
    role: str = "user"


class UpdateUserInput(BaseModel):
    user_id: str
    user_name: str | None = None
    email: str | None = None
    password: str | None = None
    full_name: str | None = None
    phone: str | None = None
    avatar_url: str | None = None
    is_active: bool | None = None
    email_verified: bool | None = None
    role: str | None = None


class DeleteUserInput(BaseModel):
    user_id: str


class UserService(BaseModel):
    def __init__(self, **data: Any) -> None:
        super().__init__(**data)
        self._db = SQLDatabase(config=PostgresSettings())

    def get_users(self, limit: int | None = None) -> UserServiceOutput:
        try:
            with self._db.get_session() as session:
                users = self._db.get_users(session=session, limit=limit) or []
            return UserServiceOutput(status=True, data=users, error=None, code=200)
        except Exception as exc:
            logger.exception("Failed to fetch users", error=str(exc))
            return UserServiceOutput(
                status=False,
                data=None,
                error="Unexpected error while fetching users.",
                code=500,
            )

    def get_user_by_id(self, inputs: GetUserByIdInput) -> UserServiceOutput:
        try:
            with self._db.get_session() as session:
                user = self._db.get_user_by_id(session=session, id=inputs.user_id)
            if user is None:
                return UserServiceOutput(
                    status=False,
                    data=None,
                    error=f"User with id '{inputs.user_id}' not found.",
                    code=404,
                )
            return UserServiceOutput(status=True, data=user, error=None, code=200)
        except Exception as exc:
            logger.exception(
                "Failed to fetch user by id", error=str(exc), user_id=inputs.user_id
            )
            return UserServiceOutput(
                status=False,
                data=None,
                error="Unexpected error while fetching user.",
                code=500,
            )

    def create_user(self, inputs: CreateUserInput) -> UserServiceOutput:
        try:
            with self._db.get_session() as session:
                existed_by_email = self._db.get_users(
                    session=session,
                    filter={"email": inputs.email},
                    limit=1,
                )
                if existed_by_email:
                    return UserServiceOutput(
                        status=False,
                        data=None,
                        error=f"Email '{inputs.email}' already exists.",
                        code=409,
                    )

                existed_by_user_name = self._db.get_users(
                    session=session,
                    filter={"user_name": inputs.user_name},
                    limit=1,
                )
                if existed_by_user_name:
                    return UserServiceOutput(
                        status=False,
                        data=None,
                        error=f"Username '{inputs.user_name}' already exists.",
                        code=409,
                    )

                model = User(
                    user_name=inputs.user_name,
                    email=inputs.email,
                    password_hash=pwd_context.hash(inputs.password),
                    full_name=inputs.full_name,
                    phone=inputs.phone,
                    avatar_url=inputs.avatar_url,
                    is_active=inputs.is_active,
                    email_verified=inputs.email_verified,
                    role=inputs.role,
                )
                created_user = self._db.insert_user(session=session, model=model)
            return UserServiceOutput(
                status=True, data=created_user, error=None, code=201
            )
        except Exception as exc:
            logger.exception("Failed to create user", error=str(exc))
            return UserServiceOutput(
                status=False,
                data=None,
                error=f"Unexpected error while creating user: {redact_message(str(exc))}",
                code=500,
            )

    def update_user(self, inputs: UpdateUserInput) -> UserServiceOutput:
        try:
            with self._db.get_session() as session:
                existing = self._db.get_user_by_id(session=session, id=inputs.user_id)
                if existing is None:
                    return UserServiceOutput(
                        status=False,
                        data=None,
                        error=f"User with id '{inputs.user_id}' not found.",
                        code=404,
                    )

                next_user_name = (
                    inputs.user_name
                    if inputs.user_name is not None
                    else existing.user_name
                )
                next_email = (
                    inputs.email if inputs.email is not None else existing.email
                )

                if next_email != existing.email:
                    existed_by_email = self._db.get_users(
                        session=session,
                        filter={"email": next_email},
                        limit=1,
                    )
                    if existed_by_email:
                        return UserServiceOutput(
                            status=False,
                            data=None,
                            error=f"Email '{next_email}' already exists.",
                            code=409,
                        )

                if next_user_name != existing.user_name:
                    existed_by_user_name = self._db.get_users(
                        session=session,
                        filter={"user_name": next_user_name},
                        limit=1,
                    )
                    if existed_by_user_name:
                        return UserServiceOutput(
                            status=False,
                            data=None,
                            error=f"Username '{next_user_name}' already exists.",
                            code=409,
                        )

                updated_model = User(
                    id=existing.id,
                    user_name=next_user_name,
                    email=next_email,
                    password_hash=(
                        pwd_context.hash(inputs.password)
                        if inputs.password is not None
                        else existing.password_hash
                    ),
                    full_name=inputs.full_name
                    if inputs.full_name is not None
                    else existing.full_name,
                    phone=inputs.phone if inputs.phone is not None else existing.phone,
                    avatar_url=inputs.avatar_url
                    if inputs.avatar_url is not None
                    else existing.avatar_url,
                    is_active=inputs.is_active
                    if inputs.is_active is not None
                    else existing.is_active,
                    email_verified=(
                        inputs.email_verified
                        if inputs.email_verified is not None
                        else existing.email_verified
                    ),
                    role=inputs.role if inputs.role is not None else existing.role,
                )
                updated_user = self._db.update_user(
                    session=session, model=updated_model
                )

            if updated_user is None:
                return UserServiceOutput(
                    status=False,
                    data=None,
                    error=f"User with id '{inputs.user_id}' not found.",
                    code=404,
                )

            return UserServiceOutput(
                status=True, data=updated_user, error=None, code=200
            )
        except Exception as exc:
            logger.exception(
                "Failed to update user", error=str(exc), user_id=inputs.user_id
            )
            return UserServiceOutput(
                status=False,
                data=None,
                error=f"Unexpected error while updating user: {redact_message(str(exc))}",
                code=500,
            )

    def delete_user(self, inputs: DeleteUserInput) -> UserServiceOutput:
        try:
            with self._db.get_session() as session:
                existing = self._db.get_user_by_id(session=session, id=inputs.user_id)
                if existing is None:
                    return UserServiceOutput(
                        status=False,
                        data=None,
                        error=f"User with id '{inputs.user_id}' not found.",
                        code=404,
                    )

                deleted_user = self._db.delete_user(session=session, id=inputs.user_id)
                if deleted_user is None:
                    return UserServiceOutput(
                        status=False,
                        data=None,
                        error=f"User with id '{inputs.user_id}' not found.",
                        code=404,
                    )
                return UserServiceOutput(
                    status=True, data=deleted_user, error=None, code=200
                )
        except Exception as exc:
            logger.exception(
                "Failed to delete user", error=str(exc), user_id=inputs.user_id
            )
            return UserServiceOutput(
                status=False,
                data=None,
                error=f"Unexpected error while deleting user: {redact_message(str(exc))}",
                code=500,
            )
