from __future__ import annotations

from pydantic import Field
from shared.base import BaseModel


class FirecrawlSettings(BaseModel):
    api_key: str = Field(..., description="The API key for the Firecrawl API")
