from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any

import tiktoken
from api.helpers.exception_handler import to_user_error_message
from app.services.chat_refinement_service import ChatRefinementService
from app.services.chat_contracts import (
    ChatRefinementInput,
    IntentContext,
    RecentChatMessage,
)
from app.workflows.chat_snapshot import ContentPlanSnapshot
from infra.database.pg import SQLDatabase
from infra.database.pg.schemas import (
    Conversation,
    ConversationMessage,
    ConversationRun,
    Project,
)
from pydantic import Field
from shared.base import BaseModel
from shared.logging import get_logger, redact_message
from shared.settings.models import PostgresSettings

logger = get_logger(__name__)


DEFAULT_CONVERSATION_MODEL = "gpt-4o-mini"
LEGACY_OPENAI_MODEL_ALIASES = {"gpt-3.5-turbo": DEFAULT_CONVERSATION_MODEL}
RECENT_CHAT_TURNS_LIMIT = 10
RECENT_CHAT_MESSAGES_LIMIT = RECENT_CHAT_TURNS_LIMIT * 2
RECENT_CHAT_MESSAGE_MAX_TOKENS = 1024
RECENT_CHAT_ENCODING = tiktoken.get_encoding("cl100k_base")


class ConversationServiceOutput(BaseModel):
    status: bool
    data: Any | None = None
    error: str | None = None
    code: int = 200


class ListProjectConversationsInput(BaseModel):
    owner_user_id: str
    project_id: str
    limit: int = 20


class CreateConversationInput(BaseModel):
    owner_user_id: str
    project_id: str
    title: str | None = None
    selected_model: str | None = None


class GetConversationInput(BaseModel):
    owner_user_id: str
    conversation_id: str


class UpdateConversationInput(BaseModel):
    owner_user_id: str
    conversation_id: str
    title: str | None = None
    selected_model: str | None = None
    status: str | None = None


class DeleteConversationInput(BaseModel):
    owner_user_id: str
    conversation_id: str


class ListConversationMessagesInput(BaseModel):
    owner_user_id: str
    conversation_id: str
    cursor: str | None = None
    limit: int = 30


class CreateConversationMessageInput(BaseModel):
    owner_user_id: str
    conversation_id: str
    content: str
    selected_model: str | None = None
    source_url: str | None = None
    platforms: list[str] = Field(default_factory=list)
    silent: bool = False
    assistant_token_callback: Callable[[str], None] | None = None


class ListProjectHistoryInput(BaseModel):
    owner_user_id: str
    project_id: str
    status: str | None = None
    cursor: str | None = None
    limit: int = 20


class GetRunInput(BaseModel):
    owner_user_id: str
    run_id: str


class SaveRunSnapshotInput(BaseModel):
    owner_user_id: str
    run_id: str
    content_plan_snapshot: dict[str, Any]


class RestoreRunSnapshotInput(BaseModel):
    owner_user_id: str
    run_id: str
    target: str = "full_snapshot"


class PersistContentPlanSnapshotInput(BaseModel):
    owner_user_id: str
    project_id: str
    conversation_id: str
    source_url: str
    selected_model: str | None = None
    additional_context: str | None = None
    content_plan_snapshot: dict[str, Any]


class ConversationService(BaseModel):
    def __init__(self, **data: Any) -> None:
        super().__init__(**data)
        self._db = SQLDatabase(config=PostgresSettings())
        self._chat_refinement_service = ChatRefinementService()

    @staticmethod
    def _now_utc() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _ensure_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @staticmethod
    def _encode_cursor(created_at: datetime | None, item_id: str | None) -> str | None:
        if created_at is None or not item_id:
            return None
        return f"{ConversationService._ensure_utc(created_at).isoformat()}|{item_id}"

    @staticmethod
    def _decode_cursor(cursor: str | None) -> tuple[datetime | None, str | None]:
        if not cursor:
            return None, None
        try:
            created_part, item_id = cursor.split("|", maxsplit=1)
            created_at = datetime.fromisoformat(created_part)
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            return created_at, item_id
        except Exception:
            return None, None

    @staticmethod
    def _conversation_sort_key(conversation: Conversation) -> datetime:
        if conversation.last_message_at is not None:
            return ConversationService._ensure_utc(conversation.last_message_at)
        if conversation.createdAt is not None:
            return ConversationService._ensure_utc(conversation.createdAt)
        return datetime.fromtimestamp(0, tz=timezone.utc)

    @staticmethod
    def _run_sort_key(run: ConversationRun) -> datetime:
        if run.createdAt is not None:
            return ConversationService._ensure_utc(run.createdAt)
        return ConversationService._ensure_utc(run.started_at)

    @staticmethod
    def _normalize_model_name(model_name: str | None) -> str:
        normalized = (model_name or "").strip()
        if not normalized:
            return DEFAULT_CONVERSATION_MODEL
        return LEGACY_OPENAI_MODEL_ALIASES.get(normalized, normalized)

    @staticmethod
    def _normalize_restore_target(target: str | None) -> str:
        normalized = (target or "").strip().lower()
        allowed = {"full_snapshot", "analysis", "linkedin", "facebook"}
        if normalized not in allowed:
            return "full_snapshot"
        return normalized

    @staticmethod
    def _normalize_platform(platform: str) -> str:
        return platform.strip().lower()

    @staticmethod
    def _normalize_message_role(role: str | None) -> str | None:
        if not isinstance(role, str):
            return None
        normalized = role.strip().lower()
        if normalized in {"user", "assistant"}:
            return normalized
        return None

    @staticmethod
    def _normalize_history_text(value: str | None) -> str:
        if not isinstance(value, str):
            return ""
        return " ".join(value.strip().split())

    @staticmethod
    def _truncate_message_tokens(
        text: str, *, max_tokens: int = RECENT_CHAT_MESSAGE_MAX_TOKENS
    ) -> str:
        compact = ConversationService._normalize_history_text(text)
        if not compact:
            return ""
        token_ids = RECENT_CHAT_ENCODING.encode(compact)
        if len(token_ids) <= max_tokens:
            return compact
        return RECENT_CHAT_ENCODING.decode(token_ids[:max_tokens]).strip()

    @staticmethod
    def _recent_messages_digest(recent_messages: list[RecentChatMessage]) -> str:
        payload = "\n".join(
            f"{item.role}:{ConversationService._normalize_history_text(item.content)}"
            for item in recent_messages
        )
        return sha256(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def _snapshot_version(payload: dict[str, Any] | None) -> str:
        if not isinstance(payload, dict):
            return sha256(b"").hexdigest()
        try:
            snapshot_payload = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        except Exception:
            snapshot_payload = ""
        return sha256(snapshot_payload.encode("utf-8")).hexdigest()

    def _resolve_recent_messages(
        self,
        *,
        session,
        conversation_id: str,
    ) -> list[RecentChatMessage]:
        rows = self._db.list_conversation_messages_by_cursor(
            session=session,
            conversation_id=conversation_id,
            cursor_created_at=None,
            cursor_id=None,
            limit=RECENT_CHAT_MESSAGES_LIMIT,
        )
        if not rows:
            return []

        recent_messages: list[RecentChatMessage] = []
        for row in reversed(rows):
            normalized_role = self._normalize_message_role(row.role)
            if normalized_role is None:
                continue
            truncated_content = self._truncate_message_tokens(row.content)
            if not truncated_content:
                continue
            recent_messages.append(
                RecentChatMessage(role=normalized_role, content=truncated_content)
            )
        return recent_messages

    @staticmethod
    def _sanitize_refinement_error(error: str | None, code: int) -> str:
        return to_user_error_message(
            error=error,
            status_code=code,
            fallback="I could not complete this request. Please try again.",
        )

    @staticmethod
    def _normalize_snapshot(
        payload: dict[str, Any] | None,
        *,
        run_id: str | None = None,
    ) -> dict[str, Any] | None:
        if not isinstance(payload, dict) or not payload:
            return None
        try:
            snapshot = ContentPlanSnapshot.from_payload(payload)
            return snapshot.model_dump(mode="json")
        except Exception as exc:
            logger.warning(
                "invalid_content_plan_snapshot_payload",
                run_id=run_id,
                error=redact_message(str(exc)),
            )
            return None

    @classmethod
    def _build_assistant_failure_text(cls, error: str | None, code: int) -> str:
        if code >= 500:
            return "I could not complete this request right now. Please try again."
        return (
            "I could not complete this request. "
            f"{cls._sanitize_refinement_error(error, code)}"
        )

    def _find_post_by_platform(
        self,
        social_posts: list[dict[str, Any]],
        platform: str,
    ) -> dict[str, Any] | None:
        for post in social_posts:
            post_platform = post.get("platform")
            if not isinstance(post_platform, str):
                continue
            if self._normalize_platform(post_platform) == platform:
                return dict(post)
        return None

    def _merge_snapshot_by_target(
        self,
        *,
        target: str,
        source_snapshot: dict[str, Any],
        base_snapshot: dict[str, Any] | None,
    ) -> tuple[dict[str, Any] | None, str | None]:
        if target == "full_snapshot":
            return dict(source_snapshot), None

        merged = dict(base_snapshot or source_snapshot)
        if target == "analysis":
            source_analysis = source_snapshot.get("analysis")
            if not isinstance(source_analysis, dict):
                return None, "Source snapshot does not contain analysis data."
            merged["analysis"] = dict(source_analysis)
            return merged, None

        source_posts_raw = source_snapshot.get("social_posts", [])
        if not isinstance(source_posts_raw, list):
            return None, "Source snapshot does not contain social posts."
        source_posts = [post for post in source_posts_raw if isinstance(post, dict)]
        source_post = self._find_post_by_platform(source_posts, target)
        if source_post is None:
            return None, f"Source snapshot does not contain a '{target}' post."

        merged_posts_raw = merged.get("social_posts", [])
        merged_posts: list[dict[str, Any]]
        if isinstance(merged_posts_raw, list):
            merged_posts = [post for post in merged_posts_raw if isinstance(post, dict)]
        else:
            merged_posts = []

        replaced = False
        next_posts: list[dict[str, Any]] = []
        for post in merged_posts:
            post_platform = post.get("platform")
            if (
                isinstance(post_platform, str)
                and self._normalize_platform(post_platform) == target
            ):
                next_posts.append(dict(source_post))
                replaced = True
            else:
                next_posts.append(dict(post))
        if not replaced:
            next_posts.append(dict(source_post))
        merged["social_posts"] = next_posts
        return merged, None

    def _resolve_latest_snapshot(
        self,
        *,
        session,
        project_id: str,
        conversation_id: str,
    ) -> dict[str, Any] | None:
        runs = (
            self._db.get_conversation_runs(
                session=session,
                filter={"conversation_id": conversation_id},
            )
            or []
        )
        if not runs:
            runs = (
                self._db.get_conversation_runs(
                    session=session,
                    filter={"project_id": project_id},
                )
                or []
            )
        ordered_runs = sorted(runs, key=self._run_sort_key, reverse=True)
        for run in ordered_runs:
            payload = dict(run.response_payload or {})
            snapshot = self._normalize_snapshot(
                payload.get("content_plan_snapshot"),
                run_id=run.id,
            )
            if snapshot is not None:
                return snapshot
        return None

    @staticmethod
    def _extract_intent_context_from_payload(
        payload: dict[str, Any] | None,
        *,
        updated_at: datetime | None = None,
    ) -> IntentContext | None:
        data = dict(payload or {})
        raw_active_context = data.get("active_context")
        active_context = (
            raw_active_context if isinstance(raw_active_context, dict) else {}
        )
        raw_intent = data.get("intent")
        intent = raw_intent if isinstance(raw_intent, dict) else {}

        last_target_platform = (
            active_context.get("last_target_platform") or intent.get("target_platform")
        )
        if (
            not isinstance(last_target_platform, str)
            or not last_target_platform.strip()
        ):
            last_target_platform = None
        else:
            last_target_platform = last_target_platform.strip().lower()

        last_action = (
            active_context.get("last_action")
            or data.get("action")
            or intent.get("action")
        )
        if not isinstance(last_action, str) or not last_action.strip():
            last_action = None
        else:
            last_action = last_action.strip().upper()

        last_language = active_context.get("last_language") or data.get("language_used")
        if not isinstance(last_language, str) or not last_language.strip():
            last_language = None
        else:
            last_language = last_language.strip().lower()

        if not (last_target_platform or last_action or last_language):
            return None

        return IntentContext(
            last_target_platform=last_target_platform,
            last_action=last_action,
            last_language=last_language,
            updated_at=(
                ConversationService._ensure_utc(updated_at).isoformat()
                if updated_at is not None
                else None
            ),
        )

    @staticmethod
    def _next_active_context(
        *,
        current_context: IntentContext | None,
        resolved_intent: dict[str, Any] | None,
        language_used: str | None,
        updated_at: datetime,
    ) -> IntentContext | None:
        if not isinstance(resolved_intent, dict):
            return None
        action_value = resolved_intent.get("action")
        if not isinstance(action_value, str):
            return None
        normalized_action = action_value.strip().upper()
        if normalized_action in {"GENERAL_QA", "CLARIFY"}:
            return None

        target_platform = resolved_intent.get("target_platform")
        normalized_platform = (
            target_platform.strip().lower()
            if isinstance(target_platform, str) and target_platform.strip()
            else None
        )
        normalized_language = (
            language_used.strip().lower()
            if isinstance(language_used, str) and language_used.strip()
            else (
                current_context.last_language
                if isinstance(current_context, IntentContext)
                else None
            )
        )
        return IntentContext(
            last_target_platform=normalized_platform,
            last_action=normalized_action,
            last_language=normalized_language,
            updated_at=ConversationService._ensure_utc(updated_at).isoformat(),
        )

    @classmethod
    def _resolve_next_active_context_after_refinement(
        cls,
        *,
        current_context: IntentContext | None,
        refinement_status: bool,
        resolved_intent: dict[str, Any] | None,
        language_used: str | None,
        updated_at: datetime,
    ) -> IntentContext | None:
        if not refinement_status:
            return current_context
        return cls._next_active_context(
            current_context=current_context,
            resolved_intent=resolved_intent,
            language_used=language_used,
            updated_at=updated_at,
        )

    def _resolve_latest_intent_context(
        self,
        *,
        session,
        conversation_id: str,
    ) -> IntentContext | None:
        runs = (
            self._db.get_conversation_runs(
                session=session,
                filter={"conversation_id": conversation_id},
            )
            or []
        )
        ordered_runs = sorted(runs, key=self._run_sort_key, reverse=True)
        for run in ordered_runs:
            context = self._extract_intent_context_from_payload(
                dict(run.request_payload or {}),
                updated_at=run.finished_at or run.started_at,
            )
            if context is not None:
                return context
        return None

    def _normalize_project_single_conversation(
        self,
        *,
        session,
        project_id: str,
    ) -> Conversation | None:
        conversations = (
            self._db.get_conversations(
                session=session,
                filter={"project_id": project_id},
            )
            or []
        )
        if not conversations:
            return None

        ordered = sorted(
            conversations,
            key=self._conversation_sort_key,
            reverse=True,
        )
        primary = ordered[0]
        duplicates = [conversation for conversation in ordered[1:] if conversation.id]
        for duplicate in duplicates:
            duplicate_id = duplicate.id
            if duplicate_id:
                self._db.delete_conversation(session=session, id=duplicate_id)

        if duplicates:
            logger.info(
                "project_conversations_normalized",
                project_id=project_id,
                primary_conversation_id=primary.id,
                soft_deleted_count=len(duplicates),
            )
        return primary

    def _get_project_owned(
        self, *, session, owner_user_id: str, project_id: str
    ) -> Project | None:
        project = self._db.get_project_by_id(session=session, id=project_id)
        if project is None or project.owner_user_id != owner_user_id:
            return None
        return project

    def _get_conversation_owned(
        self,
        *,
        session,
        owner_user_id: str,
        conversation_id: str,
    ) -> tuple[Conversation | None, Project | None]:
        conversation = self._db.get_conversation_by_id(
            session=session, id=conversation_id
        )
        if conversation is None:
            return None, None
        project = self._db.get_project_by_id(
            session=session, id=conversation.project_id
        )
        if project is None or project.owner_user_id != owner_user_id:
            return None, None
        return conversation, project

    def list_project_conversations(
        self, inputs: ListProjectConversationsInput
    ) -> ConversationServiceOutput:
        try:
            with self._db.get_session() as session:
                project = self._get_project_owned(
                    session=session,
                    owner_user_id=inputs.owner_user_id,
                    project_id=inputs.project_id,
                )
                if project is None:
                    return ConversationServiceOutput(
                        status=False,
                        data=None,
                        error=f"Project with id '{inputs.project_id}' not found.",
                        code=404,
                    )
                primary_conversation = self._normalize_project_single_conversation(
                    session=session,
                    project_id=inputs.project_id,
                )
                conversations: list[Conversation] = (
                    [primary_conversation] if primary_conversation else []
                )
                return ConversationServiceOutput(
                    status=True, data=conversations, error=None, code=200
                )
        except Exception as exc:
            logger.exception(
                "Failed to list project conversations",
                error=str(exc),
                project_id=inputs.project_id,
            )
            return ConversationServiceOutput(
                status=False,
                data=None,
                error="Unexpected error while listing conversations.",
                code=500,
            )

    def create_conversation(
        self, inputs: CreateConversationInput
    ) -> ConversationServiceOutput:
        try:
            with self._db.get_session() as session:
                project = self._get_project_owned(
                    session=session,
                    owner_user_id=inputs.owner_user_id,
                    project_id=inputs.project_id,
                )
                if project is None:
                    return ConversationServiceOutput(
                        status=False,
                        data=None,
                        error=f"Project with id '{inputs.project_id}' not found.",
                        code=404,
                    )

                now = self._now_utc()
                existing_conversation = self._normalize_project_single_conversation(
                    session=session,
                    project_id=inputs.project_id,
                )
                if existing_conversation is not None:
                    project.last_active_at = now
                    self._db.update_project(session=session, model=project)
                    return ConversationServiceOutput(
                        status=True,
                        data=existing_conversation,
                        error=None,
                        code=200,
                    )

                title = (inputs.title or "New Chat").strip() or "New Chat"
                model = Conversation(
                    project_id=inputs.project_id,
                    title=title,
                    selected_model=self._normalize_model_name(inputs.selected_model),
                    status="active",
                    message_count=0,
                    last_message_at=now,
                )
                conversation = self._db.insert_conversation(
                    session=session, model=model
                )

                project.last_active_at = now
                self._db.update_project(session=session, model=project)
                return ConversationServiceOutput(
                    status=True, data=conversation, error=None, code=201
                )
        except Exception as exc:
            logger.exception(
                "Failed to create conversation",
                error=str(exc),
                project_id=inputs.project_id,
            )
            return ConversationServiceOutput(
                status=False,
                data=None,
                error=f"Unexpected error while creating conversation: {redact_message(str(exc))}",
                code=500,
            )

    def get_conversation(
        self, inputs: GetConversationInput
    ) -> ConversationServiceOutput:
        try:
            with self._db.get_session() as session:
                conversation, project = self._get_conversation_owned(
                    session=session,
                    owner_user_id=inputs.owner_user_id,
                    conversation_id=inputs.conversation_id,
                )
                if conversation is None or project is None:
                    return ConversationServiceOutput(
                        status=False,
                        data=None,
                        error=f"Conversation with id '{inputs.conversation_id}' not found.",
                        code=404,
                    )
                return ConversationServiceOutput(
                    status=True, data=conversation, error=None, code=200
                )
        except Exception as exc:
            logger.exception(
                "Failed to get conversation",
                error=str(exc),
                conversation_id=inputs.conversation_id,
            )
            return ConversationServiceOutput(
                status=False,
                data=None,
                error="Unexpected error while getting conversation.",
                code=500,
            )

    def update_conversation(
        self, inputs: UpdateConversationInput
    ) -> ConversationServiceOutput:
        try:
            with self._db.get_session() as session:
                conversation, project = self._get_conversation_owned(
                    session=session,
                    owner_user_id=inputs.owner_user_id,
                    conversation_id=inputs.conversation_id,
                )
                if conversation is None or project is None:
                    return ConversationServiceOutput(
                        status=False,
                        data=None,
                        error=f"Conversation with id '{inputs.conversation_id}' not found.",
                        code=404,
                    )
                title = conversation.title
                if inputs.title is not None:
                    title = inputs.title.strip()
                    if not title:
                        return ConversationServiceOutput(
                            status=False,
                            data=None,
                            error="Conversation title must not be blank.",
                            code=400,
                        )

                updated_model = Conversation(
                    id=conversation.id,
                    project_id=conversation.project_id,
                    title=title,
                    selected_model=self._normalize_model_name(
                        inputs.selected_model
                        if inputs.selected_model is not None
                        else conversation.selected_model
                    ),
                    status=inputs.status
                    if inputs.status is not None
                    else conversation.status,
                    message_count=conversation.message_count,
                    last_message_at=conversation.last_message_at,
                )
                updated = self._db.update_conversation(
                    session=session, model=updated_model
                )
                if updated is None:
                    return ConversationServiceOutput(
                        status=False,
                        data=None,
                        error=f"Conversation with id '{inputs.conversation_id}' not found.",
                        code=404,
                    )
                return ConversationServiceOutput(
                    status=True, data=updated, error=None, code=200
                )
        except Exception as exc:
            logger.exception(
                "Failed to update conversation",
                error=str(exc),
                conversation_id=inputs.conversation_id,
            )
            return ConversationServiceOutput(
                status=False,
                data=None,
                error=f"Unexpected error while updating conversation: {redact_message(str(exc))}",
                code=500,
            )

    def delete_conversation(
        self, inputs: DeleteConversationInput
    ) -> ConversationServiceOutput:
        try:
            with self._db.get_session() as session:
                conversation, project = self._get_conversation_owned(
                    session=session,
                    owner_user_id=inputs.owner_user_id,
                    conversation_id=inputs.conversation_id,
                )
                if conversation is None or project is None:
                    return ConversationServiceOutput(
                        status=False,
                        data=None,
                        error=f"Conversation with id '{inputs.conversation_id}' not found.",
                        code=404,
                    )
                deleted = self._db.delete_conversation(
                    session=session, id=inputs.conversation_id
                )
                if deleted is None:
                    return ConversationServiceOutput(
                        status=False,
                        data=None,
                        error=f"Conversation with id '{inputs.conversation_id}' not found.",
                        code=404,
                    )
                return ConversationServiceOutput(
                    status=True, data=deleted, error=None, code=200
                )
        except Exception as exc:
            logger.exception(
                "Failed to delete conversation",
                error=str(exc),
                conversation_id=inputs.conversation_id,
            )
            return ConversationServiceOutput(
                status=False,
                data=None,
                error=f"Unexpected error while deleting conversation: {redact_message(str(exc))}",
                code=500,
            )

    def list_messages(
        self, inputs: ListConversationMessagesInput
    ) -> ConversationServiceOutput:
        try:
            cursor_created_at, cursor_id = self._decode_cursor(inputs.cursor)
            with self._db.get_session() as session:
                conversation, project = self._get_conversation_owned(
                    session=session,
                    owner_user_id=inputs.owner_user_id,
                    conversation_id=inputs.conversation_id,
                )
                if conversation is None or project is None:
                    return ConversationServiceOutput(
                        status=False,
                        data=None,
                        error=f"Conversation with id '{inputs.conversation_id}' not found.",
                        code=404,
                    )
                rows = self._db.list_conversation_messages_by_cursor(
                    session=session,
                    conversation_id=inputs.conversation_id,
                    cursor_created_at=cursor_created_at,
                    cursor_id=cursor_id,
                    limit=inputs.limit + 1,
                )

                has_more = len(rows) > inputs.limit
                page_rows = rows[: inputs.limit]
                next_cursor = None
                if has_more and page_rows:
                    next_cursor = self._encode_cursor(
                        page_rows[-1].createdAt, page_rows[-1].id
                    )
                ordered_messages = list(reversed(page_rows))
                return ConversationServiceOutput(
                    status=True,
                    data={"messages": ordered_messages, "next_cursor": next_cursor},
                    error=None,
                    code=200,
                )
        except Exception as exc:
            logger.exception(
                "Failed to list messages",
                error=str(exc),
                conversation_id=inputs.conversation_id,
            )
            return ConversationServiceOutput(
                status=False,
                data=None,
                error=f"Unexpected error while listing messages: {redact_message(str(exc))}",
                code=500,
            )

    def create_message(
        self, inputs: CreateConversationMessageInput
    ) -> ConversationServiceOutput:
        try:
            with self._db.get_session() as session:
                conversation, project = self._get_conversation_owned(
                    session=session,
                    owner_user_id=inputs.owner_user_id,
                    conversation_id=inputs.conversation_id,
                )
                if conversation is None or project is None:
                    return ConversationServiceOutput(
                        status=False,
                        data=None,
                        error=f"Conversation with id '{inputs.conversation_id}' not found.",
                        code=404,
                    )
                primary_conversation = self._normalize_project_single_conversation(
                    session=session,
                    project_id=conversation.project_id,
                )
                if primary_conversation is None:
                    return ConversationServiceOutput(
                        status=False,
                        data=None,
                        error=f"Conversation with id '{inputs.conversation_id}' not found.",
                        code=404,
                    )
                conversation = primary_conversation

                prompt = inputs.content.strip()
                if not prompt:
                    return ConversationServiceOutput(
                        status=False,
                        data=None,
                        error="Message content must not be blank.",
                        code=400,
                    )
                model_name = self._normalize_model_name(
                    inputs.selected_model or conversation.selected_model
                )
                if conversation.selected_model != model_name:
                    self._db.update_conversation(
                        session=session,
                        model=Conversation(
                            id=conversation.id,
                            project_id=conversation.project_id,
                            title=conversation.title,
                            selected_model=model_name,
                            status=conversation.status,
                            message_count=conversation.message_count,
                            last_message_at=conversation.last_message_at,
                        ),
                    )
                source_url = (
                    inputs.source_url or project.source_url or ""
                ).strip() or None
                started_at = self._now_utc()
                recent_messages = self._resolve_recent_messages(
                    session=session,
                    conversation_id=conversation.id or "",
                )
                recent_messages_digest = self._recent_messages_digest(recent_messages)

                user_message: ConversationMessage | None = None
                if not inputs.silent:
                    user_message = self._db.insert_conversation_message(
                        session=session,
                        model=ConversationMessage(
                            conversation_id=conversation.id or "",
                            role="user",
                            content=prompt,
                            model=model_name,
                            input_tokens=max(len(prompt.split()), 1),
                            output_tokens=None,
                            latency_ms=None,
                            error=None,
                        ),
                    )

                latest_snapshot = self._resolve_latest_snapshot(
                    session=session,
                    project_id=project.id or "",
                    conversation_id=conversation.id or "",
                )
                snapshot_version = self._snapshot_version(latest_snapshot)
                latest_intent_context = self._resolve_latest_intent_context(
                    session=session,
                    conversation_id=conversation.id or "",
                )
                context_version = (
                    latest_intent_context.updated_at
                    if latest_intent_context is not None
                    else None
                )
                run = self._db.insert_conversation_run(
                    session=session,
                    model=ConversationRun(
                        conversation_id=conversation.id or "",
                        project_id=project.id or "",
                        request_payload={
                            "content": prompt,
                            "selected_model": model_name,
                            "source_url": source_url,
                            "recent_messages_count": len(recent_messages),
                            "recent_messages_digest": recent_messages_digest,
                            "active_context": (
                                latest_intent_context.model_dump(mode="json")
                                if latest_intent_context is not None
                                else None
                            ),
                            "snapshot_version": snapshot_version,
                            "context_version": context_version,
                        },
                        response_payload={},
                        status="running",
                        started_at=started_at,
                        finished_at=None,
                        source_url=source_url,
                        platforms=inputs.platforms,
                    ),
                )

                refinement_result = self._chat_refinement_service.process(
                    ChatRefinementInput(
                        owner_user_id=inputs.owner_user_id,
                        conversation_id=conversation.id or "",
                        prompt=prompt,
                        selected_model=model_name,
                        source_url=source_url,
                        snapshot=latest_snapshot,
                        intent_context=latest_intent_context,
                        recent_messages=recent_messages,
                        assistant_token_callback=inputs.assistant_token_callback,
                    )
                )
                safe_refinement_error = self._sanitize_refinement_error(
                    refinement_result.error,
                    refinement_result.code,
                )
                assistant_text = (
                    refinement_result.assistant_text
                    if refinement_result.status and refinement_result.assistant_text
                    else self._build_assistant_failure_text(
                        refinement_result.error,
                        refinement_result.code,
                    )
                )
                assistant_message: ConversationMessage | None = None
                if not inputs.silent:
                    assistant_message = self._db.insert_conversation_message(
                        session=session,
                        model=ConversationMessage(
                            conversation_id=conversation.id or "",
                            role="assistant",
                            content=assistant_text,
                            model=model_name,
                            input_tokens=None,
                            output_tokens=max(len(assistant_text.split()), 1),
                            latency_ms=max(
                                int(
                                    (self._now_utc() - started_at).total_seconds()
                                    * 1000
                                ),
                                1,
                            ),
                            error=(
                                safe_refinement_error
                                if not refinement_result.status
                                else None
                            ),
                        ),
                    )

                finished_at = self._now_utc()
                resolved_intent_payload = (
                    refinement_result.intent.model_dump(mode="json")
                    if refinement_result.intent is not None
                    else None
                )
                language_used = (
                    refinement_result.metadata.get("language_used")
                    if isinstance(refinement_result.metadata, dict)
                    else None
                )
                routing_payload = (
                    refinement_result.intent.routing_metadata
                    if refinement_result.intent is not None
                    else {}
                )
                next_active_context = self._resolve_next_active_context_after_refinement(
                    current_context=latest_intent_context,
                    refinement_status=refinement_result.status,
                    resolved_intent=resolved_intent_payload,
                    language_used=(
                        str(language_used) if isinstance(language_used, str) else None
                    ),
                    updated_at=finished_at,
                )
                run_request_payload = {
                    "content": prompt,
                    "selected_model": model_name,
                    "source_url": source_url,
                    "recent_messages_count": len(recent_messages),
                    "recent_messages_digest": recent_messages_digest,
                    "snapshot_version": (
                        refinement_result.metadata.get("snapshot_version")
                        if isinstance(refinement_result.metadata, dict)
                        else snapshot_version
                    ),
                    "context_version": (
                        refinement_result.metadata.get("context_version")
                        if isinstance(refinement_result.metadata, dict)
                        else context_version
                    ),
                    "active_context": (
                        next_active_context.model_dump(mode="json")
                        if next_active_context is not None
                        else None
                    ),
                    "routing_stage1": (
                        routing_payload.get("stage1")
                        if isinstance(routing_payload, dict)
                        else None
                    ),
                    "routing_stage2": (
                        routing_payload.get("stage2")
                        if isinstance(routing_payload, dict)
                        else None
                    ),
                    "intent_context": (
                        latest_intent_context.model_dump(mode="json")
                        if latest_intent_context is not None
                        else None
                    ),
                    "intent": resolved_intent_payload,
                    "action": (
                        refinement_result.intent.action.value
                        if refinement_result.intent is not None
                        else None
                    ),
                    "language_used": language_used,
                }
                run_request_payload = {
                    key: value
                    for key, value in run_request_payload.items()
                    if value is not None
                }
                run_response_payload = {
                    "assistant_message_id": (
                        assistant_message.id if assistant_message is not None else None
                    ),
                    "assistant_content": assistant_text,
                    "affected_sections": refinement_result.affected_sections,
                    "content_plan_snapshot": refinement_result.content_plan_snapshot,
                    "error": safe_refinement_error
                    if not refinement_result.status
                    else None,
                    "silent": inputs.silent,
                }
                run_response_payload = {
                    key: value
                    for key, value in run_response_payload.items()
                    if value is not None
                }
                updated_run = self._db.update_conversation_run(
                    session=session,
                    model=ConversationRun(
                        id=run.id,
                        conversation_id=conversation.id or "",
                        project_id=project.id or "",
                        request_payload=run_request_payload,
                        response_payload=run_response_payload,
                        status="completed" if refinement_result.status else "failed",
                        started_at=started_at,
                        finished_at=finished_at,
                        source_url=source_url,
                        platforms=inputs.platforms,
                    ),
                )
                run = updated_run or run

                message_count_delta = 0 if inputs.silent else 2
                last_message_at = (
                    conversation.last_message_at if inputs.silent else finished_at
                )
                updated_conversation = Conversation(
                    id=conversation.id,
                    project_id=conversation.project_id,
                    title=conversation.title,
                    selected_model=model_name,
                    status="active",
                    message_count=conversation.message_count + message_count_delta,
                    last_message_at=last_message_at,
                )
                self._db.update_conversation(
                    session=session, model=updated_conversation
                )

                project.last_active_at = finished_at
                self._db.update_project(session=session, model=project)

                if not refinement_result.status:
                    return ConversationServiceOutput(
                        status=False,
                        data=None,
                        error=safe_refinement_error,
                        code=refinement_result.code,
                    )

                return ConversationServiceOutput(
                    status=True,
                    data={
                        "user_message": user_message,
                        "assistant_message": assistant_message,
                        "run": run,
                        "intent": (
                            refinement_result.intent.model_dump(mode="json")
                            if refinement_result.intent is not None
                            else None
                        ),
                        "affected_sections": refinement_result.affected_sections,
                        "content_plan_snapshot": refinement_result.content_plan_snapshot,
                    },
                    error=None,
                    code=201,
                )
        except Exception as exc:
            logger.exception(
                "Failed to create message",
                error=redact_message(str(exc)),
                conversation_id=inputs.conversation_id,
            )
            return ConversationServiceOutput(
                status=False,
                data=None,
                error=f"Unexpected error while creating message: {redact_message(str(exc))}",
                code=500,
            )

    def list_project_history(
        self, inputs: ListProjectHistoryInput
    ) -> ConversationServiceOutput:
        try:
            cursor_created_at, cursor_id = self._decode_cursor(inputs.cursor)
            with self._db.get_session() as session:
                project = self._get_project_owned(
                    session=session,
                    owner_user_id=inputs.owner_user_id,
                    project_id=inputs.project_id,
                )
                if project is None:
                    return ConversationServiceOutput(
                        status=False,
                        data=None,
                        error=f"Project with id '{inputs.project_id}' not found.",
                        code=404,
                    )
                rows = self._db.list_project_runs_by_cursor(
                    session=session,
                    project_id=inputs.project_id,
                    status=inputs.status,
                    cursor_created_at=cursor_created_at,
                    cursor_id=cursor_id,
                    limit=inputs.limit + 1,
                )
                has_more = len(rows) > inputs.limit
                page_rows = rows[: inputs.limit]
                next_cursor = None
                if has_more and page_rows:
                    next_cursor = self._encode_cursor(
                        page_rows[-1].createdAt, page_rows[-1].id
                    )
                return ConversationServiceOutput(
                    status=True,
                    data={"runs": page_rows, "next_cursor": next_cursor},
                    error=None,
                    code=200,
                )
        except Exception as exc:
            logger.exception(
                "Failed to list project history",
                error=str(exc),
                project_id=inputs.project_id,
            )
            return ConversationServiceOutput(
                status=False,
                data=None,
                error=f"Unexpected error while listing history: {redact_message(str(exc))}",
                code=500,
            )

    def persist_content_plan_snapshot(
        self, inputs: PersistContentPlanSnapshotInput
    ) -> ConversationServiceOutput:
        try:
            normalized_snapshot = self._normalize_snapshot(inputs.content_plan_snapshot)
            if normalized_snapshot is None:
                return ConversationServiceOutput(
                    status=False,
                    data=None,
                    error="Invalid content_plan_snapshot payload.",
                    code=400,
                )
            with self._db.get_session() as session:
                project = self._get_project_owned(
                    session=session,
                    owner_user_id=inputs.owner_user_id,
                    project_id=inputs.project_id,
                )
                if project is None:
                    return ConversationServiceOutput(
                        status=False,
                        data=None,
                        error=f"Project with id '{inputs.project_id}' not found.",
                        code=404,
                    )

                conversation, owned_project = self._get_conversation_owned(
                    session=session,
                    owner_user_id=inputs.owner_user_id,
                    conversation_id=inputs.conversation_id,
                )
                if conversation is None or owned_project is None:
                    return ConversationServiceOutput(
                        status=False,
                        data=None,
                        error=f"Conversation with id '{inputs.conversation_id}' not found.",
                        code=404,
                    )
                if conversation.project_id != inputs.project_id:
                    return ConversationServiceOutput(
                        status=False,
                        data=None,
                        error="Conversation does not belong to the specified project.",
                        code=400,
                    )

                now = self._now_utc()
                social_posts = normalized_snapshot.get("social_posts", [])
                platforms: list[str] = []
                if isinstance(social_posts, list):
                    for post in social_posts:
                        if not isinstance(post, dict):
                            continue
                        platform = post.get("platform")
                        if isinstance(platform, str) and platform not in platforms:
                            platforms.append(platform)

                run = self._db.insert_conversation_run(
                    session=session,
                    model=ConversationRun(
                        conversation_id=conversation.id or "",
                        project_id=inputs.project_id,
                        request_payload={
                            "source_url": inputs.source_url,
                            "selected_model": inputs.selected_model,
                            "additional_context": inputs.additional_context,
                            "trigger": "content_plan",
                        },
                        response_payload={
                            "content_plan_snapshot": normalized_snapshot,
                        },
                        status="completed",
                        started_at=now,
                        finished_at=now,
                        source_url=inputs.source_url,
                        platforms=platforms,
                    ),
                )
                project.last_active_at = now
                self._db.update_project(session=session, model=project)

                return ConversationServiceOutput(
                    status=True,
                    data=run,
                    error=None,
                    code=201,
                )
        except Exception as exc:
            logger.exception(
                "Failed to persist content plan snapshot",
                error=redact_message(str(exc)),
                project_id=inputs.project_id,
                conversation_id=inputs.conversation_id,
            )
            return ConversationServiceOutput(
                status=False,
                data=None,
                error=f"Unexpected error while persisting snapshot: {redact_message(str(exc))}",
                code=500,
            )

    def get_run(self, inputs: GetRunInput) -> ConversationServiceOutput:
        try:
            with self._db.get_session() as session:
                run = self._db.get_conversation_run_by_id(
                    session=session, id=inputs.run_id
                )
                if run is None:
                    return ConversationServiceOutput(
                        status=False,
                        data=None,
                        error=f"Run with id '{inputs.run_id}' not found.",
                        code=404,
                    )
                project = self._db.get_project_by_id(session=session, id=run.project_id)
                if project is None or project.owner_user_id != inputs.owner_user_id:
                    return ConversationServiceOutput(
                        status=False,
                        data=None,
                        error=f"Run with id '{inputs.run_id}' not found.",
                        code=404,
                    )
                return ConversationServiceOutput(
                    status=True, data=run, error=None, code=200
                )
        except Exception as exc:
            logger.exception("Failed to get run", error=str(exc), run_id=inputs.run_id)
            return ConversationServiceOutput(
                status=False,
                data=None,
                error=f"Unexpected error while getting run: {redact_message(str(exc))}",
                code=500,
            )

    def save_run_snapshot(
        self, inputs: SaveRunSnapshotInput
    ) -> ConversationServiceOutput:
        try:
            normalized_snapshot = self._normalize_snapshot(inputs.content_plan_snapshot)
            if normalized_snapshot is None:
                return ConversationServiceOutput(
                    status=False,
                    data=None,
                    error="Invalid content_plan_snapshot payload.",
                    code=400,
                )
            with self._db.get_session() as session:
                run = self._db.get_conversation_run_by_id(
                    session=session, id=inputs.run_id
                )
                if run is None:
                    return ConversationServiceOutput(
                        status=False,
                        data=None,
                        error=f"Run with id '{inputs.run_id}' not found.",
                        code=404,
                    )

                project = self._db.get_project_by_id(session=session, id=run.project_id)
                if project is None or project.owner_user_id != inputs.owner_user_id:
                    return ConversationServiceOutput(
                        status=False,
                        data=None,
                        error=f"Run with id '{inputs.run_id}' not found.",
                        code=404,
                    )

                response_payload = dict(run.response_payload or {})
                response_payload["content_plan_snapshot"] = normalized_snapshot

                updated_model = ConversationRun(
                    id=run.id,
                    conversation_id=run.conversation_id,
                    project_id=run.project_id,
                    request_payload=dict(run.request_payload or {}),
                    response_payload=response_payload,
                    status=run.status,
                    started_at=run.started_at,
                    finished_at=run.finished_at,
                    source_url=run.source_url,
                    platforms=list(run.platforms or []),
                )
                updated_run = self._db.update_conversation_run(
                    session=session,
                    model=updated_model,
                )
                if updated_run is None:
                    return ConversationServiceOutput(
                        status=False,
                        data=None,
                        error=f"Run with id '{inputs.run_id}' not found.",
                        code=404,
                    )

                return ConversationServiceOutput(
                    status=True,
                    data=updated_run,
                    error=None,
                    code=200,
                )
        except Exception as exc:
            logger.exception(
                "Failed to save run snapshot", error=str(exc), run_id=inputs.run_id
            )
            return ConversationServiceOutput(
                status=False,
                data=None,
                error=f"Unexpected error while saving run snapshot: {redact_message(str(exc))}",
                code=500,
            )

    def restore_run_snapshot(
        self, inputs: RestoreRunSnapshotInput
    ) -> ConversationServiceOutput:
        try:
            target = self._normalize_restore_target(inputs.target)
            with self._db.get_session() as session:
                source_run = self._db.get_conversation_run_by_id(
                    session=session, id=inputs.run_id
                )
                if source_run is None:
                    return ConversationServiceOutput(
                        status=False,
                        data=None,
                        error=f"Run with id '{inputs.run_id}' not found.",
                        code=404,
                    )

                project = self._db.get_project_by_id(
                    session=session, id=source_run.project_id
                )
                if project is None or project.owner_user_id != inputs.owner_user_id:
                    return ConversationServiceOutput(
                        status=False,
                        data=None,
                        error=f"Run with id '{inputs.run_id}' not found.",
                        code=404,
                    )

                snapshot = self._normalize_snapshot(
                    dict(source_run.response_payload or {}).get(
                        "content_plan_snapshot"
                    ),
                    run_id=source_run.id,
                )
                if snapshot is None:
                    return ConversationServiceOutput(
                        status=False,
                        data=None,
                        error="Source run does not contain a restorable content snapshot.",
                        code=409,
                    )

                latest_snapshot = self._resolve_latest_snapshot(
                    session=session,
                    project_id=source_run.project_id,
                    conversation_id=source_run.conversation_id,
                )
                restored_snapshot, merge_error = self._merge_snapshot_by_target(
                    target=target,
                    source_snapshot=snapshot,
                    base_snapshot=latest_snapshot,
                )
                if merge_error or not isinstance(restored_snapshot, dict):
                    return ConversationServiceOutput(
                        status=False,
                        data=None,
                        error=merge_error or "Unable to prepare restored snapshot.",
                        code=409,
                    )

                now = self._now_utc()
                selected_model = dict(source_run.request_payload or {}).get(
                    "selected_model"
                )

                restored_run = self._db.insert_conversation_run(
                    session=session,
                    model=ConversationRun(
                        conversation_id=source_run.conversation_id,
                        project_id=source_run.project_id,
                        request_payload={
                            "trigger": "restore_snapshot",
                            "target": target,
                            "restored_from_run_id": source_run.id,
                            "selected_model": selected_model,
                        },
                        response_payload={
                            "content_plan_snapshot": restored_snapshot,
                            "restored_from_run_id": source_run.id,
                            "affected_sections": (
                                ["analysis"]
                                if target == "analysis"
                                else [f"social_posts.{target}"]
                                if target in {"linkedin", "facebook"}
                                else ["analysis", "social_posts"]
                            ),
                        },
                        status="completed",
                        started_at=now,
                        finished_at=now,
                        source_url=source_run.source_url,
                        platforms=list(source_run.platforms or []),
                    ),
                )

                conversation = self._db.get_conversation_by_id(
                    session=session, id=source_run.conversation_id
                )
                if conversation is not None:
                    self._db.update_conversation(
                        session=session,
                        model=Conversation(
                            id=conversation.id,
                            project_id=conversation.project_id,
                            title=conversation.title,
                            selected_model=self._normalize_model_name(
                                selected_model
                                if isinstance(selected_model, str)
                                else conversation.selected_model
                            ),
                            status="active",
                            message_count=conversation.message_count,
                            last_message_at=now,
                        ),
                    )

                project.last_active_at = now
                self._db.update_project(session=session, model=project)

                return ConversationServiceOutput(
                    status=True,
                    data={
                        "restored_run": restored_run,
                        "content_plan_snapshot": restored_snapshot,
                    },
                    error=None,
                    code=201,
                )
        except Exception as exc:
            logger.exception(
                "Failed to restore run snapshot",
                error=redact_message(str(exc)),
                run_id=inputs.run_id,
            )
            return ConversationServiceOutput(
                status=False,
                data=None,
                error=f"Unexpected error while restoring run snapshot: {redact_message(str(exc))}",
                code=500,
            )
