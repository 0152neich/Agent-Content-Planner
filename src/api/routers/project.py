from __future__ import annotations

import asyncio
from functools import partial

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse

from api.dependencies import get_current_user
from api.helpers.exception_handler import to_user_error_message
from api.models.project import (
    ProjectAPIData,
    ProjectAPIOutput,
    ProjectCreateAPIInput,
    ProjectDeleteAPIData,
    ProjectDeleteAPIOutput,
    ProjectListAPIData,
    ProjectListAPIOutput,
    ProjectUpdateAPIInput,
)
from app.services import (
    AuthServiceOutput,
    CreateProjectInput,
    DeleteProjectInput,
    GetProjectInput,
    ListProjectsInput,
    ProjectService,
    UpdateProjectInput,
)
from infra.database.pg.schemas import Project, User
from shared.logging import get_logger

logger = get_logger(__name__)

project_router = APIRouter(prefix="/projects", tags=["Projects"])

_service = ProjectService()


def _json_response(
    payload: ProjectAPIOutput | ProjectListAPIOutput | ProjectDeleteAPIOutput,
    status_code: int,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code, content=payload.model_dump(mode="json")
    )


def _extract_user(
    auth_result: AuthServiceOutput,
) -> tuple[User | None, JSONResponse | None]:
    if not auth_result.status:
        return None, _json_response(
            ProjectAPIOutput(
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
            ProjectAPIOutput(
                success=False, data=None, error="Unexpected auth payload."
            ),
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    return auth_result.data, None


@project_router.get(
    "",
    response_model=ProjectListAPIOutput,
    status_code=status.HTTP_200_OK,
    summary="Get projects of current user",
)
async def get_projects(
    limit: int | None = Query(20, ge=1, le=200),
    current_user_result: AuthServiceOutput = Depends(get_current_user),
) -> ProjectListAPIOutput | JSONResponse:
    user, error_response = _extract_user(current_user_result)
    if error_response:
        return error_response
    assert user is not None

    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            partial(
                _service.list_projects,
                ListProjectsInput(owner_user_id=user.id or "", limit=limit or 20),
            ),
        )
    except asyncio.CancelledError:
        logger.warning("Get projects request cancelled by client.", user_id=user.id)
        raise
    except Exception as exc:
        logger.exception(
            "Unhandled exception while getting projects.",
            error=str(exc),
            user_id=user.id,
        )
        return _json_response(
            ProjectListAPIOutput(
                success=False,
                data=None,
                error="Unexpected error while getting projects.",
            ),
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    if not result.status:
        return _json_response(
            ProjectListAPIOutput(
                success=False,
                data=None,
                error=to_user_error_message(
                    error=result.error,
                    status_code=result.code,
                    fallback="Get projects failed.",
                ),
            ),
            result.code,
        )
    projects = result.data if isinstance(result.data, list) else []
    return ProjectListAPIOutput(
        success=True, data=ProjectListAPIData.from_domain(projects), error=None
    )


@project_router.post(
    "",
    response_model=ProjectAPIOutput,
    status_code=status.HTTP_201_CREATED,
    summary="Create a project",
)
async def create_project(
    input: ProjectCreateAPIInput,
    current_user_result: AuthServiceOutput = Depends(get_current_user),
) -> ProjectAPIOutput | JSONResponse:
    user, error_response = _extract_user(current_user_result)
    if error_response:
        return error_response
    assert user is not None

    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            partial(
                _service.create_project,
                CreateProjectInput(
                    owner_user_id=user.id or "",
                    name=input.name,
                    source_url=str(input.source_url) if input.source_url else None,
                    description=input.description,
                    status=input.status,
                ),
            ),
        )
    except asyncio.CancelledError:
        logger.warning("Create project request cancelled by client.", user_id=user.id)
        raise
    except Exception as exc:
        logger.exception(
            "Unhandled exception while creating project.",
            error=str(exc),
            user_id=user.id,
        )
        return _json_response(
            ProjectAPIOutput(
                success=False,
                data=None,
                error="Unexpected error while creating project.",
            ),
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    if not result.status or not isinstance(result.data, Project):
        return _json_response(
            ProjectAPIOutput(
                success=False,
                data=None,
                error=to_user_error_message(
                    error=result.error,
                    status_code=result.code,
                    fallback="Create project failed.",
                ),
            ),
            result.code,
        )
    return ProjectAPIOutput(
        success=True, data=ProjectAPIData.from_domain(result.data), error=None
    )


@project_router.get(
    "/{project_id}",
    response_model=ProjectAPIOutput,
    status_code=status.HTTP_200_OK,
    summary="Get a project detail",
)
async def get_project(
    project_id: str,
    current_user_result: AuthServiceOutput = Depends(get_current_user),
) -> ProjectAPIOutput | JSONResponse:
    user, error_response = _extract_user(current_user_result)
    if error_response:
        return error_response
    assert user is not None

    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            partial(
                _service.get_project,
                GetProjectInput(owner_user_id=user.id or "", project_id=project_id),
            ),
        )
    except asyncio.CancelledError:
        logger.warning(
            "Get project request cancelled by client.",
            user_id=user.id,
            project_id=project_id,
        )
        raise
    except Exception as exc:
        logger.exception(
            "Unhandled exception while getting project.",
            error=str(exc),
            user_id=user.id,
            project_id=project_id,
        )
        return _json_response(
            ProjectAPIOutput(
                success=False,
                data=None,
                error="Unexpected error while getting project.",
            ),
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    if not result.status or not isinstance(result.data, Project):
        return _json_response(
            ProjectAPIOutput(
                success=False,
                data=None,
                error=to_user_error_message(
                    error=result.error,
                    status_code=result.code,
                    fallback="Get project failed.",
                ),
            ),
            result.code,
        )
    return ProjectAPIOutput(
        success=True, data=ProjectAPIData.from_domain(result.data), error=None
    )


@project_router.put(
    "/{project_id}",
    response_model=ProjectAPIOutput,
    status_code=status.HTTP_200_OK,
    summary="Update a project",
)
async def update_project(
    project_id: str,
    input: ProjectUpdateAPIInput,
    current_user_result: AuthServiceOutput = Depends(get_current_user),
) -> ProjectAPIOutput | JSONResponse:
    user, error_response = _extract_user(current_user_result)
    if error_response:
        return error_response
    assert user is not None

    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            partial(
                _service.update_project,
                UpdateProjectInput(
                    owner_user_id=user.id or "",
                    project_id=project_id,
                    name=input.name,
                    source_url=str(input.source_url)
                    if input.source_url is not None
                    else None,
                    description=input.description,
                    status=input.status,
                ),
            ),
        )
    except asyncio.CancelledError:
        logger.warning(
            "Update project request cancelled by client.",
            user_id=user.id,
            project_id=project_id,
        )
        raise
    except Exception as exc:
        logger.exception(
            "Unhandled exception while updating project.",
            error=str(exc),
            user_id=user.id,
            project_id=project_id,
        )
        return _json_response(
            ProjectAPIOutput(
                success=False,
                data=None,
                error="Unexpected error while updating project.",
            ),
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    if not result.status or not isinstance(result.data, Project):
        return _json_response(
            ProjectAPIOutput(
                success=False,
                data=None,
                error=to_user_error_message(
                    error=result.error,
                    status_code=result.code,
                    fallback="Update project failed.",
                ),
            ),
            result.code,
        )
    return ProjectAPIOutput(
        success=True, data=ProjectAPIData.from_domain(result.data), error=None
    )


@project_router.delete(
    "/{project_id}",
    response_model=ProjectDeleteAPIOutput,
    status_code=status.HTTP_200_OK,
    summary="Delete a project",
)
async def delete_project(
    project_id: str,
    current_user_result: AuthServiceOutput = Depends(get_current_user),
) -> ProjectDeleteAPIOutput | JSONResponse:
    user, error_response = _extract_user(current_user_result)
    if error_response:
        return error_response
    assert user is not None

    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            partial(
                _service.delete_project,
                DeleteProjectInput(owner_user_id=user.id or "", project_id=project_id),
            ),
        )
    except asyncio.CancelledError:
        logger.warning(
            "Delete project request cancelled by client.",
            user_id=user.id,
            project_id=project_id,
        )
        raise
    except Exception as exc:
        logger.exception(
            "Unhandled exception while deleting project.",
            error=str(exc),
            user_id=user.id,
            project_id=project_id,
        )
        return _json_response(
            ProjectDeleteAPIOutput(
                success=False,
                data=None,
                error="Unexpected error while deleting project.",
            ),
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    if not result.status:
        return _json_response(
            ProjectDeleteAPIOutput(
                success=False,
                data=None,
                error=to_user_error_message(
                    error=result.error,
                    status_code=result.code,
                    fallback="Delete project failed.",
                ),
            ),
            result.code,
        )
    return ProjectDeleteAPIOutput(
        success=True,
        data=ProjectDeleteAPIData(id=project_id, deleted=True),
        error=None,
    )
