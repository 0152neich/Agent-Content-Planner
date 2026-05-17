from __future__ import annotations

from dotenv import find_dotenv
from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings

from .models import AuthSettings
from .models import AutopostSettings
from .models import CrewSettings
from .models import CelerySettings
from .models import FirecrawlSettings
from .models import OpenAISettings
from .models import AnthropicSettings
from .models import GeminiSettings
from .models import PostgresSettings

# Load .env so BaseSettings can read from it (e.g. when running outside Docker).
load_dotenv(find_dotenv(".env"), override=True)


class Settings(BaseSettings):
    auth: AuthSettings = Field(default_factory=AuthSettings)
    autopost: AutopostSettings = Field(default_factory=AutopostSettings)
    crew: CrewSettings = Field(default_factory=CrewSettings)
    celery: CelerySettings = Field(default_factory=CelerySettings)

    # Scraper
    firecrawl: FirecrawlSettings

    # LLM
    openai: OpenAISettings
    anthropic: AnthropicSettings
    gemini: GeminiSettings

    # Database (optional; use for SQLDatabase config)
    postgres: PostgresSettings | None = None

    scraper_provider: str

    class Config:
        env_nested_delimiter = "__"
