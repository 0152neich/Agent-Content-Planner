from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.agents.analyzer import create_analyzer_agent
from app.agents.copywriter import create_copywriter_agent
from app.agents.editor import create_editor_agent
from app.agents.strategist import create_strategist_agent


def test_analyzer_agent_prompt_contract() -> None:
    with (
        patch("app.agents.analyzer.Agent") as mocked_agent,
        patch("app.agents.analyzer.get_crewai_llm", return_value=MagicMock()),
        patch("app.agents.analyzer.get_scraper_tool", return_value=MagicMock()),
    ):
        mocked_agent.return_value = MagicMock()
        create_analyzer_agent()

    kwargs = mocked_agent.call_args.kwargs
    assert kwargs["role"] == "Senior Content Intelligence Analyst"
    assert "evidence-grounded" in kwargs["goal"]
    assert "quality gates" in kwargs["backstory"]
    assert "missing_information" in kwargs["backstory"]


def test_strategist_agent_prompt_contract() -> None:
    with (
        patch("app.agents.strategist.Agent") as mocked_agent,
        patch("app.agents.strategist.get_crewai_llm", return_value=MagicMock()),
    ):
        mocked_agent.return_value = MagicMock()
        create_strategist_agent()

    kwargs = mocked_agent.call_args.kwargs
    assert kwargs["role"] == "Cross-Channel Content Strategy Director"
    assert "LinkedIn and Facebook" in kwargs["goal"]
    assert "strict SOP" in kwargs["backstory"]
    assert "risk flags" in kwargs["backstory"]


def test_copywriter_agent_prompt_contract() -> None:
    with (
        patch("app.agents.copywriter.Agent") as mocked_agent,
        patch("app.agents.copywriter.get_crewai_llm", return_value=MagicMock()),
    ):
        mocked_agent.return_value = MagicMock()
        create_copywriter_agent()

    kwargs = mocked_agent.call_args.kwargs
    assert kwargs["role"] == "Senior Conversion Copywriter"
    assert "channel-native social posts" in kwargs["goal"]
    assert "framework compliance before style" in kwargs["goal"]
    assert "acceptance criteria" in kwargs["backstory"]
    assert "follow assigned PAS/AIDA structure" in kwargs["backstory"]
    assert "avoid generic AI-like phrasing" in kwargs["backstory"]


def test_editor_agent_prompt_contract() -> None:
    with (
        patch("app.agents.editor.Agent") as mocked_agent,
        patch("app.agents.editor.get_crewai_llm", return_value=MagicMock()),
    ):
        mocked_agent.return_value = MagicMock()
        create_editor_agent()

    kwargs = mocked_agent.call_args.kwargs
    assert kwargs["role"] == "Strict QA Content Editor"
    assert "quality gates" in kwargs["goal"]
    assert "proof integrity" in kwargs["goal"]
    assert "hard fail semantics" in kwargs["backstory"]
    assert "correct it inline" in kwargs["backstory"]
