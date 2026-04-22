from __future__ import annotations

from collections.abc import Callable
from enum import Enum
from typing import Any

from pydantic import Field

from shared.base import BaseModel


class ChatAction(str, Enum):
    FULL_REGENERATE = "FULL_REGENERATE"
    REANALYZE_ONLY = "REANALYZE_ONLY"
    REWRITE_FACEBOOK_ONLY = "REWRITE_FACEBOOK_ONLY"
    REWRITE_LINKEDIN_ONLY = "REWRITE_LINKEDIN_ONLY"
    REWRITE_STRATEGY_ONLY = "REWRITE_STRATEGY_ONLY"
    CLARIFY = "CLARIFY"
    GENERAL_QA = "GENERAL_QA"


class ChatIntent(BaseModel):
    action: ChatAction
    target_platform: str | None = None
    normalized_prompt: str
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    reason: str | None = None


class ChatRefinementInput(BaseModel):
    owner_user_id: str
    conversation_id: str
    prompt: str
    selected_model: str | None = None
    source_url: str | None = None
    snapshot: dict[str, Any] | None = None
    assistant_token_callback: Callable[[str], None] | None = None


class ChatRefinementOutput(BaseModel):
    status: bool
    assistant_text: str | None = None
    intent: ChatIntent | None = None
    affected_sections: list[str] = Field(default_factory=list)
    content_plan_snapshot: dict[str, Any] | None = None
    error: str | None = None
    code: int = 200
