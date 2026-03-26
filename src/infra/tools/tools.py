from __future__ import annotations

from crewai import LLM as CrewAILLM

from infra.tools.scraper import BS4ScraperTool
from infra.tools.scraper import FirecrawlScraperTool
from shared.settings import Settings

settings = Settings()


class UnsupportedModelError(ValueError):
    """Raised when selected model is invalid or unsupported by current provider."""


def get_scraper_tool():
    """Factory function to return scraper tool from SCRAPER_PROVIDER."""
    provider = settings.scraper_provider.lower()
    if provider == "firecrawl":
        return FirecrawlScraperTool(settings=settings)
    if provider == "bs4":
        return BS4ScraperTool()
    raise ValueError(
        f"Invalid SCRAPER_PROVIDER value: '{provider}'. Must be 'firecrawl' or 'bs4'."
    )


def _provider_from_model_name(model_name: str) -> str:
    normalized = model_name.strip().lower()
    if normalized.startswith("gpt-"):
        return "openai"
    if normalized.startswith("claude-"):
        return "anthropic"
    if normalized.startswith("gemini-"):
        return "gemini"
    raise UnsupportedModelError(
        "Unsupported model prefix. Supported families: gpt-*, claude-*, gemini-*."
    )


def _validate_model_against_allowlist(
    *,
    selected_model: str,
    allowed_models: list[str],
    provider: str,
) -> None:
    if not allowed_models:
        return
    if selected_model not in allowed_models:
        raise UnsupportedModelError(
            f"Model '{selected_model}' is not allowed for provider '{provider}'. "
            f"Allowed models: {', '.join(allowed_models)}."
        )


def resolve_llm_target(model_override: str | None = None) -> tuple[str, str]:
    requested_model = (model_override or "").strip()
    if requested_model:
        selected_provider = _provider_from_model_name(requested_model)
        if selected_provider == "openai":
            _validate_model_against_allowlist(
                selected_model=requested_model,
                allowed_models=settings.openai.allowed_models_list,
                provider=selected_provider,
            )
        elif selected_provider == "anthropic":
            _validate_model_against_allowlist(
                selected_model=requested_model,
                allowed_models=settings.anthropic.allowed_models_list,
                provider=selected_provider,
            )
        elif selected_provider == "gemini":
            _validate_model_against_allowlist(
                selected_model=requested_model,
                allowed_models=settings.gemini.allowed_models_list,
                provider=selected_provider,
            )
        return selected_provider, requested_model

    selected_provider = settings.llm_provider.strip().lower()
    if selected_provider == "openai":
        selected_model = settings.openai.model
        _validate_model_against_allowlist(
            selected_model=selected_model,
            allowed_models=settings.openai.allowed_models_list,
            provider=selected_provider,
        )
        return selected_provider, selected_model
    if selected_provider == "anthropic":
        selected_model = settings.anthropic.model
        _validate_model_against_allowlist(
            selected_model=selected_model,
            allowed_models=settings.anthropic.allowed_models_list,
            provider=selected_provider,
        )
        return selected_provider, selected_model
    if selected_provider == "gemini":
        selected_model = settings.gemini.model
        _validate_model_against_allowlist(
            selected_model=selected_model,
            allowed_models=settings.gemini.allowed_models_list,
            provider=selected_provider,
        )
        return selected_provider, selected_model
    raise UnsupportedModelError(
        f"Unsupported LLM provider '{selected_provider}'. "
        "Supported providers: openai, anthropic, gemini."
    )


def get_crewai_llm(model_override: str | None = None) -> CrewAILLM:
    """Return a CrewAI LLM instance with optional model override from FE."""
    provider, selected_model = resolve_llm_target(model_override=model_override)
    if provider == "openai":
        return CrewAILLM(
            model=selected_model,
            api_key=settings.openai.api_key,
            base_url=settings.openai.api_base,
            temperature=settings.openai.temperature,
            timeout=settings.openai.request_timeout,
        )
    if provider == "anthropic":
        return CrewAILLM(
            model=selected_model,
            api_key=settings.anthropic.api_key,
            temperature=settings.anthropic.temperature,
            timeout=settings.anthropic.request_timeout,
        )
    if provider == "gemini":
        return CrewAILLM(
            model=selected_model,
            api_key=settings.gemini.api_key,
            temperature=settings.gemini.temperature,
            timeout=settings.gemini.request_timeout,
        )
    raise ValueError(
        f"Invalid provider '{provider}'. Must be 'openai' or 'anthropic' or 'gemini'."
    )
