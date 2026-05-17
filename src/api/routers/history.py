from __future__ import annotations

import asyncio
from functools import partial

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse

from api.dependencies import get_current_user
from api.helpers.exception_handler import to_user_error_message
from api.models.conversation import (
    ConversationRunAPIData,
    ConversationRunAPIOutput,
    ProjectHistoryListAPIData,
    ProjectHistoryListAPIOutput,
    RunSnapshotRestoreAPIData,
    RunSnapshotRestoreAPIInput,
    RunSnapshotRestoreAPIOutput,
    RunSnapshotSaveAPIData,
    RunSnapshotSaveAPIInput,
    RunSnapshotSaveAPIOutput,
)
from app.services import (
    AuthServiceOutput,
    ConversationService,
    GetRunInput,
    ListProjectHistoryInput,
    RestoreRunSnapshotInput,
    SaveRunSnapshotInput,
)
from infra.database.pg.schemas import ConversationRun, User
from shared.logging import get_logger

logger = get_logger(__name__)

history_router = APIRouter(tags=["History"])

_service = ConversationService()


def _json_response(payload, status_code: int) -> JSONResponse:
    return JSONResponse(
        status_code=status_code, content=payload.model_dump(mode="json")
    )


def _auth_error_response(auth_result: AuthServiceOutput) -> JSONResponse | None:
    if not auth_result.status:
        return JSONResponse(
            status_code=auth_result.code,
            content={
                "success": False,
                "data": None,
                "error": to_user_error_message(
                    error=auth_result.error,
                    status_code=auth_result.code,
                    fallback="Unauthorized.",
                ),
            },
        )
    if not isinstance(auth_result.data, User):
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "data": None,
                "error": "Unexpected auth payload.",
            },
        )
    return None


def _extract_user(
    auth_result: AuthServiceOutput,
) -> tuple[User | None, JSONResponse | None]:
    error_response = _auth_error_response(auth_result)
    if error_response:
        return None, error_response
    return auth_result.data, None


@history_router.get(
    "/projects/{project_id}/history",
    response_model=ProjectHistoryListAPIOutput,
    status_code=status.HTTP_200_OK,
    summary="List project history from conversation runs",
)
async def list_project_history(
    project_id: str,
    status_filter: str | None = Query(None, alias="status"),
    cursor: str | None = Query(None),
    limit: int | None = Query(20, ge=1, le=200),
    current_user_result: AuthServiceOutput = Depends(get_current_user),
) -> ProjectHistoryListAPIOutput | JSONResponse:
    user, error_response = _extract_user(current_user_result)
    if error_response:
        return error_response
    assert user is not None
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            partial(
                _service.list_project_history,
                ListProjectHistoryInput(
                    owner_user_id=user.id or "",
                    project_id=project_id,
                    status=status_filter,
                    cursor=cursor,
                    limit=limit or 20,
                ),
            ),
        )
    except asyncio.CancelledError:
        logger.warning(
            "List history request cancelled.", user_id=user.id, project_id=project_id
        )
        raise
    except Exception as exc:
        logger.exception(
            "Unhandled exception while listing history.",
            error=str(exc),
            project_id=project_id,
        )
        return _json_response(
            ProjectHistoryListAPIOutput(
                success=False,
                data=None,
                error="Unexpected error while listing history.",
            ),
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    if not result.status:
        return _json_response(
            ProjectHistoryListAPIOutput(
                success=False,
                data=None,
                error=to_user_error_message(
                    error=result.error,
                    status_code=result.code,
                    fallback="List history failed.",
                ),
            ),
            result.code,
        )

    payload = result.data if isinstance(result.data, dict) else {}
    runs = payload.get("runs", [])
    next_cursor = payload.get("next_cursor")
    return ProjectHistoryListAPIOutput(
        success=True,
        data=ProjectHistoryListAPIData.from_domain(runs, next_cursor),
        error=None,
    )


@history_router.get(
    "/runs/{run_id}",
    response_model=ConversationRunAPIOutput,
    status_code=status.HTTP_200_OK,
    summary="Get run detail",
)
async def get_run(
    run_id: str,
    current_user_result: AuthServiceOutput = Depends(get_current_user),
) -> ConversationRunAPIOutput | JSONResponse:
    user, error_response = _extract_user(current_user_result)
    if error_response:
        return error_response
    assert user is not None
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            partial(
                _service.get_run,
                GetRunInput(owner_user_id=user.id or "", run_id=run_id),
            ),
        )
    except asyncio.CancelledError:
        logger.warning("Get run request cancelled.", user_id=user.id, run_id=run_id)
        raise
    except Exception as exc:
        logger.exception(
            "Unhandled exception while getting run.", error=str(exc), run_id=run_id
        )
        return _json_response(
            ConversationRunAPIOutput(
                success=False, data=None, error="Unexpected error while getting run."
            ),
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    if not result.status or not isinstance(result.data, ConversationRun):
        return _json_response(
            ConversationRunAPIOutput(
                success=False,
                data=None,
                error=to_user_error_message(
                    error=result.error,
                    status_code=result.code,
                    fallback="Get run failed.",
                ),
            ),
            result.code,
        )

    return ConversationRunAPIOutput(
        success=True, data=ConversationRunAPIData.from_domain(result.data), error=None
    )


@history_router.put(
    "/runs/{run_id}/snapshot",
    response_model=RunSnapshotSaveAPIOutput,
    status_code=status.HTTP_200_OK,
    summary="Save structured content snapshot to run payload",
)
async def save_run_snapshot(
    run_id: str,
    input: RunSnapshotSaveAPIInput,
    current_user_result: AuthServiceOutput = Depends(get_current_user),
) -> RunSnapshotSaveAPIOutput | JSONResponse:
    user, error_response = _extract_user(current_user_result)
    if error_response:
        return error_response
    assert user is not None
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            partial(
                _service.save_run_snapshot,
                SaveRunSnapshotInput(
                    owner_user_id=user.id or "",
                    run_id=run_id,
                    content_plan_snapshot=input.content_plan_snapshot,
                ),
            ),
        )
    except asyncio.CancelledError:
        logger.warning(
            "Save run snapshot request cancelled.", user_id=user.id, run_id=run_id
        )
        raise
    except Exception as exc:
        logger.exception(
            "Unhandled exception while saving run snapshot.",
            error=str(exc),
            run_id=run_id,
        )
        return _json_response(
            RunSnapshotSaveAPIOutput(
                success=False,
                data=None,
                error="Unexpected error while saving run snapshot.",
            ),
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    if not result.status:
        return _json_response(
            RunSnapshotSaveAPIOutput(
                success=False,
                data=None,
                error=to_user_error_message(
                    error=result.error,
                    status_code=result.code,
                    fallback="Save run snapshot failed.",
                ),
            ),
            result.code,
        )

    return RunSnapshotSaveAPIOutput(
        success=True,
        data=RunSnapshotSaveAPIData(id=run_id, saved=True),
        error=None,
    )


@history_router.post(
    "/runs/{run_id}/restore",
    response_model=RunSnapshotRestoreAPIOutput,
    status_code=status.HTTP_201_CREATED,
    summary="Restore full content snapshot from a historical run",
)
async def restore_run_snapshot(
    run_id: str,
    input: RunSnapshotRestoreAPIInput,
    current_user_result: AuthServiceOutput = Depends(get_current_user),
) -> RunSnapshotRestoreAPIOutput | JSONResponse:
    user, error_response = _extract_user(current_user_result)
    if error_response:
        return error_response
    assert user is not None
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            partial(
                _service.restore_run_snapshot,
                RestoreRunSnapshotInput(
                    owner_user_id=user.id or "",
                    run_id=run_id,
                    target=input.target,
                ),
            ),
        )
    except asyncio.CancelledError:
        logger.warning(
            "Restore run snapshot request cancelled.", user_id=user.id, run_id=run_id
        )
        raise
    except Exception as exc:
        logger.exception(
            "Unhandled exception while restoring run snapshot.",
            error=str(exc),
            run_id=run_id,
        )
        return _json_response(
            RunSnapshotRestoreAPIOutput(
                success=False,
                data=None,
                error="Unexpected error while restoring run snapshot.",
            ),
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    payload = result.data if isinstance(result.data, dict) else {}
    restored_run = payload.get("restored_run")
    content_plan_snapshot = payload.get("content_plan_snapshot")
    if (
        not result.status
        or not isinstance(restored_run, ConversationRun)
        or not isinstance(content_plan_snapshot, dict)
    ):
        return _json_response(
            RunSnapshotRestoreAPIOutput(
                success=False,
                data=None,
                error=to_user_error_message(
                    error=result.error,
                    status_code=result.code,
                    fallback="Restore run snapshot failed.",
                ),
            ),
            result.code,
        )

    return _json_response(
        RunSnapshotRestoreAPIOutput(
            success=True,
            data=RunSnapshotRestoreAPIData.from_domain(
                restored_run=restored_run,
                content_plan_snapshot=content_plan_snapshot,
            ),
            error=None,
        ),
        status.HTTP_201_CREATED,
    )
