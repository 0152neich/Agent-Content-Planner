from __future__ import annotations

from pydantic import Field

from shared.base import BaseModel


class CrewSettings(BaseModel):
    """CrewAI behavior — defaults tuned to limit redundant LLM calls (token cost)."""

    verbose: bool = Field(
        default=False,
        description="Crew/agent console output. False saves noise; enable for local debugging.",
    )
    max_iter_analyzer: int = Field(
        default=5,
        ge=1,
        le=25,
        description="Max reasoning loops for the analyzer (has scraper tool). CrewAI default 25 is excessive.",
    )
    max_iter_llm_only: int = Field(
        default=2,
        ge=1,
        le=25,
        description="Max loops for agents without tools (strategist, copywriter, editor).",
    )
    max_retry_limit: int = Field(
        default=1,
        ge=0,
        le=10,
        description="LLM failure retries per agent step. Lower = fewer duplicate prompts on errors.",
    )
    rate_limit_max_requests: int = Field(
        default=3,
        ge=1,
        le=100,
        description="Max content-plan requests allowed per user in the sliding window.",
    )
    rate_limit_window_seconds: int = Field(
        default=30,
        ge=1,
        le=3600,
        description="Sliding window duration for content-plan per-user rate limiting.",
    )
    inflight_wait_timeout_seconds: int = Field(
        default=90,
        ge=5,
        le=600,
        description="How long duplicate requests wait for an in-flight identical run before timing out.",
    )
    result_cache_ttl_seconds: int = Field(
        default=120,
        ge=0,
        le=3600,
        description="Short-lived cache TTL for identical successful content-plan requests.",
    )
    router_stage1_model: str | None = Field(
        default="gpt-5.4",
        description=(
            "Optional explicit model for chat-router stage1 classifier (mini model). "
            "If unset or invalid, router falls back to default candidate selection."
        ),
    )
    router_stage2_model: str | None = Field(
        default="gpt-5.4",
        description=(
            "Optional explicit model for chat-router stage2 action resolver. "
            "If unset or invalid, router falls back to default candidate selection."
        ),
    )
    router_stage1_confidence_threshold: float = Field(
        default=0.55,
        ge=0.0,
        le=1.0,
        description=(
            "Minimum confidence required from stage1 classifier before executing action flow. "
            "Below this threshold, router should return CLARIFY."
        ),
    )
    router_stage2_confidence_threshold: float = Field(
        default=0.60,
        ge=0.0,
        le=1.0,
        description=(
            "Minimum confidence required from stage2 action resolver. "
            "Below this threshold, router should return CLARIFY."
        ),
    )
    enable_policy_gate: bool = Field(
        default=True,
        description=(
            "Enable deterministic policy gate for prompt/content safety and out-of-scope handling."
        ),
    )
    policy_mode: str = Field(
        default="hybrid",
        description="Policy mode. Supported: hybrid, strict, soft_review.",
    )
    out_of_scope_behavior: str = Field(
        default="refuse_suggest",
        description=(
            "Behavior for out-of-scope prompts. Supported: refuse_suggest, general_qa, clarify."
        ),
    )
