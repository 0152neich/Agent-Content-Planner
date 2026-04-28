from __future__ import annotations

import asyncio
from functools import partial

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse

from api.dependencies import get_current_user
from api.helpers.exception_handler import to_user_error_message
from api.models.autopost import (
    AutopostCalendarAPIData,
    AutopostCalendarAPIOutput,
    AutopostJobActionAPIData,
    AutopostJobActionAPIOutput,
    AutopostJobAPIData,
    AutopostJobAPIOutput,
    AutopostJobCreateAPIData,
    AutopostJobCreateAPIInput,
    AutopostJobCreateAPIOutput,
    AutopostJobListAPIData,
    AutopostJobListAPIOutput,
)
from app.services import (
    AuthServiceOutput,
    AutopostService,
    CancelAutopostJobInput,
    CreateAutopostJobInput,
    GetAutopostJobInput,
    ListAutopostCalendarInput,
    ListAutopostJobsInput,
    RetryAutopostJobInput,
)
from infra.database.pg.schemas import AutopostJob, User
from shared.logging import get_logger

logger = get_logger(__name__)

autopost_router = APIRouter(prefix="/autopost", tags=["AutoPost"])
_service = AutopostService()


def _json_response(payload, status_code: int) -> JSONResponse:
    return JSONResponse(
        status_code=status_code, content=payload.model_dump(mode="json")
    )


def _extract_user(
    auth_result: AuthServiceOutput,
) -> tuple[User | None, JSONResponse | None]:
    if not auth_result.status:
        return None, _json_response(
            AutopostJobAPIOutput(
                success=False,
                data=None,
                error=to_user_error_message(
                    error=auth_result.error,
                    status_code=auth_result.code,
                    fallback="Unauthorized.",
                ),
            ),
            auth_result.code,
        )
    if not isinstance(auth_result.data, User):
        return None, _json_response(
            AutopostJobAPIOutput(
                success=False, data=None, error="Unexpected auth payload."
            ),
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    return auth_result.data, None


@autopost_router.post(
    "/jobs",
    response_model=AutopostJobCreateAPIOutput,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Create one auto-post job",
)
async def create_job(
    input: AutopostJobCreateAPIInput,
    current_user_result: AuthServiceOutput = Depends(get_current_user),
) -> AutopostJobCreateAPIOutput | JSONResponse:
    user, error_response = _extract_user(current_user_result)
    if error_response:
        return error_response
    assert user is not None
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            partial(
                _service.create_job,
                CreateAutopostJobInput(
                    user_id=user.id or "",
                    project_id=input.project_id,
                    platform=input.platform,
                    keyword=input.keyword,
                    scheduled_at=input.scheduled_at,
                    publish_mode=input.publish_mode,
                    page_id=input.page_id,
                ),
            ),
        )
    except Exception as exc:
        logger.exception("autopost_create_job_unhandled", error=str(exc))
        return _json_response(
            AutopostJobCreateAPIOutput(
                success=False,
                data=None,
                error="Unexpected error while creating job.",
            ),
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    if not result.status:
        return _json_response(
            AutopostJobCreateAPIOutput(
                success=False,
                data=None,
                error=to_user_error_message(
                    error=result.error,
                    status_code=result.code,
                    fallback="Create auto-post job failed.",
                ),
            ),
            result.code,
        )
    payload = result.data if isinstance(result.data, dict) else {}
    return _json_response(
        AutopostJobCreateAPIOutput(
            success=True,
            data=AutopostJobCreateAPIData(
                id=str(payload.get("id") or ""),
                status=str(payload.get("status") or "QUEUED"),
            ),
            error=None,
        ),
        result.code,
    )


@autopost_router.get(
    "/jobs",
    response_model=AutopostJobListAPIOutput,
    status_code=status.HTTP_200_OK,
    summary="List auto-post jobs by project",
)
async def list_jobs(
    project_id: str = Query(..., min_length=1),
    status_filter: str | None = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    current_user_result: AuthServiceOutput = Depends(get_current_user),
) -> AutopostJobListAPIOutput | JSONResponse:
    user, error_response = _extract_user(current_user_result)
    if error_response:
        return error_response
    assert user is not None
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            partial(
                _service.list_jobs,
                ListAutopostJobsInput(
                    user_id=user.id or "",
                    project_id=project_id,
                    status=status_filter,
                    limit=limit,
                ),
            ),
        )
    except Exception as exc:
        logger.exception("autopost_list_jobs_unhandled", error=str(exc))
        return _json_response(
            AutopostJobListAPIOutput(
                success=False, data=None, error="Unexpected error while listing jobs."
            ),
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    if not result.status:
        return _json_response(
            AutopostJobListAPIOutput(
                success=False,
                data=None,
                error=to_user_error_message(
                    error=result.error,
                    status_code=result.code,
                    fallback="List auto-post jobs failed.",
                ),
            ),
            result.code,
        )
    jobs = result.data if isinstance(result.data, list) else []
    return AutopostJobListAPIOutput(
        success=True, data=AutopostJobListAPIData.from_domain(jobs), error=None
    )


@autopost_router.get(
    "/jobs/{job_id}",
    response_model=AutopostJobAPIOutput,
    status_code=status.HTTP_200_OK,
    summary="Get auto-post job detail",
)
async def get_job(
    job_id: str,
    current_user_result: AuthServiceOutput = Depends(get_current_user),
) -> AutopostJobAPIOutput | JSONResponse:
    user, error_response = _extract_user(current_user_result)
    if error_response:
        return error_response
    assert user is not None
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            partial(
                _service.get_job,
                GetAutopostJobInput(
                    user_id=user.id or "",
                    job_id=job_id,
                ),
            ),
        )
    except Exception as exc:
        logger.exception("autopost_get_job_unhandled", error=str(exc))
        return _json_response(
            AutopostJobAPIOutput(
                success=False, data=None, error="Unexpected error while getting job."
            ),
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    if not result.status or not isinstance(result.data, AutopostJob):
        return _json_response(
            AutopostJobAPIOutput(
                success=False,
                data=None,
                error=to_user_error_message(
                    error=result.error,
                    status_code=result.code,
                    fallback="Get auto-post job failed.",
                ),
            ),
            result.code,
        )
    return AutopostJobAPIOutput(
        success=True,
        data=AutopostJobAPIData.from_domain(result.data),
        error=None,
    )


@autopost_router.post(
    "/jobs/{job_id}/cancel",
    response_model=AutopostJobActionAPIOutput,
    status_code=status.HTTP_200_OK,
    summary="Cancel auto-post job",
)
async def cancel_job(
    job_id: str,
    current_user_result: AuthServiceOutput = Depends(get_current_user),
) -> AutopostJobActionAPIOutput | JSONResponse:
    user, error_response = _extract_user(current_user_result)
    if error_response:
        return error_response
    assert user is not None
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            partial(
                _service.cancel_job,
                CancelAutopostJobInput(user_id=user.id or "", job_id=job_id),
            ),
        )
    except Exception as exc:
        logger.exception("autopost_cancel_job_unhandled", error=str(exc))
        return _json_response(
            AutopostJobActionAPIOutput(
                success=False, data=None, error="Unexpected error while cancelling job."
            ),
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    if not result.status:
        return _json_response(
            AutopostJobActionAPIOutput(
                success=False,
                data=None,
                error=to_user_error_message(
                    error=result.error,
                    status_code=result.code,
                    fallback="Cancel auto-post job failed.",
                ),
            ),
            result.code,
        )
    payload = result.data if isinstance(result.data, dict) else {}
    return AutopostJobActionAPIOutput(
        success=True,
        data=AutopostJobActionAPIData(
            id=str(payload.get("id") or job_id),
            status=str(payload.get("status") or ""),
        ),
        error=None,
    )


@autopost_router.post(
    "/jobs/{job_id}/retry",
    response_model=AutopostJobActionAPIOutput,
    status_code=status.HTTP_200_OK,
    summary="Retry failed auto-post job",
)
async def retry_job(
    job_id: str,
    current_user_result: AuthServiceOutput = Depends(get_current_user),
) -> AutopostJobActionAPIOutput | JSONResponse:
    user, error_response = _extract_user(current_user_result)
    if error_response:
        return error_response
    assert user is not None
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            partial(
                _service.retry_job,
                RetryAutopostJobInput(user_id=user.id or "", job_id=job_id),
            ),
        )
    except Exception as exc:
        logger.exception("autopost_retry_job_unhandled", error=str(exc))
        return _json_response(
            AutopostJobActionAPIOutput(
                success=False, data=None, error="Unexpected error while retrying job."
            ),
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    if not result.status:
        return _json_response(
            AutopostJobActionAPIOutput(
                success=False,
                data=None,
                error=to_user_error_message(
                    error=result.error,
                    status_code=result.code,
                    fallback="Retry auto-post job failed.",
                ),
            ),
            result.code,
        )
    payload = result.data if isinstance(result.data, dict) else {}
    return AutopostJobActionAPIOutput(
        success=True,
        data=AutopostJobActionAPIData(
            id=str(payload.get("id") or job_id),
            status=str(payload.get("status") or ""),
        ),
        error=None,
    )


@autopost_router.get(
    "/calendar",
    response_model=AutopostCalendarAPIOutput,
    status_code=status.HTTP_200_OK,
    summary="List auto-post timeline calendar items",
)
async def get_calendar(
    project_id: str = Query(..., min_length=1),
    status_filter: str | None = Query(None, alias="status"),
    limit: int = Query(200, ge=1, le=500),
    current_user_result: AuthServiceOutput = Depends(get_current_user),
) -> AutopostCalendarAPIOutput | JSONResponse:
    user, error_response = _extract_user(current_user_result)
    if error_response:
        return error_response
    assert user is not None
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            partial(
                _service.list_calendar,
                ListAutopostCalendarInput(
                    user_id=user.id or "",
                    project_id=project_id,
                    status=status_filter,
                    limit=limit,
                ),
            ),
        )
    except Exception as exc:
        logger.exception("autopost_calendar_unhandled", error=str(exc))
        return _json_response(
            AutopostCalendarAPIOutput(
                success=False,
                data=None,
                error="Unexpected error while loading calendar.",
            ),
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    if not result.status:
        return _json_response(
            AutopostCalendarAPIOutput(
                success=False,
                data=None,
                error=to_user_error_message(
                    error=result.error,
                    status_code=result.code,
                    fallback="Get auto-post calendar failed.",
                ),
            ),
            result.code,
        )
    jobs = result.data if isinstance(result.data, list) else []
    return AutopostCalendarAPIOutput(
        success=True, data=AutopostCalendarAPIData.from_domain(jobs), error=None
    )
