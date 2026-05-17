from __future__ import annotations

import asyncio
import json
import re
from functools import partial
from typing import Any, AsyncIterator

from fastapi import APIRouter, Depends, Query, Response, status
from fastapi.responses import JSONResponse, StreamingResponse

from api.dependencies import get_current_user
from api.helpers.exception_handler import to_user_error_message
from api.models.conversation import (
    ConversationAPIData,
    ConversationAPIOutput,
    ConversationCreateAPIInput,
    ConversationDeleteAPIData,
    ConversationDeleteAPIOutput,
    ConversationListAPIData,
    ConversationListAPIOutput,
    ConversationMessageCreateAPIData,
    ConversationMessageCreateAPIInput,
    ConversationMessageCreateAPIOutput,
    ConversationMessageListAPIData,
    ConversationMessageListAPIOutput,
    ConversationUpdateAPIInput,
)
from app.services import (
    AuthServiceOutput,
    ConversationService,
    CreateConversationInput,
    CreateConversationMessageInput,
    DeleteConversationInput,
    GetConversationInput,
    ListConversationMessagesInput,
    ListProjectConversationsInput,
    UpdateConversationInput,
)
from infra.database.pg.schemas import (
    Conversation,
    ConversationMessage,
    ConversationRun,
    User,
)
from shared.logging import get_logger
from shared.thread_pools import get_crew_executor

logger = get_logger(__name__)

conversation_router = APIRouter(tags=["Conversations"])

_service = ConversationService()


def _json_response(payload, status_code: int) -> JSONResponse:
    return JSONResponse(
        status_code=status_code, content=payload.model_dump(mode="json")
    )


def _extract_user(
    auth_result: AuthServiceOutput,
) -> tuple[User | None, JSONResponse | None]:
    if not auth_result.status:
        return None, _json_response(
            ConversationAPIOutput(
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
            ConversationAPIOutput(
                success=False, data=None, error="Unexpected auth payload."
            ),
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    return auth_result.data, None


def _build_message_create_api_data(
    result_data: dict[str, Any],
) -> tuple[ConversationMessageCreateAPIData | None, JSONResponse | None]:
    user_message = result_data.get("user_message")
    assistant_message = result_data.get("assistant_message")
    run = result_data.get("run")
    intent = result_data.get("intent")
    affected_sections = result_data.get("affected_sections")
    content_plan_snapshot = result_data.get("content_plan_snapshot")

    if not isinstance(run, ConversationRun):
        return None, _json_response(
            ConversationMessageCreateAPIOutput(
                success=False, data=None, error="Unexpected run payload."
            ),
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    if user_message is not None and not isinstance(user_message, ConversationMessage):
        return None, _json_response(
            ConversationMessageCreateAPIOutput(
                success=False, data=None, error="Unexpected user message payload."
            ),
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    if assistant_message is not None and not isinstance(
        assistant_message, ConversationMessage
    ):
        return None, _json_response(
            ConversationMessageCreateAPIOutput(
                success=False, data=None, error="Unexpected assistant message payload."
            ),
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    return (
        ConversationMessageCreateAPIData.from_domain(
            user_message=user_message,
            assistant_message=assistant_message,
            run=run,
            intent=intent if isinstance(intent, dict) else None,
            affected_sections=(
                [str(section) for section in affected_sections]
                if isinstance(affected_sections, list)
                else None
            ),
            content_plan_snapshot=(
                content_plan_snapshot
                if isinstance(content_plan_snapshot, dict)
                else None
            ),
        ),
        None,
    )


def _to_sse(event: str, payload: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _chunk_text(value: str) -> list[str]:
    text = value or ""
    if not text:
        return []
    # Preserve standalone leading/newline spaces too, so streamed chunks do not
    # collapse words (for example when upstream emits " world" as a separate delta).
    return re.findall(r"\s+|\S+\s*", text)


@conversation_router.get(
    "/projects/{project_id}/conversations",
    response_model=ConversationListAPIOutput,
    status_code=status.HTTP_200_OK,
    summary="Get conversations by project",
)
async def list_project_conversations(
    project_id: str,
    limit: int | None = Query(20, ge=1, le=200),
    current_user_result: AuthServiceOutput = Depends(get_current_user),
) -> ConversationListAPIOutput | JSONResponse:
    user, error_response = _extract_user(current_user_result)
    if error_response:
        return error_response
    assert user is not None
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            partial(
                _service.list_project_conversations,
                ListProjectConversationsInput(
                    owner_user_id=user.id or "",
                    project_id=project_id,
                    limit=limit or 20,
                ),
            ),
        )
    except asyncio.CancelledError:
        logger.warning(
            "List conversations request cancelled.",
            user_id=user.id,
            project_id=project_id,
        )
        raise
    except Exception as exc:
        logger.exception(
            "Unhandled exception while listing conversations.",
            error=str(exc),
            project_id=project_id,
        )
        return _json_response(
            ConversationListAPIOutput(
                success=False,
                data=None,
                error="Unexpected error while listing conversations.",
            ),
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    if not result.status:
        return _json_response(
            ConversationListAPIOutput(
                success=False,
                data=None,
                error=to_user_error_message(
                    error=result.error,
                    status_code=result.code,
                    fallback="List conversations failed.",
                ),
            ),
            result.code,
        )
    conversations = result.data if isinstance(result.data, list) else []
    return ConversationListAPIOutput(
        success=True,
        data=ConversationListAPIData.from_domain(conversations),
        error=None,
    )


@conversation_router.post(
    "/projects/{project_id}/conversations",
    response_model=ConversationAPIOutput,
    status_code=status.HTTP_201_CREATED,
    summary="Create conversation in project",
)
async def create_conversation(
    project_id: str,
    input: ConversationCreateAPIInput,
    current_user_result: AuthServiceOutput = Depends(get_current_user),
) -> ConversationAPIOutput | JSONResponse:
    user, error_response = _extract_user(current_user_result)
    if error_response:
        return error_response
    assert user is not None
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            partial(
                _service.create_conversation,
                CreateConversationInput(
                    owner_user_id=user.id or "",
                    project_id=project_id,
                    title=input.title,
                    selected_model=input.selected_model,
                ),
            ),
        )
    except asyncio.CancelledError:
        logger.warning(
            "Create conversation request cancelled.",
            user_id=user.id,
            project_id=project_id,
        )
        raise
    except Exception as exc:
        logger.exception(
            "Unhandled exception while creating conversation.",
            error=str(exc),
            project_id=project_id,
        )
        return _json_response(
            ConversationAPIOutput(
                success=False,
                data=None,
                error="Unexpected error while creating conversation.",
            ),
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    if not result.status or not isinstance(result.data, Conversation):
        return _json_response(
            ConversationAPIOutput(
                success=False,
                data=None,
                error=to_user_error_message(
                    error=result.error,
                    status_code=result.code,
                    fallback="Create conversation failed.",
                ),
            ),
            result.code,
        )
    return ConversationAPIOutput(
        success=True, data=ConversationAPIData.from_domain(result.data), error=None
    )


@conversation_router.get(
    "/conversations/{conversation_id}",
    response_model=ConversationAPIOutput,
    status_code=status.HTTP_200_OK,
    summary="Get conversation detail",
)
async def get_conversation(
    conversation_id: str,
    current_user_result: AuthServiceOutput = Depends(get_current_user),
) -> ConversationAPIOutput | JSONResponse:
    user, error_response = _extract_user(current_user_result)
    if error_response:
        return error_response
    assert user is not None
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            partial(
                _service.get_conversation,
                GetConversationInput(
                    owner_user_id=user.id or "", conversation_id=conversation_id
                ),
            ),
        )
    except asyncio.CancelledError:
        logger.warning(
            "Get conversation request cancelled.",
            user_id=user.id,
            conversation_id=conversation_id,
        )
        raise
    except Exception as exc:
        logger.exception(
            "Unhandled exception while getting conversation.",
            error=str(exc),
            conversation_id=conversation_id,
        )
        return _json_response(
            ConversationAPIOutput(
                success=False,
                data=None,
                error="Unexpected error while getting conversation.",
            ),
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    if not result.status or not isinstance(result.data, Conversation):
        return _json_response(
            ConversationAPIOutput(
                success=False,
                data=None,
                error=to_user_error_message(
                    error=result.error,
                    status_code=result.code,
                    fallback="Get conversation failed.",
                ),
            ),
            result.code,
        )
    return ConversationAPIOutput(
        success=True, data=ConversationAPIData.from_domain(result.data), error=None
    )


@conversation_router.put(
    "/conversations/{conversation_id}",
    response_model=ConversationAPIOutput,
    status_code=status.HTTP_200_OK,
    summary="Update conversation",
)
async def update_conversation(
    conversation_id: str,
    input: ConversationUpdateAPIInput,
    current_user_result: AuthServiceOutput = Depends(get_current_user),
) -> ConversationAPIOutput | JSONResponse:
    user, error_response = _extract_user(current_user_result)
    if error_response:
        return error_response
    assert user is not None
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            partial(
                _service.update_conversation,
                UpdateConversationInput(
                    owner_user_id=user.id or "",
                    conversation_id=conversation_id,
                    title=input.title,
                    selected_model=input.selected_model,
                    status=input.status,
                ),
            ),
        )
    except asyncio.CancelledError:
        logger.warning(
            "Update conversation request cancelled.",
            user_id=user.id,
            conversation_id=conversation_id,
        )
        raise
    except Exception as exc:
        logger.exception(
            "Unhandled exception while updating conversation.",
            error=str(exc),
            conversation_id=conversation_id,
        )
        return _json_response(
            ConversationAPIOutput(
                success=False,
                data=None,
                error="Unexpected error while updating conversation.",
            ),
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    if not result.status or not isinstance(result.data, Conversation):
        return _json_response(
            ConversationAPIOutput(
                success=False,
                data=None,
                error=to_user_error_message(
                    error=result.error,
                    status_code=result.code,
                    fallback="Update conversation failed.",
                ),
            ),
            result.code,
        )
    return ConversationAPIOutput(
        success=True, data=ConversationAPIData.from_domain(result.data), error=None
    )


@conversation_router.delete(
    "/conversations/{conversation_id}",
    response_model=ConversationDeleteAPIOutput,
    status_code=status.HTTP_200_OK,
    summary="Delete conversation",
)
async def delete_conversation(
    conversation_id: str,
    current_user_result: AuthServiceOutput = Depends(get_current_user),
) -> ConversationDeleteAPIOutput | JSONResponse:
    user, error_response = _extract_user(current_user_result)
    if error_response:
        return error_response
    assert user is not None
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            partial(
                _service.delete_conversation,
                DeleteConversationInput(
                    owner_user_id=user.id or "", conversation_id=conversation_id
                ),
            ),
        )
    except asyncio.CancelledError:
        logger.warning(
            "Delete conversation request cancelled.",
            user_id=user.id,
            conversation_id=conversation_id,
        )
        raise
    except Exception as exc:
        logger.exception(
            "Unhandled exception while deleting conversation.",
            error=str(exc),
            conversation_id=conversation_id,
        )
        return _json_response(
            ConversationDeleteAPIOutput(
                success=False,
                data=None,
                error="Unexpected error while deleting conversation.",
            ),
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    if not result.status:
        return _json_response(
            ConversationDeleteAPIOutput(
                success=False,
                data=None,
                error=to_user_error_message(
                    error=result.error,
                    status_code=result.code,
                    fallback="Delete conversation failed.",
                ),
            ),
            result.code,
        )
    return ConversationDeleteAPIOutput(
        success=True,
        data=ConversationDeleteAPIData(id=conversation_id, deleted=True),
        error=None,
    )


@conversation_router.get(
    "/conversations/{conversation_id}/messages",
    response_model=ConversationMessageListAPIOutput,
    status_code=status.HTTP_200_OK,
    summary="List conversation messages with cursor",
)
async def list_conversation_messages(
    conversation_id: str,
    cursor: str | None = Query(None),
    limit: int | None = Query(30, ge=1, le=200),
    current_user_result: AuthServiceOutput = Depends(get_current_user),
) -> ConversationMessageListAPIOutput | JSONResponse:
    user, error_response = _extract_user(current_user_result)
    if error_response:
        return error_response
    assert user is not None
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            partial(
                _service.list_messages,
                ListConversationMessagesInput(
                    owner_user_id=user.id or "",
                    conversation_id=conversation_id,
                    cursor=cursor,
                    limit=limit or 30,
                ),
            ),
        )
    except asyncio.CancelledError:
        logger.warning(
            "List messages request cancelled.",
            user_id=user.id,
            conversation_id=conversation_id,
        )
        raise
    except Exception as exc:
        logger.exception(
            "Unhandled exception while listing messages.",
            error=str(exc),
            conversation_id=conversation_id,
        )
        return _json_response(
            ConversationMessageListAPIOutput(
                success=False,
                data=None,
                error="Unexpected error while listing messages.",
            ),
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    if not result.status:
        return _json_response(
            ConversationMessageListAPIOutput(
                success=False,
                data=None,
                error=to_user_error_message(
                    error=result.error,
                    status_code=result.code,
                    fallback="List messages failed.",
                ),
            ),
            result.code,
        )
    payload = result.data if isinstance(result.data, dict) else {}
    messages = payload.get("messages", [])
    next_cursor = payload.get("next_cursor")
    return ConversationMessageListAPIOutput(
        success=True,
        data=ConversationMessageListAPIData.from_domain(messages, next_cursor),
        error=None,
    )


@conversation_router.post(
    "/conversations/{conversation_id}/messages",
    response_model=ConversationMessageCreateAPIOutput,
    status_code=status.HTTP_201_CREATED,
    summary="Create user message and assistant response",
)
async def create_conversation_message(
    conversation_id: str,
    input: ConversationMessageCreateAPIInput,
    current_user_result: AuthServiceOutput = Depends(get_current_user),
) -> ConversationMessageCreateAPIOutput | JSONResponse:
    user, error_response = _extract_user(current_user_result)
    if error_response:
        return error_response
    assert user is not None
    try:
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            get_crew_executor(),
            partial(
                _service.create_message,
                CreateConversationMessageInput(
                    owner_user_id=user.id or "",
                    conversation_id=conversation_id,
                    content=input.content,
                    selected_model=input.selected_model,
                    source_url=str(input.source_url) if input.source_url else None,
                    platforms=input.platforms,
                    silent=input.silent,
                ),
            ),
        )
    except asyncio.CancelledError:
        logger.warning(
            "Create message request cancelled.",
            user_id=user.id,
            conversation_id=conversation_id,
        )
        raise
    except Exception as exc:
        logger.exception(
            "Unhandled exception while creating message.",
            error=str(exc),
            conversation_id=conversation_id,
        )
        return _json_response(
            ConversationMessageCreateAPIOutput(
                success=False,
                data=None,
                error="Unexpected error while creating message.",
            ),
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    if not result.status:
        return _json_response(
            ConversationMessageCreateAPIOutput(
                success=False,
                data=None,
                error=to_user_error_message(
                    error=result.error,
                    status_code=result.code,
                    fallback="Create message failed.",
                ),
            ),
            result.code,
        )

    payload = result.data if isinstance(result.data, dict) else {}
    data, data_error = _build_message_create_api_data(payload)
    if data_error:
        return data_error
    if data is None:
        return _json_response(
            ConversationMessageCreateAPIOutput(
                success=False, data=None, error="Unexpected message payload."
            ),
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    return ConversationMessageCreateAPIOutput(
        success=True,
        data=data,
        error=None,
    )


@conversation_router.post(
    "/conversations/{conversation_id}/messages/stream",
    response_model=None,
    status_code=status.HTTP_200_OK,
    summary="Create user message and stream assistant response",
)
async def create_conversation_message_stream(
    conversation_id: str,
    input: ConversationMessageCreateAPIInput,
    current_user_result: AuthServiceOutput = Depends(get_current_user),
) -> Response:
    user, error_response = _extract_user(current_user_result)
    if error_response:
        return error_response
    assert user is not None

    async def stream_generator() -> AsyncIterator[str]:
        loop = asyncio.get_running_loop()
        delta_queue: asyncio.Queue[str] = asyncio.Queue()
        streamed_delta_emitted = False

        def _on_token(delta: str) -> None:
            if not delta:
                return
            for word in _chunk_text(delta):
                loop.call_soon_threadsafe(delta_queue.put_nowait, word)

        task = loop.run_in_executor(
            get_crew_executor(),
            partial(
                _service.create_message,
                CreateConversationMessageInput(
                    owner_user_id=user.id or "",
                    conversation_id=conversation_id,
                    content=input.content,
                    selected_model=input.selected_model,
                    source_url=str(input.source_url) if input.source_url else None,
                    platforms=input.platforms,
                    silent=input.silent,
                    assistant_token_callback=_on_token,
                ),
            ),
        )

        yield _to_sse("status", {"status": "started"})

        while not task.done() or not delta_queue.empty():
            try:
                delta = await asyncio.wait_for(delta_queue.get(), timeout=0.6)
            except asyncio.TimeoutError:
                yield _to_sse("status", {"status": "processing"})
                continue
            streamed_delta_emitted = True
            yield _to_sse("delta", {"delta": delta})

        try:
            result = await task
        except asyncio.CancelledError:
            task.cancel()
            logger.warning(
                "Create message stream cancelled.",
                user_id=user.id,
                conversation_id=conversation_id,
            )
            raise
        except Exception as exc:
            logger.exception(
                "Unhandled exception while streaming message.",
                error=str(exc),
                conversation_id=conversation_id,
            )
            yield _to_sse(
                "error",
                {
                    "error": "Unexpected error while creating message.",
                    "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                },
            )
            return

        if not result.status:
            yield _to_sse(
                "error",
                {
                    "error": to_user_error_message(
                        error=result.error,
                        status_code=result.code,
                        fallback="Create message failed.",
                    ),
                    "code": result.code,
                },
            )
            return

        payload = result.data if isinstance(result.data, dict) else {}
        data, _ = _build_message_create_api_data(payload)
        if data is None:
            yield _to_sse(
                "error",
                {
                    "error": "Unexpected message payload.",
                    "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                },
            )
            return

        assistant_text = (
            data.assistant_message.content if data.assistant_message else ""
        )
        if not streamed_delta_emitted and assistant_text:
            # Fallback: simulate per-word delivery when workflow returns final text at once.
            for chunk in _chunk_text(assistant_text):
                yield _to_sse("delta", {"delta": chunk})
                await asyncio.sleep(0.02)

        yield _to_sse("done", data.model_dump(mode="json"))

    return StreamingResponse(
        stream_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
