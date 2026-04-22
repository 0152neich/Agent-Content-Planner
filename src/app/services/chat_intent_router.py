from __future__ import annotations

import re
import unicodedata
from typing import Any

from crewai import Agent, Crew, Process, Task
from pydantic import Field

from app.services.chat_contracts import ChatAction, ChatIntent
from infra.tools.tools import get_crewai_llm
from shared.base import BaseModel
from shared.logging import get_logger, redact_message
from shared.settings import Settings

logger = get_logger(__name__)


class _LLMIntentOutput(BaseModel):
    action: str
    target_platform: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    reason: str | None = None


class ChatIntentRouter(BaseModel):
    @staticmethod
    def _normalize_prompt(prompt: str) -> str:
        return " ".join(prompt.strip().lower().split())

    @staticmethod
    def _strip_accents(text: str) -> str:
        normalized = unicodedata.normalize("NFD", text)
        without_marks = "".join(
            ch for ch in normalized if unicodedata.category(ch) != "Mn"
        )
        return without_marks.replace("đ", "d").replace("Đ", "D")

    @classmethod
    def _contains_any(cls, text: str, keywords: list[str]) -> bool:
        folded = cls._strip_accents(text)
        return any(keyword in text or keyword in folded for keyword in keywords)

    @staticmethod
    def _is_question_like(text: str) -> bool:
        return "?" in text or bool(
            re.search(r"\b(giai thich|la gi|vi sao|tai sao|how|what|why|help)\b", text)
        )

    def _rule_based_intent(self, prompt: str) -> ChatIntent | None:
        text = self._normalize_prompt(prompt)

        if self._contains_any(
            text,
            [
                "full regenerate",
                "regenerate all",
                "lam lai toan bo",
                "viet lai toan bo",
                "tao lai toan bo",
            ],
        ):
            return ChatIntent(
                action=ChatAction.FULL_REGENERATE,
                normalized_prompt=text,
                confidence=0.96,
                reason="Matched full regenerate keywords.",
            )

        if self._contains_any(
            text, ["chien luoc", "strategy", "angle", "huong noi dung"]
        ):
            return ChatIntent(
                action=ChatAction.REWRITE_STRATEGY_ONLY,
                normalized_prompt=text,
                confidence=0.9,
                reason="Matched strategy keywords.",
            )

        if self._contains_any(
            text, ["phan tich", "reanalyze", "analyze again", "danh gia lai"]
        ):
            return ChatIntent(
                action=ChatAction.REANALYZE_ONLY,
                normalized_prompt=text,
                confidence=0.88,
                reason="Matched reanalyze keywords.",
            )

        rewrite_keywords = [
            "sua",
            "viet lai",
            "dieu chinh",
            "rewrite",
            "toi uu",
            "rut gon",
        ]
        if self._contains_any(text, ["facebook", "fb"]) and self._contains_any(
            text, rewrite_keywords
        ):
            return ChatIntent(
                action=ChatAction.REWRITE_FACEBOOK_ONLY,
                target_platform="facebook",
                normalized_prompt=text,
                confidence=0.9,
                reason="Matched facebook + rewrite keywords.",
            )

        if self._contains_any(text, ["linkedin", "li"]) and self._contains_any(
            text, rewrite_keywords
        ):
            return ChatIntent(
                action=ChatAction.REWRITE_LINKEDIN_ONLY,
                target_platform="linkedin",
                normalized_prompt=text,
                confidence=0.9,
                reason="Matched linkedin + rewrite keywords.",
            )

        if self._is_question_like(text):
            return ChatIntent(
                action=ChatAction.CLARIFY,
                normalized_prompt=text,
                confidence=0.72,
                reason="Prompt looks like clarify/general question.",
            )
        return None

    def _fallback_llm_intent(self, prompt: str) -> ChatIntent:
        try:
            llm = get_crewai_llm(model_override=Settings().openai.model)
            router_agent = Agent(
                role="Intent Router",
                goal="Classify user refinement request into one fixed chat action.",
                backstory=(
                    "You are a strict intent classifier for Vietnamese and English prompts. "
                    "Return only a valid action."
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
                    "Classify this prompt into exactly one action:\n"
                    "- FULL_REGENERATE\n"
                    "- REANALYZE_ONLY\n"
                    "- REWRITE_FACEBOOK_ONLY\n"
                    "- REWRITE_LINKEDIN_ONLY\n"
                    "- REWRITE_STRATEGY_ONLY\n"
                    "- CLARIFY\n"
                    "- GENERAL_QA\n"
                    f"\nPrompt: {prompt}\n"
                    "Return target_platform only for facebook/linkedin rewrite."
                ),
                expected_output="JSON with fields: action, target_platform, confidence, reason.",
                agent=router_agent,
                output_pydantic=_LLMIntentOutput,
            )
            crew = Crew(
                agents=[router_agent],
                tasks=[task],
                process=Process.sequential,
                verbose=False,
            )
            crew.kickoff(inputs={"prompt": prompt})
            output = task.output.pydantic
            if not isinstance(output, _LLMIntentOutput):
                raise ValueError("Invalid LLM intent output payload.")

            action_value = output.action.strip().upper()
            if action_value not in {member.value for member in ChatAction}:
                raise ValueError(f"Invalid action '{action_value}' from LLM.")

            return ChatIntent(
                action=ChatAction(action_value),
                target_platform=output.target_platform,
                normalized_prompt=self._normalize_prompt(prompt),
                confidence=max(0.0, min(1.0, float(output.confidence))),
                reason=output.reason or "LLM fallback classification.",
            )
        except Exception as exc:
            logger.warning(
                "chat_intent_fallback_failed",
                error=redact_message(str(exc)),
            )
            return ChatIntent(
                action=ChatAction.GENERAL_QA,
                normalized_prompt=self._normalize_prompt(prompt),
                confidence=0.4,
                reason="Fallback to GENERAL_QA after LLM classify failure.",
            )

    def route(self, prompt: str, snapshot: dict[str, Any] | None = None) -> ChatIntent:
        del snapshot
        intent = self._rule_based_intent(prompt)
        if intent is not None:
            return intent
        return self._fallback_llm_intent(prompt)
