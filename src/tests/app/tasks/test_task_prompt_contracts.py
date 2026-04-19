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
    assert "LinkedIn Strategy" in kwargs["expected_output"]
    assert "Facebook Strategy" in kwargs["expected_output"]


def test_write_task_prompt_contract() -> None:
    with patch("app.tasks.write_task.Task") as mocked_task:
        mocked_task.return_value = MagicMock()
        create_write_task(MagicMock(), "vi")

    kwargs = mocked_task.call_args.kwargs
    assert kwargs["output_pydantic"] is SocialPostsBundle
    assert "EXACTLY 2 posts" in kwargs["description"]
    assert "Platform differentiation is mandatory" in kwargs["description"]
    assert "Return EXACTLY one JSON object" in kwargs["expected_output"]


def test_review_task_prompt_contract() -> None:
    with patch("app.tasks.review_task.Task") as mocked_task:
        mocked_task.return_value = MagicMock()
        create_review_task(MagicMock(), "vi")

    kwargs = mocked_task.call_args.kwargs
    assert kwargs["output_pydantic"] is SocialPostsBundle
    assert "Hard quality gates" in kwargs["description"]
    assert "Platform differentiation" in kwargs["description"]
    assert "fix inline" in kwargs["description"]
