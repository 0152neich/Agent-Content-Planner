from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.tasks.analyze_task import create_analyze_task
from app.tasks.review_task import create_review_task
from app.tasks.strategize_task import create_strategize_task
from app.tasks.write_task import create_write_task
from domain.models.models import SocialPostsBundle


def test_analyze_task_prompt_contract() -> None:
    with patch("app.tasks.analyze_task.Task") as mocked_task:
        mocked_task.return_value = MagicMock()
        create_analyze_task(MagicMock(), "https://example.com/blog", "vi")

    kwargs = mocked_task.call_args.kwargs
    assert "Mandatory SOP workflow" in kwargs["description"]
    assert "Quality gates and acceptance criteria" in kwargs["description"]
    assert "supporting_claims" in kwargs["expected_output"]
    assert "confidence_score" in kwargs["expected_output"]


def test_strategize_task_prompt_contract() -> None:
    with patch("app.tasks.strategize_task.Task") as mocked_task:
        mocked_task.return_value = MagicMock()
        create_strategize_task(MagicMock(), "vi")

    kwargs = mocked_task.call_args.kwargs
    assert "must explicitly use these analysis fields" in kwargs["description"].lower()
    assert "platform differentiation is mandatory" in kwargs["description"].lower()
    assert "framework assignment rule" in kwargs["description"].lower()
    assert "pain/risk/time-loss" in kwargs["description"]
    assert "growth/opportunity/competitive-advantage" in kwargs["description"]
    assert "- Framework: PAS or AIDA" in kwargs["expected_output"]
    assert "LinkedIn Strategy" in kwargs["expected_output"]
    assert "Facebook Strategy" in kwargs["expected_output"]


def test_write_task_prompt_contract() -> None:
    with patch("app.tasks.write_task.Task") as mocked_task:
        mocked_task.return_value = MagicMock()
        create_write_task(MagicMock(), "vi")

    kwargs = mocked_task.call_args.kwargs
    assert kwargs["output_pydantic"] is SocialPostsBundle
    assert "EXACTLY 2 posts" in kwargs["description"]
    assert "Framework rule (mandatory)" in kwargs["description"]
    assert "Proof is mandatory" in kwargs["description"]
    assert "one single action only" in kwargs["description"]
    assert "max 2 lines" in kwargs["description"]
    assert "Platform differentiation is mandatory" in kwargs["description"]
    assert "Agitation/Interest, Solution/Value, and Proof" in kwargs["expected_output"]
    assert "Exactly one CTA per post" in kwargs["expected_output"]
    assert "Return EXACTLY one JSON object" in kwargs["expected_output"]


def test_review_task_prompt_contract() -> None:
    with patch("app.tasks.review_task.Task") as mocked_task:
        mocked_task.return_value = MagicMock()
        create_review_task(MagicMock(), "vi")

    kwargs = mocked_task.call_args.kwargs
    assert kwargs["output_pydantic"] is SocialPostsBundle
    assert "Quality Gates Checklist" in kwargs["description"]
    assert "Hook must fit within 2 lines" in kwargs["description"]
    assert "Exactly ONE clear CTA" in kwargs["description"]
    assert "must include at least one valid evidence point" in kwargs["description"]
    assert "Platform differentiation" in kwargs["description"]
    assert "fix inline" in kwargs["description"]
