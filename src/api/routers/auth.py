from __future__ import annotations

import asyncio
from functools import partial
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from fastapi.responses import RedirectResponse
from starlette.responses import Response

from api.dependencies import get_current_user
from api.helpers.exception_handler import to_user_error_message
from api.models.auth import (
    AuthTokenAPIData,
    ForgotPasswordResetAPIData,
    ForgotPasswordResetAPIInput,
    ForgotPasswordResetAPIOutput,
    ForgotPasswordSendOtpAPIData,
    ForgotPasswordSendOtpAPIInput,
    ForgotPasswordSendOtpAPIOutput,
    ForgotPasswordVerifyOtpAPIData,
    ForgotPasswordVerifyOtpAPIInput,
    ForgotPasswordVerifyOtpAPIOutput,
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
    GoogleAuthCallbackInput,
    GoogleAuthService,
    LoginInput,
    LogoutInput,
    PasswordResetService,
    RefreshInput,
    ResetPasswordInput,
    SendPasswordResetOtpInput,
    VerifyPasswordResetOtpInput,
)
from infra.database.pg.schemas import User
from shared.logging import get_logger, redact_message
from shared.settings import Settings

logger = get_logger(__name__)

auth_router = APIRouter(prefix="/auth", tags=["Auth"])

_service = AuthService()
_google_auth_service = GoogleAuthService()
_password_reset_service = PasswordResetService()
_settings = Settings()


def _json_response(payload: Any, status_code: int) -> JSONResponse:
    return JSONResponse(
        status_code=status_code, content=payload.model_dump(mode="json")
    )


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
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


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=_settings.auth.refresh_cookie_name,
        path=_settings.auth.refresh_cookie_path,
    )


def _set_google_state_cookie(
    response: RedirectResponse, state_cookie_value: str
) -> None:
    response.set_cookie(
        key=_settings.auth.google_state_cookie_name,
        value=state_cookie_value,
        max_age=_settings.auth.google_state_ttl_seconds,
        httponly=True,
        secure=_settings.auth.google_state_cookie_secure,
        samesite=_settings.auth.google_state_cookie_samesite,
        path=_settings.auth.google_state_cookie_path,
    )


def _clear_google_state_cookie(response: RedirectResponse) -> None:
    response.delete_cookie(
        key=_settings.auth.google_state_cookie_name,
        path=_settings.auth.google_state_cookie_path,
    )


def _append_query_param(url: str, key: str, value: str) -> str:
    parsed = urlparse(url)
    pairs = parse_qsl(parsed.query, keep_blank_values=True)
    pairs.append((key, value))
    query = urlencode(pairs)
    return urlunparse(parsed._replace(query=query))


def _google_error_redirect(code: str) -> RedirectResponse:
    target = _append_query_param(_settings.auth.google_fe_error_redirect, "error", code)
    response = RedirectResponse(url=target, status_code=status.HTTP_302_FOUND)
    _clear_google_state_cookie(response)
    return response


def _google_success_redirect() -> RedirectResponse:
    target = _append_query_param(
        _settings.auth.google_fe_success_redirect, "status", "success"
    )
    response = RedirectResponse(url=target, status_code=status.HTTP_302_FOUND)
    _clear_google_state_cookie(response)
    return response


def _client_ip(request: Request) -> str | None:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


@auth_router.get(
    "/google/login",
    status_code=status.HTTP_302_FOUND,
    summary="Start Google OAuth login",
)
async def google_login() -> RedirectResponse:
    start_result = _google_auth_service.build_authorization_request()
    if not start_result.status or not isinstance(start_result.data, dict):
        logger.warning(
            "google_login_start_failed",
            error=redact_message(start_result.error or "Google login init failed."),
        )
        return _google_error_redirect("google_login_unavailable")

    authorize_url = str(start_result.data.get("authorize_url", "")).strip()
    state_cookie_value = str(start_result.data.get("state_cookie_value", "")).strip()
    if not authorize_url or not state_cookie_value:
        return _google_error_redirect("google_login_unavailable")

    response = RedirectResponse(url=authorize_url, status_code=status.HTTP_302_FOUND)
    _set_google_state_cookie(response, state_cookie_value)
    return response


@auth_router.get(
    "/google/callback",
    status_code=status.HTTP_302_FOUND,
    summary="Google OAuth callback",
)
async def google_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    if error:
        logger.warning("google_callback_error", error=error)
        return _google_error_redirect("google_oauth_denied")

    if not code or not state:
        return _google_error_redirect("google_invalid_request")

    state_cookie_value = request.cookies.get(_settings.auth.google_state_cookie_name)
    if not state_cookie_value:
        return _google_error_redirect("google_invalid_state")

    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            partial(
                _google_auth_service.authenticate_with_google,
                GoogleAuthCallbackInput(
                    code=code,
                    state=state,
                    state_cookie_value=state_cookie_value,
                    ip=_client_ip(request),
                    user_agent=request.headers.get("user-agent"),
                ),
            ),
        )
    except asyncio.CancelledError:
        logger.warning("Google callback request was cancelled by the client.")
        raise
    except Exception as exc:
        logger.exception("Unhandled exception while google callback.", error=str(exc))
        return _google_error_redirect("google_callback_failed")

    if not result.status:
        if result.code == status.HTTP_423_LOCKED:
            return _google_error_redirect("inactive_user")
        if result.code == status.HTTP_409_CONFLICT:
            return _google_error_redirect("google_account_conflict")
        if result.code == status.HTTP_401_UNAUTHORIZED:
            return _google_error_redirect("google_auth_invalid")
        return _google_error_redirect("google_callback_failed")

    refresh_token = str((result.data or {}).get("refresh_token", "")).strip()
    if not refresh_token:
        return _google_error_redirect("google_callback_failed")

    response = _google_success_redirect()
    _set_refresh_cookie(response, refresh_token)
    return response


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
                error=to_user_error_message(
                    error=result.error,
                    status_code=result.code,
                    fallback="Login failed.",
                ),
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
                error=to_user_error_message(
                    error=result.error,
                    status_code=result.code,
                    fallback="Refresh failed.",
                ),
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
                error=to_user_error_message(
                    error=result.error,
                    status_code=result.code,
                    fallback="Logout failed.",
                ),
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
                error=to_user_error_message(
                    error=current_user_result.error,
                    status_code=current_user_result.code,
                    fallback="Unauthorized.",
                ),
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


@auth_router.post(
    "/forgot-password/send-otp",
    response_model=ForgotPasswordSendOtpAPIOutput,
    status_code=status.HTTP_200_OK,
    summary="Send OTP for forgot-password flow",
)
async def forgot_password_send_otp(
    input: ForgotPasswordSendOtpAPIInput,
    request: Request,
) -> ForgotPasswordSendOtpAPIOutput | JSONResponse:
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            partial(
                _password_reset_service.send_otp,
                SendPasswordResetOtpInput(
                    email=input.email,
                    ip=_client_ip(request),
                    user_agent=request.headers.get("user-agent"),
                ),
            ),
        )
    except asyncio.CancelledError:
        logger.warning("Forgot-password send OTP request was cancelled by the client.")
        raise
    except Exception as exc:
        logger.exception(
            "Unhandled exception while sending forgot-password OTP.", error=str(exc)
        )
        return _json_response(
            ForgotPasswordSendOtpAPIOutput(
                success=False,
                data=None,
                error="Unexpected error while sending OTP.",
            ),
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    if not result.status:
        return _json_response(
            ForgotPasswordSendOtpAPIOutput(
                success=False,
                data=None,
                error=to_user_error_message(
                    error=result.error,
                    status_code=result.code,
                    fallback="Send OTP failed.",
                ),
            ),
            result.code,
        )

    payload = result.data if isinstance(result.data, dict) else {}
    return ForgotPasswordSendOtpAPIOutput(
        success=True,
        data=ForgotPasswordSendOtpAPIData(
            sent=bool(payload.get("sent", True)),
            expires_in=int(payload.get("expires_in", 0)),
            message=str(payload.get("message", "OTP sent.")),
        ),
        error=None,
    )


@auth_router.post(
    "/forgot-password/verify-otp",
    response_model=ForgotPasswordVerifyOtpAPIOutput,
    status_code=status.HTTP_200_OK,
    summary="Verify forgot-password OTP and issue reset token",
)
async def forgot_password_verify_otp(
    input: ForgotPasswordVerifyOtpAPIInput,
) -> ForgotPasswordVerifyOtpAPIOutput | JSONResponse:
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            partial(
                _password_reset_service.verify_otp,
                VerifyPasswordResetOtpInput(email=input.email, otp=input.otp),
            ),
        )
    except asyncio.CancelledError:
        logger.warning(
            "Forgot-password verify OTP request was cancelled by the client."
        )
        raise
    except Exception as exc:
        logger.exception(
            "Unhandled exception while verifying forgot-password OTP.", error=str(exc)
        )
        return _json_response(
            ForgotPasswordVerifyOtpAPIOutput(
                success=False,
                data=None,
                error="Unexpected error while verifying OTP.",
            ),
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    if not result.status:
        return _json_response(
            ForgotPasswordVerifyOtpAPIOutput(
                success=False,
                data=None,
                error=to_user_error_message(
                    error=result.error,
                    status_code=result.code,
                    fallback="Verify OTP failed.",
                ),
            ),
            result.code,
        )

    payload = result.data if isinstance(result.data, dict) else {}
    return ForgotPasswordVerifyOtpAPIOutput(
        success=True,
        data=ForgotPasswordVerifyOtpAPIData(
            verified=bool(payload.get("verified", True)),
            reset_token=str(payload.get("reset_token", "")),
            expires_in=int(payload.get("expires_in", 0)),
        ),
        error=None,
    )


@auth_router.post(
    "/forgot-password/reset",
    response_model=ForgotPasswordResetAPIOutput,
    status_code=status.HTTP_200_OK,
    summary="Reset password using reset token from verified OTP",
)
async def forgot_password_reset(
    input: ForgotPasswordResetAPIInput,
) -> ForgotPasswordResetAPIOutput | JSONResponse:
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            partial(
                _password_reset_service.reset_password,
                ResetPasswordInput(
                    reset_token=input.reset_token,
                    new_password=input.new_password,
                ),
            ),
        )
    except asyncio.CancelledError:
        logger.warning("Forgot-password reset request was cancelled by the client.")
        raise
    except Exception as exc:
        logger.exception(
            "Unhandled exception while resetting forgot-password password.",
            error=str(exc),
        )
        return _json_response(
            ForgotPasswordResetAPIOutput(
                success=False,
                data=None,
                error="Unexpected error while resetting password.",
            ),
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    if not result.status:
        return _json_response(
            ForgotPasswordResetAPIOutput(
                success=False,
                data=None,
                error=to_user_error_message(
                    error=result.error,
                    status_code=result.code,
                    fallback="Reset password failed.",
                ),
            ),
            result.code,
        )

    payload = result.data if isinstance(result.data, dict) else {}
    return ForgotPasswordResetAPIOutput(
        success=True,
        data=ForgotPasswordResetAPIData(reset=bool(payload.get("reset", True))),
        error=None,
    )
