from __future__ import annotations

from pydantic import field_validator

from shared.base import BaseModel


def _normalize_csv(value: str) -> str:
    return ",".join(item.strip() for item in value.split(",") if item.strip())


class OpenAISettings(BaseModel):
    model: str = "gpt-4o-mini"
    allowed_models: str = (
        "gpt-5.4,gpt-5.1,gpt-5,gpt-4.1,gpt-4o,gpt-4o-mini,gpt-4-turbo,gpt-3.5-turbo"
    )
    api_key: str
    api_base: str
    temperature: float = 0.3
    request_timeout: int = 60

    @field_validator("model")
    @classmethod
    def normalize_model(cls, value: str) -> str:
        return value.strip()

    @field_validator("allowed_models")
    @classmethod
    def normalize_allowed_models(cls, value: str) -> str:
        return _normalize_csv(value)

    @property
    def allowed_models_list(self) -> list[str]:
        return [item.strip() for item in self.allowed_models.split(",") if item.strip()]


class AnthropicSettings(BaseModel):
    model: str = "claude-3-5-sonnet-20240620"
    allowed_models: str = "claude-sonnet-4-6,claude-opus-4-6,claude-haiku-4-5,claude-3-5-sonnet-20240620,claude-3-opus-20240229,claude-3-haiku-20240307"
    api_key: str
    temperature: float = 0.3
    request_timeout: int = 60

    @field_validator("model")
    @classmethod
    def normalize_model(cls, value: str) -> str:
        return value.strip()

    @field_validator("allowed_models")
    @classmethod
    def normalize_allowed_models(cls, value: str) -> str:
        return _normalize_csv(value)

    @property
    def allowed_models_list(self) -> list[str]:
        return [item.strip() for item in self.allowed_models.split(",") if item.strip()]


class GeminiSettings(BaseModel):
    model: str = "gemini-2.5-flash"
    allowed_models: str = "gemini-2.5-pro,gemini-2.5-flash,gemini-2.5-flash-lite,gemini-3-pro-preview,gemini-3-flash-preview,gemini-1.5-pro,gemini-1.5-flash"
    api_key: str
    temperature: float = 0.3
    request_timeout: int = 60

    @field_validator("model")
    @classmethod
    def normalize_model(cls, value: str) -> str:
        return value.strip()

    @field_validator("allowed_models")
    @classmethod
    def normalize_allowed_models(cls, value: str) -> str:
        return _normalize_csv(value)

    @property
    def allowed_models_list(self) -> list[str]:
        return [item.strip() for item in self.allowed_models.split(",") if item.strip()]
