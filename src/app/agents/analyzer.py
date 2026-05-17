from __future__ import annotations

from crewai import Agent

from infra.tools.tools import get_crewai_llm
from infra.tools.tools import get_scraper_tool
from shared.settings import Settings
from shared.settings.models import CrewSettings


def create_analyzer_agent(
    model_override: str | None = None,
    *,
    crew_settings: CrewSettings | None = None,
) -> Agent:
    c = crew_settings or Settings().crew
    return Agent(
        role="Senior Content Intelligence Analyst",
        goal=(
            "Produce Marketing Ops analysis that is evidence-grounded, conversion-aware, "
            "and directly usable for channel strategy decisions."
        ),
        backstory=(
            "You are an evidence-first analyst with strict quality gates and acceptance "
            "criteria. You must map each strong claim to explicit source evidence, avoid "
            "unsupported inference, and surface uncertainty through missing_information "
            "instead of guessing."
        ),
        llm=get_crewai_llm(model_override=model_override),
        tools=[get_scraper_tool()],
        allow_delegation=False,
        verbose=c.verbose,
        max_iter=c.max_iter_analyzer,
        max_retry_limit=c.max_retry_limit,
    )
