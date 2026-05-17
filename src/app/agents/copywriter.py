from __future__ import annotations

from crewai import Agent

from infra.tools.tools import get_crewai_llm
from shared.settings import Settings
from shared.settings.models import CrewSettings


def create_copywriter_agent(
    model_override: str | None = None,
    *,
    crew_settings: CrewSettings | None = None,
) -> Agent:
    c = crew_settings or Settings().crew
    return Agent(
        role="Senior Conversion Copywriter",
        goal=(
            "Write high-performing, channel-native social posts from approved strategy and "
            "analysis, with framework compliance before style, clear hooks, practical value, "
            "and one conversion-oriented CTA."
        ),
        backstory=(
            "You are an execution-focused copywriter with strict acceptance criteria. "
            "You must preserve strategic intent, follow assigned PAS/AIDA structure, "
            "differentiate tone and structure per platform, and avoid generic AI-like phrasing. "
            "Every output must be ready to "
            "publish after QA review."
        ),
        llm=get_crewai_llm(model_override=model_override),
        tools=[],
        allow_delegation=False,
        verbose=c.verbose,
        max_iter=c.max_iter_llm_only,
        max_retry_limit=c.max_retry_limit,
    )
