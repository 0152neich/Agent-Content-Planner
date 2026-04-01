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
