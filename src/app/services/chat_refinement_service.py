from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from hashlib import sha256
import json
from threading import Event, Lock
from time import monotonic
from typing import Deque

from pydantic import PrivateAttr

from app.services.chat_contracts import (
    ChatAction,
    ChatIntent,
    ChatRefinementInput,
    ChatRefinementOutput,
    IntentContext,
    RecentChatMessage,
)
from app.services.chat_intent_router import ChatIntentRouter
from app.services.chat_policy_service import (
    ChatPolicyService,
    PolicyDecision,
    PolicySeverity,
)
from app.workflows.chat_action_workflow import (
    ChatActionWorkflowInput,
    ChatActionWorkflowService,
)
from app.workflows.chat_snapshot import ContentPlanSnapshot, apply_partial_update
from shared.base import BaseModel
from shared.language_policy import LanguagePolicyService
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
    _policy_service: ChatPolicyService = PrivateAttr(default_factory=ChatPolicyService)
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
        intent_context: IntentContext | None,
        recent_messages: list[RecentChatMessage],
        snapshot: dict[str, object] | None,
    ) -> str:
        context_payload = (
            intent_context.model_dump(mode="json") if intent_context is not None else {}
        )
        history_payload = "\n".join(
            [
                "|".join(
                    [
                        cls._normalize_text(message.role),
                        cls._normalize_text(message.content),
                    ]
                )
                for message in recent_messages
            ]
        )
        history_digest = sha256(history_payload.encode("utf-8")).hexdigest()
        try:
            snapshot_payload = (
                json.dumps(snapshot, ensure_ascii=False, sort_keys=True)
                if isinstance(snapshot, dict)
                else ""
            )
        except Exception:
            snapshot_payload = ""
        snapshot_digest = sha256(snapshot_payload.encode("utf-8")).hexdigest()
        payload = "|".join(
            [
                owner_user_id,
                conversation_id,
                cls._normalize_text(prompt),
                cls._normalize_text(selected_model),
                cls._normalize_text(str(context_payload.get("last_target_platform"))),
                cls._normalize_text(str(context_payload.get("last_action"))),
                cls._normalize_text(str(context_payload.get("last_language"))),
                history_digest,
                snapshot_digest,
            ]
        )
        return sha256(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def _parse_snapshot(
        payload: dict[str, object] | None,
        *,
        owner_user_id: str,
        conversation_id: str,
    ) -> ContentPlanSnapshot | None:
        if payload is None:
            return None
        try:
            return ContentPlanSnapshot.from_payload(payload)
        except Exception as exc:
            logger.warning(
                "chat_refinement_snapshot_invalid",
                owner_user_id=owner_user_id,
                conversation_id=conversation_id,
                error=redact_message(str(exc)),
            )
            return None

    @staticmethod
    def _snapshot_version(snapshot: dict[str, object] | None) -> str:
        try:
            payload = (
                json.dumps(snapshot, ensure_ascii=False, sort_keys=True)
                if isinstance(snapshot, dict)
                else ""
            )
        except Exception:
            payload = ""
        return sha256(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def _context_version(intent_context: IntentContext | None) -> str | None:
        if intent_context is None:
            return None
        updated_at = (intent_context.updated_at or "").strip()
        return updated_at or None

    @staticmethod
    def _policy_enabled() -> bool:
        try:
            return bool(getattr(Settings().crew, "enable_policy_gate", True))
        except Exception:
            return True

    @staticmethod
    def _out_of_scope_behavior() -> str:
        try:
            value = getattr(Settings().crew, "out_of_scope_behavior", "refuse_suggest")
        except Exception:
            value = "refuse_suggest"
        normalized = str(value or "").strip().lower()
        if normalized in {"refuse_suggest", "general_qa", "clarify"}:
            return normalized
        return "refuse_suggest"

    @staticmethod
    def _policy_mode() -> str:
        try:
            value = getattr(Settings().crew, "policy_mode", "hybrid")
        except Exception:
            value = "hybrid"
        normalized = str(value or "").strip().lower()
        if normalized in {"hybrid", "strict", "soft_review"}:
            return normalized
        return "hybrid"

    @staticmethod
    def _snapshot_text_blob(snapshot: ContentPlanSnapshot | None) -> str:
        if snapshot is None:
            return ""
        parts: list[str] = []
        try:
            parts.extend(
                [
                    snapshot.analysis.core_message,
                    snapshot.analysis.value_proposition,
                    snapshot.analysis.primary_cta,
                ]
            )
            for post in snapshot.social_posts:
                parts.extend([post.hook, post.body_content, post.call_to_action])
            strategy = str(snapshot.meta.get("strategy", "")).strip() if snapshot.meta else ""
            if strategy:
                parts.append(strategy)
        except Exception:
            return ""
        return " ".join(part.strip() for part in parts if isinstance(part, str) and part.strip())

    def _build_policy_refusal_result(
        self,
        *,
        prompt: str,
        snapshot: ContentPlanSnapshot | None,
        reason: str,
        reply: str,
        decision: PolicyDecision,
        severity: str,
        snapshot_version: str,
        context_version: str | None,
    ) -> ChatRefinementOutput:
        intent = ChatIntent(
            action=ChatAction.GENERAL_QA,
            normalized_prompt=self._normalize_text(prompt),
            confidence=1.0,
            reason=reason,
            routing_metadata={},
        )
        metadata = {
            "language_used": LanguagePolicyService().detect_target_language(prompt),
            "policy_decision": decision.value,
            "policy_reason": reason,
            "policy_severity": severity,
            "snapshot_version": snapshot_version,
            "context_version": context_version,
        }
        return ChatRefinementOutput(
            status=True,
            assistant_text=reply,
            intent=intent,
            affected_sections=[],
            content_plan_snapshot=(
                snapshot.model_dump(mode="json") if snapshot is not None else None
            ),
            metadata=metadata,
            error=None,
            code=200,
        )

    def _apply_input_policy_gate(
        self,
        *,
        prompt: str,
        snapshot: ContentPlanSnapshot | None,
        snapshot_version: str,
        context_version: str | None,
    ) -> ChatRefinementOutput | None:
        if not self._policy_enabled():
            return None
        policy_mode = self._policy_mode()
        policy_result = self._policy_service.evaluate_user_prompt(prompt)
        if policy_result.decision == PolicyDecision.ALLOW:
            return None
        if policy_mode == "soft_review" and policy_result.decision == PolicyDecision.OUT_OF_SCOPE:
            return None
        if policy_mode == "strict" and policy_result.decision == PolicyDecision.OUT_OF_SCOPE:
            return self._build_policy_refusal_result(
                prompt=prompt,
                snapshot=snapshot,
                reason=f"{policy_result.reason} (strict mode)",
                reply=policy_result.suggested_reply
                or "Yêu cầu nằm ngoài phạm vi trợ lý content marketing.",
                decision=PolicyDecision.HARD_BLOCK,
                severity=PolicySeverity.HIGH.value,
                snapshot_version=snapshot_version,
                context_version=context_version,
            )
        if policy_result.decision == PolicyDecision.HARD_BLOCK:
            return self._build_policy_refusal_result(
                prompt=prompt,
                snapshot=snapshot,
                reason=policy_result.reason,
                reply=policy_result.suggested_reply
                or "Mình không thể hỗ trợ yêu cầu này.",
                decision=policy_result.decision,
                severity=policy_result.severity.value,
                snapshot_version=snapshot_version,
                context_version=context_version,
            )
        behavior = self._out_of_scope_behavior()
        if behavior == "general_qa":
            return None
        if behavior == "clarify":
            return ChatRefinementOutput(
                status=True,
                assistant_text=(
                    "Bạn muốn mình hỗ trợ trong phạm vi content marketing nào: "
                    "chỉnh Facebook, LinkedIn hay chiến lược?"
                ),
                intent=ChatIntent(
                    action=ChatAction.CLARIFY,
                    normalized_prompt=self._normalize_text(prompt),
                    confidence=1.0,
                    reason=policy_result.reason,
                    needs_clarification=True,
                    clarify_question=(
                        "Bạn muốn mình hỗ trợ trong phạm vi content marketing nào?"
                    ),
                    routing_metadata={
                        "policy_decision": policy_result.decision.value,
                        "policy_reason": policy_result.reason,
                        "policy_severity": policy_result.severity.value,
                    },
                ),
                affected_sections=[],
                content_plan_snapshot=(
                    snapshot.model_dump(mode="json") if snapshot is not None else None
                ),
                metadata={
                    "language_used": LanguagePolicyService().detect_target_language(
                        prompt
                    ),
                    "policy_decision": policy_result.decision.value,
                    "policy_reason": policy_result.reason,
                    "policy_severity": policy_result.severity.value,
                    "snapshot_version": snapshot_version,
                    "context_version": context_version,
                },
                error=None,
                code=200,
            )
        return self._build_policy_refusal_result(
            prompt=prompt,
            snapshot=snapshot,
            reason=policy_result.reason,
            reply=policy_result.suggested_reply
            or (
                "Yêu cầu này chưa đúng phạm vi trợ lý content marketing. "
                "Bạn có thể yêu cầu chỉnh Facebook, LinkedIn hoặc chiến lược."
            ),
            decision=policy_result.decision,
            severity=policy_result.severity.value,
            snapshot_version=snapshot_version,
            context_version=context_version,
        )

    def _validate_intent_coherence(
        self,
        *,
        prompt: str,
        intent: ChatIntent,
        snapshot: ContentPlanSnapshot | None,
        snapshot_version: str,
        context_version: str | None,
    ) -> ChatRefinementOutput | None:
        rewrite_actions = {
            ChatAction.REWRITE_FACEBOOK_ONLY,
            ChatAction.REWRITE_LINKEDIN_ONLY,
            ChatAction.REWRITE_STRATEGY_ONLY,
        }
        if intent.action in rewrite_actions and snapshot is None:
            return ChatRefinementOutput(
                status=False,
                assistant_text=None,
                intent=intent,
                metadata={
                    "validator_status": "failed",
                    "validator_reason": "snapshot_missing_for_rewrite",
                    "snapshot_version": snapshot_version,
                    "context_version": context_version,
                },
                error=(
                    "No content snapshot found for this project yet. "
                    "Please run content generation first."
                ),
                code=409,
            )
        if snapshot is None:
            return None
        if intent.action == ChatAction.REWRITE_FACEBOOK_ONLY:
            if intent.target_platform not in {None, "facebook"}:
                return ChatRefinementOutput(
                    status=True,
                    assistant_text="Bạn muốn chỉnh Facebook hay LinkedIn?",
                    intent=ChatIntent(
                        action=ChatAction.CLARIFY,
                        normalized_prompt=self._normalize_text(prompt),
                        confidence=0.0,
                        reason="Action/platform mismatch for facebook rewrite.",
                        needs_clarification=True,
                        clarify_question="Bạn muốn chỉnh Facebook hay LinkedIn?",
                        routing_metadata={"ambiguity_type": "missing_target"},
                    ),
                    metadata={
                        "validator_status": "failed",
                        "validator_reason": "action_platform_mismatch",
                        "snapshot_version": snapshot_version,
                        "context_version": context_version,
                    },
                    code=200,
                )
            # If facebook post does not exist yet, rewrite flow will create one
            # from current snapshot analysis.
        if intent.action == ChatAction.REWRITE_LINKEDIN_ONLY:
            if intent.target_platform not in {None, "linkedin"}:
                return ChatRefinementOutput(
                    status=True,
                    assistant_text="Bạn muốn chỉnh Facebook hay LinkedIn?",
                    intent=ChatIntent(
                        action=ChatAction.CLARIFY,
                        normalized_prompt=self._normalize_text(prompt),
                        confidence=0.0,
                        reason="Action/platform mismatch for linkedin rewrite.",
                        needs_clarification=True,
                        clarify_question="Bạn muốn chỉnh Facebook hay LinkedIn?",
                        routing_metadata={"ambiguity_type": "missing_target"},
                    ),
                    metadata={
                        "validator_status": "failed",
                        "validator_reason": "action_platform_mismatch",
                        "snapshot_version": snapshot_version,
                        "context_version": context_version,
                    },
                    code=200,
                )
            # If linkedin post does not exist yet, rewrite flow will create one
            # from current snapshot analysis.
        return None

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
            intent_context=inputs.intent_context,
            recent_messages=inputs.recent_messages,
            snapshot=inputs.snapshot,
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
            snapshot = self._parse_snapshot(
                inputs.snapshot,
                owner_user_id=inputs.owner_user_id,
                conversation_id=inputs.conversation_id,
            )
            snapshot_version = self._snapshot_version(inputs.snapshot)
            context_version = self._context_version(inputs.intent_context)

            input_policy_result = self._apply_input_policy_gate(
                prompt=inputs.prompt,
                snapshot=snapshot,
                snapshot_version=snapshot_version,
                context_version=context_version,
            )
            if input_policy_result is not None:
                final_result = input_policy_result
                self._set_cached_result(request_key=request_key, result=final_result)
                return final_result

            intent = self._intent_router.route(
                prompt=inputs.prompt,
                snapshot=inputs.snapshot,
                intent_context=inputs.intent_context,
                recent_messages=inputs.recent_messages,
            )
            logger.info(
                "chat_refinement_routing_resolved",
                owner_user_id=inputs.owner_user_id,
                conversation_id=inputs.conversation_id,
                stage1_class=intent.routing_metadata.get("stage1", {}).get(
                    "intent_class"
                ),
                stage2_action=intent.routing_metadata.get("stage2", {}).get("action"),
                final_action=intent.action.value,
                confidence=float(intent.confidence),
                ambiguity_type=intent.routing_metadata.get("ambiguity_type"),
            )

            coherence_error = self._validate_intent_coherence(
                prompt=inputs.prompt,
                intent=intent,
                snapshot=snapshot,
                snapshot_version=snapshot_version,
                context_version=context_version,
            )
            if coherence_error is not None:
                final_result = coherence_error
                return final_result

            if intent.action == ChatAction.CLARIFY:
                clarify_message = (
                    intent.clarify_question
                    if isinstance(intent.clarify_question, str)
                    and intent.clarify_question.strip()
                    else "Bạn muốn mình chỉnh phần nào cụ thể?"
                )
                final_result = ChatRefinementOutput(
                    status=True,
                    assistant_text=clarify_message,
                    intent=intent,
                    affected_sections=[],
                    content_plan_snapshot=(
                        snapshot.model_dump(mode="json")
                        if snapshot is not None
                        else None
                    ),
                    metadata={
                        "language_used": LanguagePolicyService().detect_target_language(
                            inputs.prompt
                        ),
                        "routing": dict(intent.routing_metadata or {}),
                        "policy_decision": "ALLOW",
                        "policy_reason": "Prompt allowed by policy gate.",
                        "policy_severity": "LOW",
                        "validator_status": "passed",
                        "validator_reason": "coherent",
                        "snapshot_version": snapshot_version,
                        "context_version": context_version,
                    },
                    error=None,
                    code=200,
                )
                self._set_cached_result(request_key=request_key, result=final_result)
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
                metadata=dict(workflow_result.metadata or {}),
                error=None,
                code=200,
            )
            final_result.metadata["routing"] = dict(intent.routing_metadata or {})
            final_result.metadata["policy_decision"] = "ALLOW"
            final_result.metadata["policy_reason"] = "Prompt allowed by policy gate."
            final_result.metadata["policy_severity"] = "LOW"
            final_result.metadata["validator_status"] = "passed"
            final_result.metadata["validator_reason"] = "coherent"
            final_result.metadata["snapshot_version"] = snapshot_version
            final_result.metadata["context_version"] = context_version

            if self._policy_enabled():
                output_blob = " ".join(
                    [
                        str(workflow_result.assistant_text or ""),
                        self._snapshot_text_blob(next_snapshot),
                    ]
                ).strip()
                output_policy = self._policy_service.evaluate_generated_text(output_blob)
                if output_policy.decision == PolicyDecision.HARD_BLOCK:
                    final_result = self._build_policy_refusal_result(
                        prompt=inputs.prompt,
                        snapshot=snapshot,
                        reason=output_policy.reason,
                        reply=output_policy.suggested_reply
                        or "Mình không thể trả về nội dung này vì lý do an toàn.",
                        decision=output_policy.decision,
                        severity=output_policy.severity.value,
                        snapshot_version=snapshot_version,
                        context_version=context_version,
                    )
                    final_result.intent = intent
                    final_result.metadata["routing"] = dict(intent.routing_metadata or {})
                    final_result.metadata["validator_status"] = "passed"
                    final_result.metadata["validator_reason"] = "coherent"
                    self._set_cached_result(request_key=request_key, result=final_result)
                    return final_result

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
