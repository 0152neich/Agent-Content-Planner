from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from hashlib import sha256
from threading import Event, Lock
from time import monotonic
from typing import Deque

from pydantic import PrivateAttr

from app.services.chat_contracts import (
    ChatAction,
    ChatRefinementInput,
    ChatRefinementOutput,
)
from app.services.chat_intent_router import ChatIntentRouter
from app.workflows.chat_action_workflow import (
    ChatActionWorkflowInput,
    ChatActionWorkflowService,
)
from app.workflows.chat_snapshot import ContentPlanSnapshot, apply_partial_update
from shared.base import BaseModel
from shared.logging import get_logger, redact_message
from shared.settings import Settings

logger = get_logger(__name__)


@dataclass
class _InFlightChatRequest:
    event: Event = field(default_factory=Event)
    result: ChatRefinementOutput | None = None


@dataclass
class _CachedChatResult:
    result: ChatRefinementOutput
    expires_at: float


class ChatRefinementService(BaseModel):
    _intent_router: ChatIntentRouter = PrivateAttr(default_factory=ChatIntentRouter)
    _workflow_service: ChatActionWorkflowService = PrivateAttr(
        default_factory=ChatActionWorkflowService
    )
    _state_lock: Lock = PrivateAttr(default_factory=Lock)
    _inflight_requests: dict[str, _InFlightChatRequest] = PrivateAttr(
        default_factory=dict
    )
    _cached_results: dict[str, _CachedChatResult] = PrivateAttr(default_factory=dict)
    _rate_limit_windows: dict[str, Deque[float]] = PrivateAttr(
        default_factory=lambda: defaultdict(deque)
    )

    @staticmethod
    def _normalize_text(value: str | None) -> str:
        if value is None:
            return ""
        return " ".join(value.strip().split())

    @classmethod
    def _build_request_key(
        cls,
        *,
        owner_user_id: str,
        conversation_id: str,
        prompt: str,
        selected_model: str | None,
    ) -> str:
        payload = "|".join(
            [
                owner_user_id,
                conversation_id,
                cls._normalize_text(prompt),
                cls._normalize_text(selected_model),
            ]
        )
        return sha256(payload.encode("utf-8")).hexdigest()

    def _apply_rate_limit(self, owner_user_id: str) -> ChatRefinementOutput | None:
        crew_cfg = Settings().crew
        if crew_cfg.rate_limit_max_requests <= 0:
            return None

        now = monotonic()
        window = float(crew_cfg.rate_limit_window_seconds)
        with self._state_lock:
            hits = self._rate_limit_windows[owner_user_id]
            while hits and now - hits[0] > window:
                hits.popleft()
            if len(hits) >= crew_cfg.rate_limit_max_requests:
                retry_after = max(1, int(window - (now - hits[0])))
                return ChatRefinementOutput(
                    status=False,
                    assistant_text=None,
                    error=f"Too many requests. Please retry after {retry_after}s.",
                    code=429,
                )
            hits.append(now)
        return None

    def _get_cached_result(self, request_key: str) -> ChatRefinementOutput | None:
        now = monotonic()
        with self._state_lock:
            expired = [
                key
                for key, cache_entry in self._cached_results.items()
                if cache_entry.expires_at <= now
            ]
            for key in expired:
                self._cached_results.pop(key, None)

            cache_entry = self._cached_results.get(request_key)
            if cache_entry is None:
                return None
            return cache_entry.result

    def _set_cached_result(
        self, request_key: str, result: ChatRefinementOutput
    ) -> None:
        crew_cfg = Settings().crew
        if not result.status or crew_cfg.result_cache_ttl_seconds <= 0:
            return
        with self._state_lock:
            self._cached_results[request_key] = _CachedChatResult(
                result=result,
                expires_at=monotonic() + float(crew_cfg.result_cache_ttl_seconds),
            )

    def _acquire_inflight_slot(
        self, request_key: str
    ) -> tuple[_InFlightChatRequest, bool]:
        with self._state_lock:
            existing = self._inflight_requests.get(request_key)
            if existing is not None:
                return existing, False
            entry = _InFlightChatRequest()
            self._inflight_requests[request_key] = entry
            return entry, True

    def _release_inflight_slot(
        self,
        request_key: str,
        entry: _InFlightChatRequest,
        result: ChatRefinementOutput,
    ) -> None:
        with self._state_lock:
            entry.result = result
            entry.event.set()
            self._inflight_requests.pop(request_key, None)

    def process(self, inputs: ChatRefinementInput) -> ChatRefinementOutput:
        rate_limit_error = self._apply_rate_limit(inputs.owner_user_id)
        if rate_limit_error is not None:
            return rate_limit_error

        request_key = self._build_request_key(
            owner_user_id=inputs.owner_user_id,
            conversation_id=inputs.conversation_id,
            prompt=inputs.prompt,
            selected_model=inputs.selected_model,
        )
        cached = self._get_cached_result(request_key=request_key)
        if cached is not None:
            logger.info(
                "chat_refinement_cache_hit",
                owner_user_id=inputs.owner_user_id,
                conversation_id=inputs.conversation_id,
            )
            return cached

        inflight_entry, is_owner = self._acquire_inflight_slot(request_key=request_key)
        if not is_owner:
            logger.info(
                "chat_refinement_inflight_dedup_wait",
                owner_user_id=inputs.owner_user_id,
                conversation_id=inputs.conversation_id,
            )
            waited = inflight_entry.event.wait(
                timeout=float(Settings().crew.inflight_wait_timeout_seconds)
            )
            if not waited:
                return ChatRefinementOutput(
                    status=False,
                    assistant_text=None,
                    error="An identical request is currently running. Please retry shortly.",
                    code=409,
                )
            if inflight_entry.result is None:
                return ChatRefinementOutput(
                    status=False,
                    assistant_text=None,
                    error="In-flight request completed without result.",
                    code=500,
                )
            return inflight_entry.result

        final_result = ChatRefinementOutput(
            status=False,
            assistant_text=None,
            error="Unexpected chat refinement error.",
            code=500,
        )
        try:
            snapshot = (
                ContentPlanSnapshot.from_payload(inputs.snapshot)
                if inputs.snapshot is not None
                else None
            )
            intent = self._intent_router.route(
                prompt=inputs.prompt,
                snapshot=inputs.snapshot,
            )

            if (
                intent.action
                in {
                    ChatAction.REWRITE_FACEBOOK_ONLY,
                    ChatAction.REWRITE_LINKEDIN_ONLY,
                    ChatAction.REWRITE_STRATEGY_ONLY,
                }
                and snapshot is None
            ):
                final_result = ChatRefinementOutput(
                    status=False,
                    assistant_text=None,
                    intent=intent,
                    error=(
                        "No content snapshot found for this project yet. "
                        "Please run content generation first."
                    ),
                    code=409,
                )
                return final_result

            workflow_result = self._workflow_service.process(
                ChatActionWorkflowInput(
                    action=intent.action,
                    prompt=inputs.prompt,
                    selected_model=inputs.selected_model,
                    source_url=inputs.source_url
                    or (snapshot.source_url if snapshot else None),
                    snapshot=snapshot,
                    owner_user_id=inputs.owner_user_id,
                    assistant_token_callback=inputs.assistant_token_callback,
                )
            )
            if not workflow_result.status:
                final_result = ChatRefinementOutput(
                    status=False,
                    assistant_text=None,
                    intent=intent,
                    error=workflow_result.error or "Chat refinement workflow failed.",
                    code=workflow_result.code,
                )
                return final_result

            next_snapshot: ContentPlanSnapshot | None = snapshot
            affected_sections = workflow_result.affected_sections
            if intent.action == ChatAction.FULL_REGENERATE:
                if workflow_result.patch.full_snapshot is None:
                    final_result = ChatRefinementOutput(
                        status=False,
                        assistant_text=None,
                        intent=intent,
                        error="FULL_REGENERATE did not return a full snapshot.",
                        code=500,
                    )
                    return final_result
                next_snapshot, affected_sections = apply_partial_update(
                    snapshot=workflow_result.patch.full_snapshot,
                    patch=workflow_result.patch,
                    action=ChatAction.FULL_REGENERATE,
                )
            elif snapshot is None and intent.action == ChatAction.REANALYZE_ONLY:
                if workflow_result.patch.analysis is None:
                    final_result = ChatRefinementOutput(
                        status=False,
                        assistant_text=None,
                        intent=intent,
                        error="REANALYZE_ONLY did not return analysis patch.",
                        code=500,
                    )
                    return final_result
                source_url = (inputs.source_url or "").strip()
                if not source_url:
                    final_result = ChatRefinementOutput(
                        status=False,
                        assistant_text=None,
                        intent=intent,
                        error="Missing source URL for initial analysis snapshot.",
                        code=409,
                    )
                    return final_result
                bootstrap_snapshot = ContentPlanSnapshot(
                    source_url=source_url,
                    analysis=workflow_result.patch.analysis,
                    social_posts=[],
                    meta={},
                )
                next_snapshot, affected_sections = apply_partial_update(
                    snapshot=bootstrap_snapshot,
                    patch=workflow_result.patch,
                    action=ChatAction.REANALYZE_ONLY,
                )
            elif snapshot is not None:
                next_snapshot, affected_sections = apply_partial_update(
                    snapshot=snapshot,
                    patch=workflow_result.patch,
                    action=intent.action,
                )

            final_result = ChatRefinementOutput(
                status=True,
                assistant_text=workflow_result.assistant_text,
                intent=intent,
                affected_sections=affected_sections,
                content_plan_snapshot=(
                    next_snapshot.model_dump(mode="json")
                    if next_snapshot is not None
                    else None
                ),
                error=None,
                code=200,
            )
            self._set_cached_result(request_key=request_key, result=final_result)
            return final_result
        except Exception as exc:
            logger.exception(
                "chat_refinement_service_failed",
                owner_user_id=inputs.owner_user_id,
                conversation_id=inputs.conversation_id,
                error=redact_message(str(exc)),
            )
            final_result = ChatRefinementOutput(
                status=False,
                assistant_text=None,
                error=redact_message(str(exc)),
                code=500,
            )
            return final_result
        finally:
            self._release_inflight_slot(
                request_key=request_key,
                entry=inflight_entry,
                result=final_result,
            )
