from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.tasks.analyze_task import create_analyze_task
from domain.models.models import DraftAnalysis


def test_create_analyze_task_enforces_evidence_only_schema() -> None:
    with patch("app.tasks.analyze_task.Task") as mocked_task:
        mocked_task.return_value = MagicMock()
        create_analyze_task(MagicMock(), "https://example.com/blog", "vi")

    kwargs = mocked_task.call_args.kwargs
    assert kwargs["output_pydantic"] is DraftAnalysis
    assert "supporting_claims" in kwargs["expected_output"]
    assert "evidence_excerpt" in kwargs["expected_output"]
    assert "confidence_score" in kwargs["expected_output"]
    assert "evidence-only mode" in kwargs["description"]
