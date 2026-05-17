from __future__ import annotations

from pydantic import Field

from shared.base import BaseModel


class CelerySettings(BaseModel):
    broker_url: str = Field(default="redis://localhost:6379/0")
    result_backend: str = Field(default="redis://localhost:6379/1")
    timezone: str = Field(default="UTC")
    enable_beat: bool = Field(default=True)
    due_scan_limit: int = Field(default=100, ge=1, le=1000)
