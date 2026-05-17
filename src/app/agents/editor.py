from __future__ import annotations

from crewai import Agent

from infra.tools.tools import get_crewai_llm
from shared.settings import Settings
from shared.settings.models import CrewSettings


def create_editor_agent(
    model_override: str | None = None,
    *,
    crew_settings: CrewSettings | None = None,
) -> Agent:
    c = crew_settings or Settings().crew
    return Agent(
        role="Strict QA Content Editor",
        goal=(
            "Enforce final quality gates on social posts: language correctness, platform fit, "
            "strategy alignment, proof integrity, and publish-ready clarity."
        ),
        backstory=(
            "You are a strict quality gate enforcer with hard fail semantics. "
            "If a draft fails any gate, you must correct it inline and return a final "
            "version in one pass. You never ask for a full rewrite loop when a direct edit "
            "can resolve the issue."
        ),
        llm=get_crewai_llm(model_override=model_override),
        tools=[],
        # Sequential pipeline requires deterministic inline editing.
        allow_delegation=False,
        verbose=c.verbose,
        max_iter=c.max_iter_llm_only,
        max_retry_limit=c.max_retry_limit,
    )
