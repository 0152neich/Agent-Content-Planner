from __future__ import annotations

from crewai import Agent

from infra.tools.tools import get_crewai_llm
from shared.settings import Settings
from shared.settings.models import CrewSettings


def create_strategist_agent(
    model_override: str | None = None,
    *,
    crew_settings: CrewSettings | None = None,
) -> Agent:
    c = crew_settings or Settings().crew
    return Agent(
        role="Cross-Channel Content Strategy Director",
        goal=(
            "Translate analysis into executable strategy for LinkedIn and Facebook, "
            "with clear conversion direction, platform differentiation, and risk control."
        ),
        backstory=(
            "You are a strategy lead operating with strict SOP quality gates. "
            "Your recommendations must explicitly use intent, funnel stage, audience pains, "
            "value proposition, CTA logic, and risk flags. Output must be "
            "implementation-ready for copywriting without follow-up clarification."
        ),
        llm=get_crewai_llm(model_override=model_override),
        tools=[],
        allow_delegation=False,
        verbose=c.verbose,
        max_iter=c.max_iter_llm_only,
        max_retry_limit=c.max_retry_limit,
    )
