from __future__ import annotations

import asyncio
from functools import partial
from typing import Any

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from api.dependencies import get_current_user
from api.models.content import ContentPlanAPIInput
from api.models.content import ContentPlanAPIData, ContentPlanAPIOutput
from app.services import (
    AuthServiceOutput,
    ConversationService,
    PersistContentPlanSnapshotInput,
)
from app.workflows.content_pipeline import ContentPlanningInput, ContentPlanningService
from domain.models.models import ContentPlanOutput
from infra.database.pg.schemas import User
from shared.logging import get_logger
from shared.logging import redact_message
from shared.thread_pools import get_crew_executor

logger = get_logger(__name__)

content_plan_router = APIRouter(prefix="/content-plan", tags=["Content Planning"])

_service = ContentPlanningService()
_conversation_service = ConversationService()


def _json_response(payload: Any, status_code: int) -> JSONResponse:
    return JSONResponse(
        status_code=status_code, content=payload.model_dump(mode="json")
    )


@content_plan_router.post(
    "",
    response_model=ContentPlanAPIOutput,
    status_code=status.HTTP_200_OK,
    summary="Generate a multi-platform content plan from a blog URL",
)
async def create_content_plan(
    input: ContentPlanAPIInput,
    current_user_result: AuthServiceOutput = Depends(get_current_user),
) -> ContentPlanAPIOutput | JSONResponse:
    if not current_user_result.status:
        return _json_response(
            ContentPlanAPIOutput(
                success=False,
                data=None,
                error=redact_message(current_user_result.error or "Unauthorized."),
            ),
            current_user_result.code,
        )

    if not isinstance(current_user_result.data, User):
        return _json_response(
            ContentPlanAPIOutput(
                success=False, data=None, error="Unexpected auth payload."
            ),
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    logger.info(
        "Received content-plan request.",
        url=str(input.url),
        selected_model=input.selected_model,
    )

    try:
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            get_crew_executor(),
            partial(
                _service.process,
                ContentPlanningInput(
                    url=str(input.url),
                    additional_context=input.additional_context,
                    selected_model=input.selected_model,
                    requester_user_id=current_user_result.data.id,
                ),
            ),
        )
    except asyncio.CancelledError:
        logger.warning("Content-plan request was cancelled by the client.")
        raise
    except Exception:
        logger.exception("Unhandled exception while running content planning pipeline.")
        return _json_response(
            ContentPlanAPIOutput(
                success=False,
                data=None,
                error="Unexpected error while generating content plan. Please try again later.",
            ),
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    if not result.status or not isinstance(result.data, ContentPlanOutput):
        logger.error("Pipeline failed", error=redact_message(result.error or ""))
        return _json_response(
            ContentPlanAPIOutput(
                success=False,
                data=None,
                error=result.error
                or "Pipeline failed without a specific error message.",
            ),
            result.code,
        )

    if input.project_id and input.conversation_id:
        persist_result = await loop.run_in_executor(
            None,
            partial(
                _conversation_service.persist_content_plan_snapshot,
                PersistContentPlanSnapshotInput(
                    owner_user_id=current_user_result.data.id or "",
                    project_id=input.project_id,
                    conversation_id=input.conversation_id,
                    source_url=str(input.url),
                    selected_model=input.selected_model,
                    additional_context=input.additional_context,
                    content_plan_snapshot=result.data.model_dump(mode="json"),
                ),
            ),
        )
        if not persist_result.status:
            return _json_response(
                ContentPlanAPIOutput(
                    success=False,
                    data=None,
                    error=persist_result.error
                    or "Generated content but failed to persist snapshot.",
                ),
                persist_result.code,
            )

    return _json_response(
        ContentPlanAPIOutput(
            success=True,
            data=ContentPlanAPIData.from_domain(result.data),
            error=None,
        ),
        status.HTTP_200_OK,
    )
