from __future__ import annotations

from pydantic import Field

from shared.base import BaseModel


class AutopostSettings(BaseModel):
    enable_quality_gate: bool = Field(default=True)
    quality_min_score: float = Field(default=0.6, ge=0.0, le=1.0)
    require_review_on_quality_failure: bool = Field(default=True)
    enable_duplicate_guard: bool = Field(default=True)
    duplicate_window_minutes: int = Field(default=15, ge=1, le=1440)
    publish_timeout_seconds: int = Field(default=20, ge=1, le=300)
