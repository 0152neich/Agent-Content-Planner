from __future__ import annotations

import os
import re
from typing import Any

from crewai import Agent, Crew, Process, Task
from pydantic import Field

from app.services.chat_contracts import (
    ChatAction,
    ChatIntent,
    IntentContext,
    RecentChatMessage,
)
from infra.tools.tools import get_crewai_llm
from shared.base import BaseModel
from shared.logging import get_logger, redact_message
from shared.settings import Settings

logger = get_logger(__name__)


class _Stage1Output(BaseModel):
    intent_class: str
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    reason: str | None = None
    clarify_question: str | None = None


class _Stage2Output(BaseModel):
    action: str
    target_platform: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    needs_clarification: bool = False
    clarify_question: str | None = None
    reason: str | None = None


class ChatIntentRouter(BaseModel):
    _ROUTER_POLICY_VERSION = "v1"

    @staticmethod
    def _read_env_float(*, keys: tuple[str, ...], default: float) -> float:
        for key in keys:
            raw = os.getenv(key)
            if raw is None:
                continue
            try:
                return max(0.0, min(1.0, float(raw)))
            except Exception:
                continue
        return default

    @staticmethod
    def _resolve_router_model(
        *,
        configured_model: str | None,
        fallback_candidates: list[str],
    ) -> str:
        settings = Settings()
        allowed = set(settings.openai.allowed_models_list)
        configured = (
            configured_model.strip()
            if isinstance(configured_model, str) and configured_model.strip()
            else None
        )
        if configured and configured in allowed:
            return configured
        for candidate in fallback_candidates:
            if candidate in allowed:
                return candidate
        return settings.openai.model

    @staticmethod
    def _normalize_prompt(prompt: str) -> str:
        return " ".join(prompt.strip().split())

    @staticmethod
    def _stage1_confidence_threshold() -> float:
        env_override = ChatIntentRouter._read_env_float(
            keys=(
                "ROUTER_STAGE1_CONFIDENCE_THRESHOLD",
                "CREW__ROUTER_STAGE1_CONFIDENCE_THRESHOLD",
            ),
            default=-1.0,
        )
        if env_override >= 0.0:
            return env_override
        try:
            settings = Settings()
            raw = getattr(settings.crew, "router_stage1_confidence_threshold", 0.55)
        except Exception:
            raw = 0.55
        try:
            return max(0.0, min(1.0, float(raw)))
        except Exception:
            return 0.55

    @staticmethod
    def _stage2_confidence_threshold() -> float:
        env_override = ChatIntentRouter._read_env_float(
            keys=(
                "ROUTER_STAGE2_CONFIDENCE_THRESHOLD",
                "CREW__ROUTER_STAGE2_CONFIDENCE_THRESHOLD",
            ),
            default=-1.0,
        )
        if env_override >= 0.0:
            return env_override
        try:
            settings = Settings()
            raw = getattr(settings.crew, "router_stage2_confidence_threshold", 0.60)
        except Exception:
            raw = 0.60
        try:
            return max(0.0, min(1.0, float(raw)))
        except Exception:
            return 0.60

    @staticmethod
    def _is_strong_small_talk_prompt(prompt: str) -> bool:
        normalized = " ".join(prompt.strip().lower().split())
        if not normalized:
            return False
        return bool(
            re.fullmatch(
                r"(xin chào|chào|chao|hello|hi|hey|alo|ok|okay|thanks|thank you|cảm ơn|cam on)[!. ]*",
                normalized,
            )
        )

    def _extract_explicit_platform(self, prompt: str) -> str | None:
        normalized = f" {prompt.strip().lower()} "
        if any(marker in normalized for marker in (" facebook ", " fb ")):
            return "facebook"
        if any(marker in normalized for marker in (" linkedin ", " li ")):
            return "linkedin"
        return None

    @staticmethod
    def _is_multi_action_conflict_prompt(prompt: str) -> bool:
        normalized = " ".join(prompt.strip().lower().split())
        if not normalized:
            return False
        action_groups = [
            any(marker in normalized for marker in ("reanalyze", "phân tích lại", "phan tich lai")),
            any(
                marker in normalized
                for marker in (
                    "rewrite",
                    "viết lại",
                    "viet lai",
                    "chỉnh lại",
                    "chinh lai",
                )
            ),
            any(marker in normalized for marker in ("regenerate", "tạo lại", "tao lai", "làm mới", "lam moi")),
        ]
        return sum(1 for matched in action_groups if matched) >= 2

    @staticmethod
    def _clarify_template(ambiguity_type: str | None) -> str:
        normalized = (ambiguity_type or "").strip().lower()
        templates = {
            "missing_target": "Bạn muốn mình chỉnh phần nào cụ thể: Facebook, LinkedIn hay chiến lược?",
            "missing_scope": "Bạn muốn chỉnh phần nào: hook, body, CTA hay toàn bộ nội dung?",
            "missing_output_language": "Bạn muốn output bằng tiếng Việt, tiếng Anh hay song ngữ?",
            "multi_action_conflict": "Mình thấy có nhiều action cùng lúc. Bạn muốn ưu tiên 1 việc trước: reanalyze, rewrite hay regenerate?",
            "low_confidence_stage1": "Mình cần rõ hơn yêu cầu. Bạn muốn chỉnh Facebook, LinkedIn hay phần chiến lược?",
            "low_confidence_stage2": "Mình chưa đủ chắc về action cần làm. Bạn muốn mình chỉnh target nào và phạm vi nào?",
        }
        return templates.get(
            normalized,
            "Bạn muốn mình chỉnh phần nào cụ thể: Facebook, LinkedIn, hay chiến lược?",
        )

    @staticmethod
    def _resolve_ambiguity_type(
        *,
        ambiguity_type: str | None,
        reason: str | None,
    ) -> str:
        if isinstance(ambiguity_type, str) and ambiguity_type.strip():
            return ambiguity_type.strip().lower()
        reason_text = (reason or "").strip().lower()
        if "language" in reason_text or "tiếng" in reason_text:
            return "missing_output_language"
        if "scope" in reason_text or "phạm vi" in reason_text:
            return "missing_scope"
        if "target" in reason_text or "platform" in reason_text:
            return "missing_target"
        return "missing_target"

    @staticmethod
    def _normalize_platform(value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if normalized == "fb":
            return "facebook"
        if normalized == "li":
            return "linkedin"
        if normalized in {"facebook", "linkedin"}:
            return normalized
        return None

    @staticmethod
    def _coerce_intent_context(
        intent_context: IntentContext | dict[str, Any] | None,
    ) -> IntentContext | None:
        if intent_context is None:
            return None
        if isinstance(intent_context, IntentContext):
            return intent_context
        if isinstance(intent_context, dict):
            try:
                return IntentContext.model_validate(intent_context)
            except Exception:
                return None
        return None

    @staticmethod
    def _coerce_recent_messages(
        recent_messages: list[RecentChatMessage] | list[dict[str, Any]] | None,
    ) -> list[RecentChatMessage]:
        if not recent_messages:
            return []
        normalized: list[RecentChatMessage] = []
        for item in recent_messages:
            try:
                if isinstance(item, RecentChatMessage):
                    normalized.append(item)
                elif isinstance(item, dict):
                    normalized.append(RecentChatMessage.model_validate(item))
            except Exception:
                continue
        return normalized

    @classmethod
    def _render_recent_messages_block(
        cls,
        recent_messages: list[RecentChatMessage],
    ) -> str:
        if not recent_messages:
            return "No recent conversation history."
        lines: list[str] = []
        for idx, message in enumerate(recent_messages, start=1):
            content = cls._normalize_prompt(message.content)
            if not content:
                continue
            role = "user" if message.role.strip().lower() == "user" else "assistant"
            lines.append(f"{idx}. {role}: {content}")
        return "\n".join(lines) if lines else "No recent conversation history."

    @classmethod
    def _render_intent_context_block(cls, context: IntentContext | None) -> str:
        if context is None:
            return "No active editing context."
        return (
            f"last_action={context.last_action or 'none'}; "
            f"last_target_platform={context.last_target_platform or 'none'}; "
            f"last_language={context.last_language or 'none'}; "
            f"updated_at={context.updated_at or 'none'}"
        )

    @staticmethod
    def _stage1_model() -> str:
        settings = Settings()
        return ChatIntentRouter._resolve_router_model(
            configured_model=settings.crew.router_stage1_model,
            fallback_candidates=["gpt-5.4"],
        )

    @staticmethod
    def _stage2_model() -> str:
        settings = Settings()
        return ChatIntentRouter._resolve_router_model(
            configured_model=settings.crew.router_stage2_model,
            fallback_candidates=["gpt-5.4"],
        )

    def _run_stage1(
        self,
        *,
        prompt: str,
        intent_context: IntentContext | None,
        recent_messages: list[RecentChatMessage],
    ) -> _Stage1Output:
        try:
            llm = get_crewai_llm(model_override=self._stage1_model())
            agent = Agent(
                role="Chat Intent Classifier",
                goal="Classify whether this turn is action request, general QA, or needs clarification.",
                backstory=(
                    "You classify user turns in a content-editing assistant. "
                    "Prioritize latest prompt. Use prior context only as support."
                ),
                llm=llm,
                tools=[],
                allow_delegation=False,
                verbose=False,
                max_iter=1,
                max_retry_limit=0,
            )
            task = Task(
                description=(
                    "Classify the latest user prompt into one intent_class exactly:\n"
                    "- ACTION_REQUEST: user asks to modify/regenerate/analyze content output\n"
                    "- GENERAL_QA: casual talk or normal Q&A not requiring content-edit tools\n"
                    "- CLARIFY: user likely asks for an action but target/scope is ambiguous\n\n"
                    "Decision policy:\n"
                    "- Latest prompt has absolute priority.\n"
                    "- Active context and history are supporting signals only.\n"
                    "- If uncertain for action execution, choose CLARIFY and provide one short question.\n\n"
                    f"Active context:\n{self._render_intent_context_block(intent_context)}\n\n"
                    f"Recent conversation history:\n{self._render_recent_messages_block(recent_messages)}\n\n"
                    f"Latest prompt:\n{self._normalize_prompt(prompt)}\n"
                ),
                expected_output=(
                    "JSON with fields: intent_class, confidence, reason, clarify_question."
                ),
                agent=agent,
                output_pydantic=_Stage1Output,
            )
            crew = Crew(
                agents=[agent],
                tasks=[task],
                process=Process.sequential,
                verbose=False,
            )
            crew.kickoff(inputs={})
            result = task.output.pydantic
            if not isinstance(result, _Stage1Output):
                raise ValueError("Invalid stage1 routing output.")

            normalized_class = result.intent_class.strip().upper()
            if normalized_class not in {"ACTION_REQUEST", "GENERAL_QA", "CLARIFY"}:
                raise ValueError(f"Invalid stage1 intent_class '{normalized_class}'.")

            return result.model_copy(update={"intent_class": normalized_class})
        except Exception as exc:
            logger.warning("chat_intent_stage1_failed", error=redact_message(str(exc)))
            return _Stage1Output(
                intent_class="CLARIFY",
                confidence=0.0,
                reason="Stage1 classifier failed.",
                clarify_question="Bạn muốn mình hỗ trợ chỉnh phần nào cụ thể trong nội dung hiện tại?",
            )

    def _run_stage2(
        self,
        *,
        prompt: str,
        snapshot: dict[str, Any] | None,
        intent_context: IntentContext | None,
        recent_messages: list[RecentChatMessage],
    ) -> _Stage2Output:
        available_platforms: list[str] = []
        if isinstance(snapshot, dict):
            raw_posts = snapshot.get("social_posts")
            if isinstance(raw_posts, list):
                for post in raw_posts:
                    if not isinstance(post, dict):
                        continue
                    platform = self._normalize_platform(post.get("platform"))
                    if platform and platform not in available_platforms:
                        available_platforms.append(platform)
        try:
            llm = get_crewai_llm(model_override=self._stage2_model())
            agent = Agent(
                role="Chat Action Resolver",
                goal="Resolve exact workflow action for this turn.",
                backstory=(
                    "You map editing requests to concrete workflow actions. "
                    "Prioritize latest prompt; use context only to disambiguate."
                ),
                llm=llm,
                tools=[],
                allow_delegation=False,
                verbose=False,
                max_iter=1,
                max_retry_limit=0,
            )
            task = Task(
                description=(
                    "Return one workflow action from:\n"
                    "- FULL_REGENERATE\n"
                    "- REANALYZE_ONLY\n"
                    "- REWRITE_FACEBOOK_ONLY\n"
                    "- REWRITE_LINKEDIN_ONLY\n"
                    "- REWRITE_STRATEGY_ONLY\n"
                    "- CLARIFY\n"
                    "- GENERAL_QA\n\n"
                    "Decision policy:\n"
                    "- Latest prompt has highest priority.\n"
                    "- Use active context/history only when latest prompt is under-specified.\n"
                    "- If action target/scope is unclear, set needs_clarification=true and provide one short clarify_question.\n"
                    "- For facebook/linkedin rewrite, provide target_platform.\n\n"
                    f"Has snapshot: {'yes' if isinstance(snapshot, dict) else 'no'}\n"
                    f"Available platforms in snapshot: {', '.join(available_platforms) or 'none'}\n"
                    f"Active context:\n{self._render_intent_context_block(intent_context)}\n\n"
                    f"Recent conversation history:\n{self._render_recent_messages_block(recent_messages)}\n\n"
                    f"Latest prompt:\n{self._normalize_prompt(prompt)}\n"
                ),
                expected_output=(
                    "JSON with fields: action, target_platform, confidence, "
                    "needs_clarification, clarify_question, reason."
                ),
                agent=agent,
                output_pydantic=_Stage2Output,
            )
            crew = Crew(
                agents=[agent],
                tasks=[task],
                process=Process.sequential,
                verbose=False,
            )
            crew.kickoff(inputs={})
            result = task.output.pydantic
            if not isinstance(result, _Stage2Output):
                raise ValueError("Invalid stage2 routing output.")

            normalized_action = result.action.strip().upper()
            valid_actions = {member.value for member in ChatAction}
            if normalized_action not in valid_actions:
                raise ValueError(f"Invalid stage2 action '{normalized_action}'.")

            normalized_platform = self._normalize_platform(result.target_platform)
            needs_clarification = bool(result.needs_clarification)
            if normalized_action in {
                ChatAction.REWRITE_FACEBOOK_ONLY.value,
                ChatAction.REWRITE_LINKEDIN_ONLY.value,
            }:
                if normalized_action == ChatAction.REWRITE_FACEBOOK_ONLY.value:
                    normalized_platform = "facebook"
                else:
                    normalized_platform = "linkedin"
            if normalized_action == ChatAction.CLARIFY:
                needs_clarification = True

            return result.model_copy(
                update={
                    "action": normalized_action,
                    "target_platform": normalized_platform,
                    "needs_clarification": needs_clarification,
                }
            )
        except Exception as exc:
            logger.warning("chat_intent_stage2_failed", error=redact_message(str(exc)))
            return _Stage2Output(
                action=ChatAction.CLARIFY.value,
                confidence=0.0,
                needs_clarification=True,
                clarify_question="Bạn muốn mình chỉnh Facebook, LinkedIn hay phần chiến lược?",
                reason="Stage2 resolver failed.",
            )

    def _build_clarify_intent(
        self,
        *,
        prompt: str,
        confidence: float,
        reason: str | None,
        clarify_question: str | None,
        ambiguity_type: str | None,
        routing_metadata: dict[str, Any],
    ) -> ChatIntent:
        resolved_ambiguity_type = self._resolve_ambiguity_type(
            ambiguity_type=ambiguity_type,
            reason=reason,
        )
        question = (
            clarify_question.strip()
            if isinstance(clarify_question, str) and clarify_question.strip()
            else self._clarify_template(resolved_ambiguity_type)
        )
        routing_payload = dict(routing_metadata or {})
        routing_payload["ambiguity_type"] = resolved_ambiguity_type
        return ChatIntent(
            action=ChatAction.CLARIFY,
            normalized_prompt=self._normalize_prompt(prompt),
            confidence=max(0.0, min(1.0, confidence)),
            reason=reason or "Clarification required before execution.",
            needs_clarification=True,
            clarify_question=question,
            routing_metadata=routing_payload,
        )

    def route(
        self,
        prompt: str,
        snapshot: dict[str, Any] | None = None,
        intent_context: IntentContext | dict[str, Any] | None = None,
        recent_messages: list[RecentChatMessage] | list[dict[str, Any]] | None = None,
    ) -> ChatIntent:
        normalized_prompt = self._normalize_prompt(prompt)
        coerced_context = self._coerce_intent_context(intent_context)
        coerced_recent_messages = self._coerce_recent_messages(recent_messages)
        stage1_threshold = self._stage1_confidence_threshold()
        stage2_threshold = self._stage2_confidence_threshold()
        base_metadata: dict[str, Any] = {
            "router_policy_version": self._ROUTER_POLICY_VERSION,
            "stage1_confidence_threshold": stage1_threshold,
            "stage2_confidence_threshold": stage2_threshold,
        }

        if self._is_strong_small_talk_prompt(normalized_prompt):
            return ChatIntent(
                action=ChatAction.GENERAL_QA,
                normalized_prompt=normalized_prompt,
                confidence=1.0,
                reason="Forced GENERAL_QA by strong small-talk resolver.",
                routing_metadata={
                    **base_metadata,
                    "resolver": {"forced_general_qa": True, "source": "small_talk"},
                },
            )

        stage1 = self._run_stage1(
            prompt=normalized_prompt,
            intent_context=coerced_context,
            recent_messages=coerced_recent_messages,
        )
        stage1_metadata = {
            "intent_class": stage1.intent_class,
            "confidence": stage1.confidence,
            "reason": stage1.reason,
        }
        routing_metadata = {**base_metadata, "stage1": stage1_metadata}

        if (
            stage1.intent_class == "ACTION_REQUEST"
            and stage1.confidence < stage1_threshold
        ):
            return self._build_clarify_intent(
                prompt=normalized_prompt,
                confidence=stage1.confidence,
                reason=(
                    stage1.reason
                    or "Stage1 confidence below configured threshold for action routing."
                ),
                clarify_question=stage1.clarify_question,
                ambiguity_type="low_confidence_stage1",
                routing_metadata=routing_metadata,
            )

        if stage1.intent_class == "GENERAL_QA":
            return ChatIntent(
                action=ChatAction.GENERAL_QA,
                normalized_prompt=normalized_prompt,
                confidence=max(0.0, min(1.0, stage1.confidence)),
                reason=stage1.reason or "Classified as GENERAL_QA by stage1.",
                routing_metadata=routing_metadata,
            )

        if stage1.intent_class == "CLARIFY":
            return self._build_clarify_intent(
                prompt=normalized_prompt,
                confidence=stage1.confidence,
                reason=stage1.reason,
                clarify_question=stage1.clarify_question,
                ambiguity_type="missing_target",
                routing_metadata=routing_metadata,
            )

        if self._is_multi_action_conflict_prompt(normalized_prompt):
            return self._build_clarify_intent(
                prompt=normalized_prompt,
                confidence=stage1.confidence,
                reason="Prompt contains multiple conflicting actions.",
                clarify_question=None,
                ambiguity_type="multi_action_conflict",
                routing_metadata=routing_metadata,
            )

        stage2 = self._run_stage2(
            prompt=normalized_prompt,
            snapshot=snapshot,
            intent_context=coerced_context,
            recent_messages=coerced_recent_messages,
        )
        stage2_metadata = {
            "action": stage2.action,
            "target_platform": stage2.target_platform,
            "confidence": stage2.confidence,
            "needs_clarification": stage2.needs_clarification,
            "reason": stage2.reason,
        }
        routing_metadata["stage2"] = stage2_metadata

        if stage2.confidence < stage2_threshold:
            return self._build_clarify_intent(
                prompt=normalized_prompt,
                confidence=stage2.confidence,
                reason=(
                    stage2.reason
                    or "Stage2 confidence below configured threshold for action routing."
                ),
                clarify_question=stage2.clarify_question,
                ambiguity_type="low_confidence_stage2",
                routing_metadata=routing_metadata,
            )

        # Confidence gate is the primary blocker. If stage2 confidence is already
        # above threshold, do not force CLARIFY solely from needs_clarification.
        if stage2.needs_clarification:
            resolver_meta = dict(routing_metadata.get("resolver") or {})
            resolver_meta["needs_clarification_ignored"] = True
            routing_metadata["resolver"] = resolver_meta

        try:
            action = ChatAction(stage2.action)
        except Exception:
            return self._build_clarify_intent(
                prompt=normalized_prompt,
                confidence=0.0,
                reason=f"Unsupported action from stage2: {stage2.action}",
                clarify_question=stage2.clarify_question,
                ambiguity_type="missing_scope",
                routing_metadata=routing_metadata,
            )

        if action == ChatAction.CLARIFY:
            return self._build_clarify_intent(
                prompt=normalized_prompt,
                confidence=stage2.confidence,
                reason=stage2.reason,
                clarify_question=stage2.clarify_question,
                ambiguity_type="missing_scope",
                routing_metadata=routing_metadata,
            )

        explicit_platform = self._extract_explicit_platform(normalized_prompt)
        if explicit_platform and action in {
            ChatAction.REWRITE_FACEBOOK_ONLY,
            ChatAction.REWRITE_LINKEDIN_ONLY,
        }:
            if explicit_platform == "facebook":
                action = ChatAction.REWRITE_FACEBOOK_ONLY
                stage2.target_platform = "facebook"
            elif explicit_platform == "linkedin":
                action = ChatAction.REWRITE_LINKEDIN_ONLY
                stage2.target_platform = "linkedin"
            routing_metadata["resolver"] = {
                "platform_override_applied": True,
                "explicit_platform": explicit_platform,
            }

        return ChatIntent(
            action=action,
            target_platform=stage2.target_platform,
            normalized_prompt=normalized_prompt,
            confidence=max(0.0, min(1.0, stage2.confidence)),
            reason=stage2.reason or "Resolved by stage2 action resolver.",
            needs_clarification=False,
            clarify_question=None,
            routing_metadata=routing_metadata,
        )
