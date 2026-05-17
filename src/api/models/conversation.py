from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import AnyHttpUrl, Field, field_validator, model_validator

from api.helpers.exception_handler import to_user_error_message
from infra.database.pg.schemas import Conversation, ConversationMessage, ConversationRun
from shared.base import BaseModel


class ConversationAPIData(BaseModel):
    id: str
    project_id: str
    title: str
    selected_model: str | None = None
    status: str
    message_count: int
    last_message_at: datetime | None = None
    createdAt: datetime | None = None
    updatedAt: datetime | None = None

    @classmethod
    def from_domain(cls, conversation: Conversation) -> "ConversationAPIData":
        return cls(
            id=str(conversation.id),
            project_id=conversation.project_id,
            title=conversation.title,
            selected_model=conversation.selected_model,
            status=conversation.status,
            message_count=conversation.message_count,
            last_message_at=conversation.last_message_at,
            createdAt=conversation.createdAt,
            updatedAt=conversation.updatedAt,
        )


class ConversationCreateAPIInput(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=255)
    selected_model: str | None = Field(None, max_length=64)

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("Conversation title must not be blank.")
        return normalized


class ConversationUpdateAPIInput(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=255)
    selected_model: str | None = Field(None, max_length=64)
    status: str | None = Field(None, max_length=32)

    @field_validator("title")
    @classmethod
    def validate_optional_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("Conversation title must not be blank.")
        return normalized

    @model_validator(mode="after")
    def validate_at_least_one_field(self) -> "ConversationUpdateAPIInput":
        has_payload = any(
            value is not None
            for value in [self.title, self.selected_model, self.status]
        )
        if not has_payload:
            raise ValueError("At least one field must be provided for update.")
        return self


class ConversationListAPIData(BaseModel):
    conversations: list[ConversationAPIData]

    @classmethod
    def from_domain(
        cls, conversations: list[Conversation]
    ) -> "ConversationListAPIData":
        return cls(
            conversations=[ConversationAPIData.from_domain(c) for c in conversations]
        )


class ConversationAPIOutput(BaseModel):
    success: bool
    data: ConversationAPIData | None = None
    error: str | None = None


class ConversationListAPIOutput(BaseModel):
    success: bool
    data: ConversationListAPIData | None = None
    error: str | None = None


class ConversationDeleteAPIData(BaseModel):
    id: str
    deleted: bool


class ConversationDeleteAPIOutput(BaseModel):
    success: bool
    data: ConversationDeleteAPIData | None = None
    error: str | None = None


class ConversationMessageAPIData(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    model: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    latency_ms: int | None = None
    error: str | None = None
    createdAt: datetime | None = None

    @classmethod
    def from_domain(cls, message: ConversationMessage) -> "ConversationMessageAPIData":
        safe_error = (
            to_user_error_message(
                error=message.error,
                status_code=400,
                fallback="I could not complete this request. Please try again.",
            )
            if message.error
            else None
        )
        return cls(
            id=str(message.id),
            conversation_id=message.conversation_id,
            role=message.role,
            content=message.content,
            model=message.model,
            input_tokens=message.input_tokens,
            output_tokens=message.output_tokens,
            latency_ms=message.latency_ms,
            error=safe_error,
            createdAt=message.createdAt,
        )


class ConversationMessageListAPIData(BaseModel):
    messages: list[ConversationMessageAPIData]
    next_cursor: str | None = None

    @classmethod
    def from_domain(
        cls,
        messages: list[ConversationMessage],
        next_cursor: str | None,
    ) -> "ConversationMessageListAPIData":
        return cls(
            messages=[ConversationMessageAPIData.from_domain(msg) for msg in messages],
            next_cursor=next_cursor,
        )


class ConversationMessageListAPIOutput(BaseModel):
    success: bool
    data: ConversationMessageListAPIData | None = None
    error: str | None = None


class ConversationRunAPIData(BaseModel):
    id: str
    conversation_id: str
    project_id: str
    status: str
    started_at: datetime
    finished_at: datetime | None = None
    source_url: str | None = None
    platforms: list[str]
    request_payload: dict[str, Any]
    response_payload: dict[str, Any]
    createdAt: datetime | None = None

    @classmethod
    def from_domain(cls, run: ConversationRun) -> "ConversationRunAPIData":
        response_payload = dict(run.response_payload or {})
        raw_error = response_payload.get("error")
        if isinstance(raw_error, str):
            response_payload["error"] = to_user_error_message(
                error=raw_error,
                status_code=400,
                fallback="I could not complete this request. Please try again.",
            )
        return cls(
            id=str(run.id),
            conversation_id=run.conversation_id,
            project_id=run.project_id,
            status=run.status,
            started_at=run.started_at,
            finished_at=run.finished_at,
            source_url=run.source_url,
            platforms=[str(p) for p in (run.platforms or [])],
            request_payload=dict(run.request_payload or {}),
            response_payload=response_payload,
            createdAt=run.createdAt,
        )


class ChatIntentAPIData(BaseModel):
    action: str
    target_platform: str | None = None
    normalized_prompt: str
    confidence: float = 0.0
    reason: str | None = None
    needs_clarification: bool = False
    clarify_question: str | None = None

    @classmethod
    def from_domain(cls, payload: dict[str, Any]) -> "ChatIntentAPIData":
        return cls(
            action=str(payload.get("action") or "GENERAL_QA"),
            target_platform=payload.get("target_platform"),
            normalized_prompt=str(payload.get("normalized_prompt") or ""),
            confidence=float(payload.get("confidence") or 0.0),
            reason=payload.get("reason"),
            needs_clarification=bool(payload.get("needs_clarification") or False),
            clarify_question=(
                str(payload.get("clarify_question"))
                if isinstance(payload.get("clarify_question"), str)
                and str(payload.get("clarify_question")).strip()
                else None
            ),
        )


class ConversationMessageCreateAPIInput(BaseModel):
    content: str = Field(..., min_length=1)
    selected_model: str | None = Field(None, max_length=64)
    source_url: AnyHttpUrl | None = None
    platforms: list[str] = Field(default_factory=list)
    silent: bool = False

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Message content must not be blank.")
        return normalized


class ConversationMessageCreateAPIData(BaseModel):
    user_message: ConversationMessageAPIData | None = None
    assistant_message: ConversationMessageAPIData | None = None
    run: ConversationRunAPIData
    intent: ChatIntentAPIData | None = None
    affected_sections: list[str] = Field(default_factory=list)
    content_plan_snapshot: dict[str, Any] | None = None

    @classmethod
    def from_domain(
        cls,
        *,
        user_message: ConversationMessage | None,
        assistant_message: ConversationMessage | None,
        run: ConversationRun,
        intent: dict[str, Any] | None = None,
        affected_sections: list[str] | None = None,
        content_plan_snapshot: dict[str, Any] | None = None,
    ) -> "ConversationMessageCreateAPIData":
        return cls(
            user_message=(
                ConversationMessageAPIData.from_domain(user_message)
                if user_message is not None
                else None
            ),
            assistant_message=(
                ConversationMessageAPIData.from_domain(assistant_message)
                if assistant_message is not None
                else None
            ),
            run=ConversationRunAPIData.from_domain(run),
            intent=ChatIntentAPIData.from_domain(intent)
            if isinstance(intent, dict)
            else None,
            affected_sections=list(affected_sections or []),
            content_plan_snapshot=content_plan_snapshot,
        )


class ConversationMessageCreateAPIOutput(BaseModel):
    success: bool
    data: ConversationMessageCreateAPIData | None = None
    error: str | None = None


class ProjectHistoryListAPIData(BaseModel):
    runs: list[ConversationRunAPIData]
    next_cursor: str | None = None

    @classmethod
    def from_domain(
        cls,
        runs: list[ConversationRun],
        next_cursor: str | None,
    ) -> "ProjectHistoryListAPIData":
        return cls(
            runs=[ConversationRunAPIData.from_domain(run) for run in runs],
            next_cursor=next_cursor,
        )


class ProjectHistoryListAPIOutput(BaseModel):
    success: bool
    data: ProjectHistoryListAPIData | None = None
    error: str | None = None


class ConversationRunAPIOutput(BaseModel):
    success: bool
    data: ConversationRunAPIData | None = None
    error: str | None = None


class RunSnapshotSaveAPIInput(BaseModel):
    content_plan_snapshot: dict[str, Any] = Field(default_factory=dict)


class RunSnapshotSaveAPIData(BaseModel):
    id: str
    saved: bool


class RunSnapshotSaveAPIOutput(BaseModel):
    success: bool
    data: RunSnapshotSaveAPIData | None = None
    error: str | None = None


class RunSnapshotRestoreAPIInput(BaseModel):
    target: str = Field(default="full_snapshot")

    @field_validator("target")
    @classmethod
    def validate_target(cls, value: str) -> str:
        normalized = value.strip()
        allowed_targets = {
            "full_snapshot",
            "analysis",
            "linkedin",
            "facebook",
        }
        if normalized not in allowed_targets:
            raise ValueError(
                "Unsupported restore target. Allowed: full_snapshot, analysis, linkedin, facebook."
            )
        return normalized


class RunSnapshotRestoreAPIData(BaseModel):
    restored_run: ConversationRunAPIData
    content_plan_snapshot: dict[str, Any]

    @classmethod
    def from_domain(
        cls,
        *,
        restored_run: ConversationRun,
        content_plan_snapshot: dict[str, Any],
    ) -> "RunSnapshotRestoreAPIData":
        return cls(
            restored_run=ConversationRunAPIData.from_domain(restored_run),
            content_plan_snapshot=dict(content_plan_snapshot),
        )


class RunSnapshotRestoreAPIOutput(BaseModel):
    success: bool
    data: RunSnapshotRestoreAPIData | None = None
    error: str | None = None
