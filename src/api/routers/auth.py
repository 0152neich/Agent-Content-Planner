from __future__ import annotations

import asyncio
from functools import partial
from typing import Any

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse

from api.dependencies import get_current_user
from api.models.auth import (
    AuthTokenAPIData,
    LoginAPIInput,
    LoginAPIOutput,
    LogoutAPIData,
    LogoutAPIOutput,
    MeAPIOutput,
    RefreshAPIOutput,
)
from api.models.user import UserAPIData
from app.services import (
    AuthService,
    AuthServiceOutput,
    LoginInput,
    LogoutInput,
    RefreshInput,
)
from infra.database.pg.schemas import User
from shared.logging import get_logger, redact_message
from shared.settings import Settings

logger = get_logger(__name__)

auth_router = APIRouter(prefix="/auth", tags=["Auth"])

_service = AuthService()
_settings = Settings()


def _json_response(payload: Any, status_code: int) -> JSONResponse:
    return JSONResponse(
        status_code=status_code, content=payload.model_dump(mode="json")
    )


def _set_refresh_cookie(response: JSONResponse, refresh_token: str) -> None:
    max_age = _settings.auth.refresh_token_ttl_days * 24 * 60 * 60
    response.set_cookie(
        key=_settings.auth.refresh_cookie_name,
        value=refresh_token,
        max_age=max_age,
        httponly=True,
        secure=_settings.auth.refresh_cookie_secure,
        samesite=_settings.auth.refresh_cookie_samesite,
        path=_settings.auth.refresh_cookie_path,
    )


def _clear_refresh_cookie(response: JSONResponse) -> None:
    response.delete_cookie(
        key=_settings.auth.refresh_cookie_name,
        path=_settings.auth.refresh_cookie_path,
    )


def _client_ip(request: Request) -> str | None:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


@auth_router.post(
    "/login",
    response_model=LoginAPIOutput,
    status_code=status.HTTP_200_OK,
    summary="Authenticate user and issue tokens",
)
async def login(
    input: LoginAPIInput, request: Request
) -> LoginAPIOutput | JSONResponse:
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            partial(
                _service.login,
                LoginInput(
                    identifier=input.identifier,
                    password=input.password,
                    ip=_client_ip(request),
                    user_agent=request.headers.get("user-agent"),
                ),
            ),
        )
    except asyncio.CancelledError:
        logger.warning("Login request was cancelled by the client.")
        raise
    except Exception as exc:
        logger.exception("Unhandled exception while login.", error=str(exc))
        return _json_response(
            LoginAPIOutput(
                success=False, data=None, error="Unexpected error while login."
            ),
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    if not result.status:
        return _json_response(
            LoginAPIOutput(
                success=False,
                data=None,
                error=redact_message(result.error or "Login failed."),
            ),
            result.code,
        )

    try:
        auth_data = AuthTokenAPIData.from_service_payload(result.data or {})
        refresh_token = str((result.data or {}).get("refresh_token", ""))
        response = _json_response(
            LoginAPIOutput(success=True, data=auth_data, error=None), status.HTTP_200_OK
        )
        if refresh_token:
            _set_refresh_cookie(response, refresh_token)
        return response
    except Exception as exc:
        logger.exception("Failed to build login response.", error=str(exc))
        return _json_response(
            LoginAPIOutput(
                success=False, data=None, error="Unexpected error while login."
            ),
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@auth_router.post(
    "/refresh",
    response_model=RefreshAPIOutput,
    status_code=status.HTTP_200_OK,
    summary="Rotate refresh token and issue a new access token",
)
async def refresh(request: Request) -> RefreshAPIOutput | JSONResponse:
    refresh_token = request.cookies.get(_settings.auth.refresh_cookie_name)
    if not refresh_token:
        return _json_response(
            RefreshAPIOutput(success=False, data=None, error="Invalid refresh token."),
            status.HTTP_401_UNAUTHORIZED,
        )

    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            partial(
                _service.refresh,
                RefreshInput(
                    refresh_token=refresh_token,
                    ip=_client_ip(request),
                    user_agent=request.headers.get("user-agent"),
                ),
            ),
        )
    except asyncio.CancelledError:
        logger.warning("Refresh request was cancelled by the client.")
        raise
    except Exception as exc:
        logger.exception("Unhandled exception while refresh.", error=str(exc))
        return _json_response(
            RefreshAPIOutput(
                success=False, data=None, error="Unexpected error while refresh."
            ),
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    if not result.status:
        return _json_response(
            RefreshAPIOutput(
                success=False,
                data=None,
                error=redact_message(result.error or "Refresh failed."),
            ),
            result.code,
        )

    try:
        auth_data = AuthTokenAPIData.from_service_payload(result.data or {})
        next_refresh_token = str((result.data or {}).get("refresh_token", ""))
        response = _json_response(
            RefreshAPIOutput(success=True, data=auth_data, error=None),
            status.HTTP_200_OK,
        )
        if next_refresh_token:
            _set_refresh_cookie(response, next_refresh_token)
        return response
    except Exception as exc:
        logger.exception("Failed to build refresh response.", error=str(exc))
        return _json_response(
            RefreshAPIOutput(
                success=False, data=None, error="Unexpected error while refresh."
            ),
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@auth_router.post(
    "/logout",
    response_model=LogoutAPIOutput,
    status_code=status.HTTP_200_OK,
    summary="Revoke current refresh token and clear cookie",
)
async def logout(request: Request) -> LogoutAPIOutput | JSONResponse:
    refresh_token = request.cookies.get(_settings.auth.refresh_cookie_name)
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            partial(_service.logout, LogoutInput(refresh_token=refresh_token)),
        )
    except asyncio.CancelledError:
        logger.warning("Logout request was cancelled by the client.")
        raise
    except Exception as exc:
        logger.exception("Unhandled exception while logout.", error=str(exc))
        response = _json_response(
            LogoutAPIOutput(
                success=False, data=None, error="Unexpected error while logout."
            ),
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
        _clear_refresh_cookie(response)
        return response

    if not result.status:
        response = _json_response(
            LogoutAPIOutput(
                success=False,
                data=None,
                error=redact_message(result.error or "Logout failed."),
            ),
            result.code,
        )
        _clear_refresh_cookie(response)
        return response

    response = _json_response(
        LogoutAPIOutput(success=True, data=LogoutAPIData(logged_out=True), error=None),
        status.HTTP_200_OK,
    )
    _clear_refresh_cookie(response)
    return response


@auth_router.get(
    "/me",
    response_model=MeAPIOutput,
    status_code=status.HTTP_200_OK,
    summary="Get current authenticated user profile",
)
async def me(
    current_user_result: AuthServiceOutput = Depends(get_current_user),
) -> MeAPIOutput | JSONResponse:
    if not current_user_result.status:
        return _json_response(
            MeAPIOutput(
                success=False,
                data=None,
                error=redact_message(current_user_result.error or "Unauthorized."),
            ),
            current_user_result.code,
        )

    if not isinstance(current_user_result.data, User):
        return _json_response(
            MeAPIOutput(success=False, data=None, error="Unexpected auth payload."),
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    return MeAPIOutput(
        success=True, data=UserAPIData.from_domain(current_user_result.data), error=None
    )
