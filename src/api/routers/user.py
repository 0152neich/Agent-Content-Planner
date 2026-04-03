from __future__ import annotations

import asyncio
import os
from functools import partial
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile, status
from fastapi.responses import JSONResponse

from api.dependencies import get_current_user
from api.helpers.exception_handler import to_user_error_message
from api.models.user import (
    UserAPIData,
    UserAPIOutput,
    UserCreateAPIInput,
    UserDeleteAPIData,
    UserDeleteAPIOutput,
    UserListAPIData,
    UserListAPIOutput,
    UserUpdateAPIInput,
)
from app.services import (
    AuthServiceOutput,
    CreateUserInput,
    DeleteUserInput,
    GetUserByIdInput,
    UpdateUserInput,
    UserService,
)
from infra.database.pg.schemas import User
from shared.logging import get_logger

logger = get_logger(__name__)

user_router = APIRouter(prefix="/users", tags=["Users"])

_service = UserService()
_default_upload_dir = (Path(__file__).resolve().parents[2] / "uploads").as_posix()
_upload_dir = Path(os.getenv("USER__UPLOAD_DIR", _default_upload_dir)).resolve()
_avatar_upload_dir = _upload_dir / "avatars"
_allowed_avatar_content_types = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
}
_allowed_avatar_extensions = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
_avatar_extension_by_content_type = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}
_avatar_max_size_bytes = int(
    os.getenv("USER__AVATAR_MAX_SIZE_BYTES", str(5 * 1024 * 1024))
)


def _json_response(
    payload: UserAPIOutput | UserListAPIOutput | UserDeleteAPIOutput,
    status_code: int,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code, content=payload.model_dump(mode="json")
    )


def _extract_current_user(
    auth_result: AuthServiceOutput,
) -> tuple[User | None, str | None, int]:
    if not auth_result.status:
        return (
            None,
            to_user_error_message(
                error=auth_result.error,
                status_code=auth_result.code,
                fallback="Unauthorized.",
            ),
            auth_result.code,
        )
    if not isinstance(auth_result.data, User):
        return None, "Unexpected auth payload.", status.HTTP_500_INTERNAL_SERVER_ERROR
    return auth_result.data, None, status.HTTP_200_OK


def _is_admin(user: User) -> bool:
    return (user.role or "").lower() == "admin"


def _can_access_user(current_user: User, target_user_id: str) -> bool:
    return _is_admin(current_user) or (current_user.id == target_user_id)


def _resolve_avatar_extension(file_name: str | None, content_type: str) -> str:
    file_extension = Path(file_name or "").suffix.lower()
    if file_extension in _allowed_avatar_extensions:
        return ".jpg" if file_extension == ".jpeg" else file_extension
    return _avatar_extension_by_content_type.get(content_type.lower(), ".jpg")


def _build_avatar_public_url(request: Request, file_name: str) -> str:
    return f"{str(request.base_url).rstrip('/')}/uploads/avatars/{file_name}"


@user_router.get(
    "",
    response_model=UserListAPIOutput,
    status_code=status.HTTP_200_OK,
    summary="Get users",
)
async def get_users(
    limit: int | None = Query(None, ge=1, le=200),
    current_user_result: AuthServiceOutput = Depends(get_current_user),
) -> UserListAPIOutput | JSONResponse:
    current_user, auth_error, auth_code = _extract_current_user(current_user_result)
    if auth_error:
        return _json_response(
            UserListAPIOutput(success=False, data=None, error=auth_error), auth_code
        )
    assert current_user is not None

    if not _is_admin(current_user):
        return _json_response(
            UserListAPIOutput(success=False, data=None, error="Forbidden user access."),
            status.HTTP_403_FORBIDDEN,
        )

    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, partial(_service.get_users, limit))
    except asyncio.CancelledError:
        logger.warning("Get users request was cancelled by the client.")
        raise
    except Exception as exc:
        logger.exception("Unhandled exception while getting users.", error=str(exc))
        return _json_response(
            UserListAPIOutput(
                success=False,
                data=None,
                error="Unexpected error while getting users.",
            ),
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    if not result.status:
        return _json_response(
            UserListAPIOutput(
                success=False,
                data=None,
                error=to_user_error_message(
                    error=result.error,
                    status_code=result.code,
                    fallback="Get users failed.",
                ),
            ),
            result.code,
        )

    users = result.data if isinstance(result.data, list) else []
    return UserListAPIOutput(
        success=True, data=UserListAPIData.from_domain(users), error=None
    )


@user_router.get(
    "/{user_id}",
    response_model=UserAPIOutput,
    status_code=status.HTTP_200_OK,
    summary="Get user by id",
)
async def get_user_by_id(
    user_id: str,
    current_user_result: AuthServiceOutput = Depends(get_current_user),
) -> UserAPIOutput | JSONResponse:
    current_user, auth_error, auth_code = _extract_current_user(current_user_result)
    if auth_error:
        return _json_response(
            UserAPIOutput(success=False, data=None, error=auth_error), auth_code
        )
    assert current_user is not None

    if not _can_access_user(current_user, user_id):
        return _json_response(
            UserAPIOutput(success=False, data=None, error="Forbidden user access."),
            status.HTTP_403_FORBIDDEN,
        )

    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            partial(_service.get_user_by_id, GetUserByIdInput(user_id=user_id)),
        )
    except asyncio.CancelledError:
        logger.warning(
            "Get user by id request was cancelled by the client.", user_id=user_id
        )
        raise
    except Exception as exc:
        logger.exception(
            "Unhandled exception while getting user by id.",
            error=str(exc),
            user_id=user_id,
        )
        return _json_response(
            UserAPIOutput(
                success=False,
                data=None,
                error="Unexpected error while getting user.",
            ),
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    if not result.status or not isinstance(result.data, User):
        return _json_response(
            UserAPIOutput(
                success=False,
                data=None,
                error=to_user_error_message(
                    error=result.error,
                    status_code=result.code,
                    fallback="Get user failed.",
                ),
            ),
            result.code,
        )

    return UserAPIOutput(
        success=True, data=UserAPIData.from_domain(result.data), error=None
    )


@user_router.post(
    "",
    response_model=UserAPIOutput,
    status_code=status.HTTP_201_CREATED,
    summary="Create a user",
)
async def create_user(input: UserCreateAPIInput) -> UserAPIOutput | JSONResponse:
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            partial(
                _service.create_user,
                CreateUserInput(
                    user_name=input.user_name,
                    email=input.email,
                    password=input.password,
                    full_name=input.full_name,
                    phone=input.phone,
                    avatar_url=input.avatar_url,
                    is_active=input.is_active,
                    email_verified=input.email_verified,
                    role=input.role,
                ),
            ),
        )
    except asyncio.CancelledError:
        logger.warning("Create user request was cancelled by the client.")
        raise
    except Exception as exc:
        logger.exception("Unhandled exception while creating user.", error=str(exc))
        return _json_response(
            UserAPIOutput(
                success=False,
                data=None,
                error="Unexpected error while creating user.",
            ),
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    if not result.status or not isinstance(result.data, User):
        return _json_response(
            UserAPIOutput(
                success=False,
                data=None,
                error=to_user_error_message(
                    error=result.error,
                    status_code=result.code,
                    fallback="Create user failed.",
                ),
            ),
            result.code,
        )

    return UserAPIOutput(
        success=True, data=UserAPIData.from_domain(result.data), error=None
    )


@user_router.put(
    "/{user_id}",
    response_model=UserAPIOutput,
    status_code=status.HTTP_200_OK,
    summary="Update a user",
)
async def update_user(
    user_id: str,
    input: UserUpdateAPIInput,
    current_user_result: AuthServiceOutput = Depends(get_current_user),
) -> UserAPIOutput | JSONResponse:
    current_user, auth_error, auth_code = _extract_current_user(current_user_result)
    if auth_error:
        return _json_response(
            UserAPIOutput(success=False, data=None, error=auth_error), auth_code
        )
    assert current_user is not None

    if not _can_access_user(current_user, user_id):
        return _json_response(
            UserAPIOutput(success=False, data=None, error="Forbidden user access."),
            status.HTTP_403_FORBIDDEN,
        )

    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            partial(
                _service.update_user,
                UpdateUserInput(
                    user_id=user_id,
                    user_name=input.user_name,
                    email=input.email,
                    password=input.password,
                    full_name=input.full_name,
                    phone=input.phone,
                    avatar_url=input.avatar_url,
                    is_active=input.is_active,
                    email_verified=input.email_verified,
                    role=input.role,
                ),
            ),
        )
    except asyncio.CancelledError:
        logger.warning(
            "Update user request was cancelled by the client.", user_id=user_id
        )
        raise
    except Exception as exc:
        logger.exception(
            "Unhandled exception while updating user.", error=str(exc), user_id=user_id
        )
        return _json_response(
            UserAPIOutput(
                success=False,
                data=None,
                error="Unexpected error while updating user.",
            ),
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    if not result.status or not isinstance(result.data, User):
        return _json_response(
            UserAPIOutput(
                success=False,
                data=None,
                error=to_user_error_message(
                    error=result.error,
                    status_code=result.code,
                    fallback="Update user failed.",
                ),
            ),
            result.code,
        )

    return UserAPIOutput(
        success=True, data=UserAPIData.from_domain(result.data), error=None
    )


@user_router.post(
    "/{user_id}/avatar",
    response_model=UserAPIOutput,
    status_code=status.HTTP_200_OK,
    summary="Upload user avatar",
)
async def upload_user_avatar(
    user_id: str,
    request: Request,
    file: UploadFile = File(...),
    current_user_result: AuthServiceOutput = Depends(get_current_user),
) -> UserAPIOutput | JSONResponse:
    current_user, auth_error, auth_code = _extract_current_user(current_user_result)
    if auth_error:
        return _json_response(
            UserAPIOutput(success=False, data=None, error=auth_error), auth_code
        )
    assert current_user is not None

    if not _can_access_user(current_user, user_id):
        return _json_response(
            UserAPIOutput(success=False, data=None, error="Forbidden user access."),
            status.HTTP_403_FORBIDDEN,
        )

    content_type = (file.content_type or "").lower()
    if content_type not in _allowed_avatar_content_types:
        return _json_response(
            UserAPIOutput(
                success=False,
                data=None,
                error="Unsupported avatar format. Please upload JPG, PNG, WEBP, or GIF.",
            ),
            status.HTTP_400_BAD_REQUEST,
        )

    temp_file_path: Path | None = None
    try:
        file_content = await file.read(_avatar_max_size_bytes + 1)
        if not file_content:
            return _json_response(
                UserAPIOutput(success=False, data=None, error="Avatar file is empty."),
                status.HTTP_400_BAD_REQUEST,
            )
        if len(file_content) > _avatar_max_size_bytes:
            return _json_response(
                UserAPIOutput(
                    success=False,
                    data=None,
                    error=f"Avatar file is too large (max {_avatar_max_size_bytes // (1024 * 1024)}MB).",
                ),
                status.HTTP_400_BAD_REQUEST,
            )

        _avatar_upload_dir.mkdir(parents=True, exist_ok=True)
        file_extension = _resolve_avatar_extension(file.filename, content_type)
        avatar_file_name = f"{user_id}_{uuid4().hex}{file_extension}"
        temp_file_path = _avatar_upload_dir / avatar_file_name
        temp_file_path.write_bytes(file_content)
        avatar_public_url = _build_avatar_public_url(request, avatar_file_name)

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            partial(
                _service.update_user,
                UpdateUserInput(
                    user_id=user_id,
                    avatar_url=avatar_public_url,
                ),
            ),
        )
    except asyncio.CancelledError:
        logger.warning(
            "Upload avatar request was cancelled by the client.", user_id=user_id
        )
        raise
    except Exception as exc:
        logger.exception(
            "Unhandled exception while uploading avatar.",
            error=str(exc),
            user_id=user_id,
        )
        return _json_response(
            UserAPIOutput(
                success=False,
                data=None,
                error="Unexpected error while uploading avatar.",
            ),
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    finally:
        await file.close()

    if not result.status or not isinstance(result.data, User):
        if temp_file_path is not None:
            try:
                temp_file_path.unlink(missing_ok=True)
            except OSError:
                logger.warning(
                    "Failed to cleanup uploaded avatar after failed update.",
                    path=str(temp_file_path),
                )
        return _json_response(
            UserAPIOutput(
                success=False,
                data=None,
                error=to_user_error_message(
                    error=result.error,
                    status_code=result.code,
                    fallback="Upload avatar failed.",
                ),
            ),
            result.code,
        )

    return UserAPIOutput(
        success=True, data=UserAPIData.from_domain(result.data), error=None
    )


@user_router.delete(
    "/{user_id}",
    response_model=UserDeleteAPIOutput,
    status_code=status.HTTP_200_OK,
    summary="Delete a user",
)
async def delete_user(
    user_id: str,
    current_user_result: AuthServiceOutput = Depends(get_current_user),
) -> UserDeleteAPIOutput | JSONResponse:
    current_user, auth_error, auth_code = _extract_current_user(current_user_result)
    if auth_error:
        return _json_response(
            UserDeleteAPIOutput(success=False, data=None, error=auth_error), auth_code
        )
    assert current_user is not None

    if not _can_access_user(current_user, user_id):
        return _json_response(
            UserDeleteAPIOutput(
                success=False, data=None, error="Forbidden user access."
            ),
            status.HTTP_403_FORBIDDEN,
        )

    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            partial(_service.delete_user, DeleteUserInput(user_id=user_id)),
        )
    except asyncio.CancelledError:
        logger.warning(
            "Delete user request was cancelled by the client.", user_id=user_id
        )
        raise
    except Exception as exc:
        logger.exception(
            "Unhandled exception while deleting user.", error=str(exc), user_id=user_id
        )
        return _json_response(
            UserDeleteAPIOutput(
                success=False,
                data=None,
                error="Unexpected error while deleting user.",
            ),
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    if not result.status:
        return _json_response(
            UserDeleteAPIOutput(
                success=False,
                data=None,
                error=to_user_error_message(
                    error=result.error,
                    status_code=result.code,
                    fallback="Delete user failed.",
                ),
            ),
            result.code,
        )

    return UserDeleteAPIOutput(
        success=True,
        data=UserDeleteAPIData(id=user_id, deleted=True),
        error=None,
    )
