from __future__ import annotations

import asyncio
from functools import partial
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse, RedirectResponse

from api.dependencies import get_current_user
from api.helpers.exception_handler import to_user_error_message
from api.models.social_publish import (
    FacebookConnectionStatusAPIData,
    FacebookConnectionStatusAPIOutput,
    FacebookConnectStartAPIData,
    FacebookConnectStartAPIOutput,
    FacebookDisconnectAPIData,
    FacebookDisconnectAPIOutput,
    FacebookPageAPIData,
    FacebookPagesListAPIOutput,
    LinkedInConnectionStatusAPIData,
    LinkedInConnectionStatusAPIOutput,
    LinkedInConnectStartAPIData,
    LinkedInConnectStartAPIOutput,
    LinkedInDisconnectAPIData,
    LinkedInDisconnectAPIOutput,
    SocialPublishAPIData,
    SocialPublishAPIInput,
    SocialPublishAPIOutput,
)
from app.services import (
    AuthServiceOutput,
    FacebookConnectionService,
    FacebookOAuthCallbackInput,
    LinkedInConnectionService,
    LinkedInOAuthCallbackInput,
    SocialPublishInput,
    SocialPublishService,
)
from infra.database.pg.schemas import User
from shared.logging import get_logger
from shared.settings import Settings

logger = get_logger(__name__)

social_publish_router = APIRouter(prefix="/social", tags=["Social Publish"])
_publish_service = SocialPublishService()
_linkedin_connection_service = LinkedInConnectionService()
_facebook_connection_service = FacebookConnectionService()
_settings = Settings()


def _json_response(payload: Any, status_code: int) -> JSONResponse:
    return JSONResponse(
        status_code=status_code, content=payload.model_dump(mode="json")
    )


def _extract_user(
    auth_result: AuthServiceOutput,
) -> tuple[User | None, JSONResponse | None]:
    if not auth_result.status:
        return None, _json_response(
            SocialPublishAPIOutput(
                success=False,
                data=None,
                error=to_user_error_message(
                    error=auth_result.error,
                    status_code=auth_result.code,
                    fallback="Unauthorized.",
                ),
                code=None,
            ),
            auth_result.code,
        )
    if not isinstance(auth_result.data, User):
        return None, _json_response(
            SocialPublishAPIOutput(
                success=False, data=None, error="Unexpected auth payload.", code=None
            ),
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    return auth_result.data, None


def _append_query_param(url: str, key: str, value: str) -> str:
    parsed = urlparse(url)
    pairs = parse_qsl(parsed.query, keep_blank_values=True)
    pairs.append((key, value))
    query = urlencode(pairs)
    return urlunparse(parsed._replace(query=query))


def _resolve_oauth_return_target(
    return_to: str | None,
    *,
    fallback_url: str,
) -> str:
    fallback = fallback_url.strip()
    if not return_to:
        return fallback

    raw = return_to.strip()
    if not raw:
        return fallback

    fallback_parsed = urlparse(fallback)
    fallback_origin = f"{fallback_parsed.scheme}://{fallback_parsed.netloc}".strip(":/")
    if fallback_parsed.scheme and fallback_parsed.netloc:
        fallback_origin = f"{fallback_parsed.scheme}://{fallback_parsed.netloc}"
    else:
        fallback_origin = ""

    if raw.startswith("/"):
        return f"{fallback_origin}{raw}" if fallback_origin else raw

    if raw.startswith("http://") or raw.startswith("https://"):
        parsed = urlparse(raw)
        if not parsed.path:
            return fallback
        path_and_query = parsed.path
        if parsed.query:
            path_and_query += f"?{parsed.query}"
        return (
            f"{fallback_origin}{path_and_query}" if fallback_origin else path_and_query
        )

    return fallback


@social_publish_router.get(
    "/linkedin/connection",
    response_model=LinkedInConnectionStatusAPIOutput,
    status_code=status.HTTP_200_OK,
    summary="Get current user's LinkedIn connection status",
)
async def get_linkedin_connection(
    current_user_result: AuthServiceOutput = Depends(get_current_user),
) -> LinkedInConnectionStatusAPIOutput | JSONResponse:
    user, error_response = _extract_user(current_user_result)
    if error_response:
        return error_response
    assert user is not None

    result = _linkedin_connection_service.get_connection(user)
    if not result.status or not isinstance(result.data, dict):
        return _json_response(
            LinkedInConnectionStatusAPIOutput(
                success=False, data=None, error=result.error, code=result.error_code
            ),
            result.code,
        )

    return LinkedInConnectionStatusAPIOutput(
        success=True,
        data=LinkedInConnectionStatusAPIData(
            connected=bool(result.data.get("connected")),
            provider=str(result.data.get("provider") or "linkedin"),
            display_name=result.data.get("display_name"),
            member_urn=result.data.get("member_urn"),
            expires_at=result.data.get("expires_at"),
        ),
        error=None,
        code=None,
    )


@social_publish_router.post(
    "/linkedin/connect",
    response_model=LinkedInConnectStartAPIOutput,
    status_code=status.HTTP_200_OK,
    summary="Start LinkedIn OAuth flow for current user",
)
async def start_linkedin_connect(
    return_to: str | None = None,
    current_user_result: AuthServiceOutput = Depends(get_current_user),
) -> LinkedInConnectStartAPIOutput | JSONResponse:
    user, error_response = _extract_user(current_user_result)
    if error_response:
        return error_response
    assert user is not None

    result = _linkedin_connection_service.build_connect_url(user, return_to=return_to)
    if not result.status or not isinstance(result.data, dict):
        return _json_response(
            LinkedInConnectStartAPIOutput(
                success=False, data=None, error=result.error, code=result.error_code
            ),
            result.code,
        )

    authorize_url = str(result.data.get("authorize_url") or "").strip()
    if not authorize_url:
        return _json_response(
            LinkedInConnectStartAPIOutput(
                success=False,
                data=None,
                error="LinkedIn authorize URL is missing.",
                code="SOCIAL_CONFIG_INVALID",
            ),
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    return LinkedInConnectStartAPIOutput(
        success=True,
        data=LinkedInConnectStartAPIData(authorize_url=authorize_url),
        error=None,
        code=None,
    )


@social_publish_router.get(
    "/linkedin/callback",
    status_code=status.HTTP_302_FOUND,
    summary="LinkedIn OAuth callback",
)
async def linkedin_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    if error:
        target = _append_query_param(
            _settings.auth.linkedin_fe_error_redirect,
            "linkedin_error",
            "oauth_denied",
        )
        return RedirectResponse(url=target, status_code=status.HTTP_302_FOUND)

    if not code or not state:
        target = _append_query_param(
            _settings.auth.linkedin_fe_error_redirect,
            "linkedin_error",
            "invalid_request",
        )
        return RedirectResponse(url=target, status_code=status.HTTP_302_FOUND)

    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            partial(
                _linkedin_connection_service.handle_callback,
                LinkedInOAuthCallbackInput(code=code, state=state),
            ),
        )
    except Exception as exc:
        logger.exception("linkedin_callback_unhandled_exception", error=str(exc))
        target = _append_query_param(
            _settings.auth.linkedin_fe_error_redirect,
            "linkedin_error",
            "callback_failed",
        )
        return RedirectResponse(url=target, status_code=status.HTTP_302_FOUND)

    if not result.status:
        target = _append_query_param(
            _settings.auth.linkedin_fe_error_redirect,
            "linkedin_error",
            str(result.error_code or "callback_failed").lower(),
        )
        return RedirectResponse(url=target, status_code=status.HTTP_302_FOUND)

    return_to = None
    if isinstance(result.data, dict):
        raw_return_to = str(result.data.get("return_to") or "").strip()
        if raw_return_to.startswith("/"):
            return_to = raw_return_to
        elif raw_return_to.startswith("http://") or raw_return_to.startswith(
            "https://"
        ):
            parsed = urlparse(raw_return_to)
            if parsed.path:
                return_to = parsed.path
                if parsed.query:
                    return_to += f"?{parsed.query}"

    target_base = _resolve_oauth_return_target(
        return_to, fallback_url=_settings.auth.linkedin_fe_success_redirect
    )
    target = _append_query_param(target_base, "linkedin", "connected")
    return RedirectResponse(url=target, status_code=status.HTTP_302_FOUND)


@social_publish_router.delete(
    "/linkedin/connection",
    response_model=LinkedInDisconnectAPIOutput,
    status_code=status.HTTP_200_OK,
    summary="Disconnect current user's LinkedIn account",
)
async def disconnect_linkedin(
    current_user_result: AuthServiceOutput = Depends(get_current_user),
) -> LinkedInDisconnectAPIOutput | JSONResponse:
    user, error_response = _extract_user(current_user_result)
    if error_response:
        return error_response
    assert user is not None

    result = _linkedin_connection_service.disconnect(user)
    if not result.status or not isinstance(result.data, dict):
        return _json_response(
            LinkedInDisconnectAPIOutput(
                success=False, data=None, error=result.error, code=result.error_code
            ),
            result.code,
        )
    return LinkedInDisconnectAPIOutput(
        success=True,
        data=LinkedInDisconnectAPIData(
            disconnected=bool(result.data.get("disconnected"))
        ),
        error=None,
        code=None,
    )


@social_publish_router.get(
    "/facebook/connection",
    response_model=FacebookConnectionStatusAPIOutput,
    status_code=status.HTTP_200_OK,
    summary="Get current user's Facebook connection status",
)
async def get_facebook_connection(
    current_user_result: AuthServiceOutput = Depends(get_current_user),
) -> FacebookConnectionStatusAPIOutput | JSONResponse:
    user, error_response = _extract_user(current_user_result)
    if error_response:
        return error_response
    assert user is not None
    result = _facebook_connection_service.get_connection(user)
    if not result.status or not isinstance(result.data, dict):
        return _json_response(
            FacebookConnectionStatusAPIOutput(
                success=False, data=None, error=result.error, code=result.error_code
            ),
            result.code,
        )
    return FacebookConnectionStatusAPIOutput(
        success=True,
        data=FacebookConnectionStatusAPIData(
            connected=bool(result.data.get("connected")),
            provider=str(result.data.get("provider") or "facebook"),
            display_name=result.data.get("display_name"),
            account_id=result.data.get("account_id"),
            expires_at=result.data.get("expires_at"),
        ),
        error=None,
        code=None,
    )


@social_publish_router.post(
    "/facebook/connect",
    response_model=FacebookConnectStartAPIOutput,
    status_code=status.HTTP_200_OK,
    summary="Start Facebook OAuth flow for current user",
)
async def start_facebook_connect(
    return_to: str | None = None,
    current_user_result: AuthServiceOutput = Depends(get_current_user),
) -> FacebookConnectStartAPIOutput | JSONResponse:
    user, error_response = _extract_user(current_user_result)
    if error_response:
        return error_response
    assert user is not None
    result = _facebook_connection_service.build_connect_url(user, return_to=return_to)
    if not result.status or not isinstance(result.data, dict):
        return _json_response(
            FacebookConnectStartAPIOutput(
                success=False, data=None, error=result.error, code=result.error_code
            ),
            result.code,
        )
    authorize_url = str(result.data.get("authorize_url") or "").strip()
    if not authorize_url:
        return _json_response(
            FacebookConnectStartAPIOutput(
                success=False,
                data=None,
                error="Facebook authorize URL is missing.",
                code="SOCIAL_CONFIG_INVALID",
            ),
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    return FacebookConnectStartAPIOutput(
        success=True,
        data=FacebookConnectStartAPIData(authorize_url=authorize_url),
        error=None,
        code=None,
    )


@social_publish_router.get(
    "/facebook/callback",
    status_code=status.HTTP_302_FOUND,
    summary="Facebook OAuth callback",
)
async def facebook_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    if error:
        target = _append_query_param(
            _settings.auth.facebook_fe_error_redirect,
            "facebook_error",
            "oauth_denied",
        )
        return RedirectResponse(url=target, status_code=status.HTTP_302_FOUND)

    if not code or not state:
        target = _append_query_param(
            _settings.auth.facebook_fe_error_redirect,
            "facebook_error",
            "invalid_request",
        )
        return RedirectResponse(url=target, status_code=status.HTTP_302_FOUND)

    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            partial(
                _facebook_connection_service.handle_callback,
                FacebookOAuthCallbackInput(code=code, state=state),
            ),
        )
    except Exception as exc:
        logger.exception("facebook_callback_unhandled_exception", error=str(exc))
        target = _append_query_param(
            _settings.auth.facebook_fe_error_redirect,
            "facebook_error",
            "callback_failed",
        )
        return RedirectResponse(url=target, status_code=status.HTTP_302_FOUND)

    if not result.status:
        target = _append_query_param(
            _settings.auth.facebook_fe_error_redirect,
            "facebook_error",
            str(result.error_code or "callback_failed").lower(),
        )
        return RedirectResponse(url=target, status_code=status.HTTP_302_FOUND)

    return_to = None
    if isinstance(result.data, dict):
        raw_return_to = str(result.data.get("return_to") or "").strip()
        if raw_return_to.startswith("/"):
            return_to = raw_return_to
        elif raw_return_to.startswith("http://") or raw_return_to.startswith(
            "https://"
        ):
            parsed = urlparse(raw_return_to)
            if parsed.path:
                return_to = parsed.path
                if parsed.query:
                    return_to += f"?{parsed.query}"

    target_base = _resolve_oauth_return_target(
        return_to, fallback_url=_settings.auth.facebook_fe_success_redirect
    )
    target = _append_query_param(target_base, "facebook", "connected")
    return RedirectResponse(url=target, status_code=status.HTTP_302_FOUND)


@social_publish_router.delete(
    "/facebook/connection",
    response_model=FacebookDisconnectAPIOutput,
    status_code=status.HTTP_200_OK,
    summary="Disconnect current user's Facebook account",
)
async def disconnect_facebook(
    current_user_result: AuthServiceOutput = Depends(get_current_user),
) -> FacebookDisconnectAPIOutput | JSONResponse:
    user, error_response = _extract_user(current_user_result)
    if error_response:
        return error_response
    assert user is not None
    result = _facebook_connection_service.disconnect(user)
    if not result.status or not isinstance(result.data, dict):
        return _json_response(
            FacebookDisconnectAPIOutput(
                success=False, data=None, error=result.error, code=result.error_code
            ),
            result.code,
        )
    return FacebookDisconnectAPIOutput(
        success=True,
        data=FacebookDisconnectAPIData(
            disconnected=bool(result.data.get("disconnected"))
        ),
        error=None,
        code=None,
    )


@social_publish_router.get(
    "/facebook/pages",
    response_model=FacebookPagesListAPIOutput,
    status_code=status.HTTP_200_OK,
    summary="List Facebook pages available for current user",
)
async def list_facebook_pages(
    current_user_result: AuthServiceOutput = Depends(get_current_user),
) -> FacebookPagesListAPIOutput | JSONResponse:
    user, error_response = _extract_user(current_user_result)
    if error_response:
        return error_response
    assert user is not None
    result = _facebook_connection_service.list_pages(user)
    if not result.status:
        return _json_response(
            FacebookPagesListAPIOutput(
                success=False, data=None, error=result.error, code=result.error_code
            ),
            result.code,
        )
    rows = result.data if isinstance(result.data, list) else []
    parsed_rows: list[FacebookPageAPIData] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        page_id = str(row.get("id") or "").strip()
        name = str(row.get("name") or "").strip()
        if not page_id or not name:
            continue
        tasks = row.get("tasks")
        perms = row.get("perms")
        parsed_rows.append(
            FacebookPageAPIData(
                id=page_id,
                name=name,
                tasks=[str(v).strip() for v in tasks if str(v).strip()]
                if isinstance(tasks, list)
                else [],
                perms=[str(v).strip() for v in perms if str(v).strip()]
                if isinstance(perms, list)
                else [],
            )
        )
    return FacebookPagesListAPIOutput(
        success=True,
        data=parsed_rows,
        error=None,
        code=None,
    )


@social_publish_router.post(
    "/publish",
    response_model=SocialPublishAPIOutput,
    status_code=status.HTTP_200_OK,
    summary="Publish social post to LinkedIn or Facebook",
)
async def publish_social_post(
    input: SocialPublishAPIInput,
    current_user_result: AuthServiceOutput = Depends(get_current_user),
) -> SocialPublishAPIOutput | JSONResponse:
    user, error_response = _extract_user(current_user_result)
    if error_response:
        return error_response
    assert user is not None
    user_id = str(user.id or "").strip()
    if not user_id:
        return _json_response(
            SocialPublishAPIOutput(
                success=False,
                data=None,
                error="Unexpected auth payload.",
                code="SOCIAL_INVALID_USER",
            ),
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            partial(
                _publish_service.publish,
                SocialPublishInput(
                    user_id=user_id,
                    platform=input.platform,
                    content=input.content,
                    page_id=input.page_id,
                ),
            ),
        )
    except asyncio.CancelledError:
        logger.warning("Social publish request cancelled.", user_id=user.id)
        raise
    except Exception as exc:
        logger.exception(
            "Unhandled exception while publishing social post.", error=str(exc)
        )
        return _json_response(
            SocialPublishAPIOutput(
                success=False,
                data=None,
                error="Unexpected error while publishing post.",
                code="SOCIAL_UNEXPECTED_ERROR",
            ),
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    if not result.status or not isinstance(result.data, dict):
        return _json_response(
            SocialPublishAPIOutput(
                success=False,
                data=None,
                error=to_user_error_message(
                    error=result.error,
                    status_code=result.code,
                    fallback="Failed to publish post.",
                ),
                code=result.error_code,
            ),
            result.code,
        )

    data = result.data
    platform = str(data.get("platform") or "").strip()
    provider_post_id = str(data.get("provider_post_id") or "").strip()
    view_url = str(data.get("view_url") or "").strip()
    if not platform or not provider_post_id or not view_url:
        return _json_response(
            SocialPublishAPIOutput(
                success=False,
                data=None,
                error="Unexpected publish response payload.",
                code="SOCIAL_PROVIDER_ERROR",
            ),
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    return SocialPublishAPIOutput(
        success=True,
        data=SocialPublishAPIData(
            platform=platform,
            provider_post_id=provider_post_id,
            view_url=view_url,
        ),
        error=None,
        code=None,
    )
