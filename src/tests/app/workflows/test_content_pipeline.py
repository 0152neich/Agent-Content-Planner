"""Unit tests for ContentPlanningService (content_pipeline)."""

from __future__ import annotations

from contextlib import ExitStack
from unittest.mock import MagicMock, patch

import pytest

from app.workflows.content_pipeline import (
    ContentPlanningInput,
    ContentPlanningService,
)
from domain.models.models import ContentPlanOutput, DraftAnalysis, SocialPostsBundle
from shared.exceptions import UnsupportedModelError

# ---------------------------------------------------------------------------
# Patch definitions
# ---------------------------------------------------------------------------

# 1) Agent-factory patches — prevent real LLM/network setup.
_AGENT_PATCHES = [
    patch(
        "app.workflows.content_pipeline.create_analyzer_agent", return_value=MagicMock()
    ),
    patch(
        "app.workflows.content_pipeline.create_strategist_agent",
        return_value=MagicMock(),
    ),
    patch(
        "app.workflows.content_pipeline.create_copywriter_agent",
        return_value=MagicMock(),
    ),
    patch(
        "app.workflows.content_pipeline.create_editor_agent", return_value=MagicMock()
    ),
]

# 2) Task-factory patches — prevent Task(agent=MagicMock) Pydantic validation.
_TASK_PATCHES = [
    patch(
        "app.workflows.content_pipeline.create_analyze_task", return_value=MagicMock()
    ),
    patch(
        "app.workflows.content_pipeline.create_strategize_task",
        return_value=MagicMock(),
    ),
    patch("app.workflows.content_pipeline.create_write_task", return_value=MagicMock()),
    patch(
        "app.workflows.content_pipeline.create_review_task", return_value=MagicMock()
    ),
]

_ALL_PATCHES = _AGENT_PATCHES + _TASK_PATCHES


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_capture_crew(
    fake_analysis: DraftAnalysis,
    fake_posts: SocialPostsBundle,
    captured_tasks: list,
    captured_inputs: dict | None = None,
):
    """Factory: returns a Crew side_effect that captures tasks and wires fake
    task outputs, optionally capturing kickoff inputs."""

    def _crew_factory(*args, **kwargs):
        captured_tasks[:] = kwargs.get("tasks", [])
        mock_crew = MagicMock()

        def _kickoff(inputs: dict | None = None, **_kw):
            if captured_inputs is not None and inputs is not None:
                captured_inputs.update(inputs)
            for t in captured_tasks:
                if not getattr(t, "output", None):
                    t.output = MagicMock()
            if len(captured_tasks) >= 4:
                captured_tasks[0].output.pydantic = fake_analysis
                captured_tasks[3].output.pydantic = fake_posts

        mock_crew.kickoff.side_effect = _kickoff
        return mock_crew

    return _crew_factory


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def service() -> ContentPlanningService:
    return ContentPlanningService()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_process_returns_success_and_assembles_output_when_crew_succeeds(
    service: ContentPlanningService,
    content_planning_input: ContentPlanningInput,
    fake_draft_analysis: DraftAnalysis,
    fake_social_posts_bundle: SocialPostsBundle,
) -> None:
    """process() returns status=True and a correct ContentPlanOutput on success."""
    captured_tasks: list = []

    crew_patch = patch(
        "app.workflows.content_pipeline.Crew",
        side_effect=_make_capture_crew(
            fake_draft_analysis, fake_social_posts_bundle, captured_tasks
        ),
    )

    with ExitStack() as stack:
        for p in _ALL_PATCHES:
            stack.enter_context(p)
        stack.enter_context(crew_patch)
        result = service.process(content_planning_input)

    assert result.status is True
    assert result.error is None
    assert isinstance(result.data, ContentPlanOutput)
    assert result.data.source_url == content_planning_input.url
    assert result.data.analysis == fake_draft_analysis
    assert result.data.social_posts == fake_social_posts_bundle.posts


def test_process_passes_additional_context_into_crew_inputs(
    service: ContentPlanningService,
    content_planning_input_with_context: ContentPlanningInput,
    fake_draft_analysis: DraftAnalysis,
    fake_social_posts_bundle: SocialPostsBundle,
) -> None:
    """process() passes url and additional_context into crew.kickoff(inputs=...)."""
    captured_tasks: list = []
    captured_inputs: dict = {}

    crew_patch = patch(
        "app.workflows.content_pipeline.Crew",
        side_effect=_make_capture_crew(
            fake_draft_analysis,
            fake_social_posts_bundle,
            captured_tasks,
            captured_inputs,
        ),
    )

    with ExitStack() as stack:
        for p in _ALL_PATCHES:
            stack.enter_context(p)
        stack.enter_context(crew_patch)
        service.process(content_planning_input_with_context)

    assert captured_inputs.get("url") == content_planning_input_with_context.url
    assert captured_inputs.get("additional_context") == "Focus on B2B audience."


def test_process_passes_target_language_into_task_factories(
    service: ContentPlanningService,
    content_planning_input_with_context: ContentPlanningInput,
    fake_draft_analysis: DraftAnalysis,
    fake_social_posts_bundle: SocialPostsBundle,
) -> None:
    captured_tasks: list = []
    crew_patch = patch(
        "app.workflows.content_pipeline.Crew",
        side_effect=_make_capture_crew(
            fake_draft_analysis, fake_social_posts_bundle, captured_tasks
        ),
    )

    with ExitStack() as stack:
        stack.enter_context(
            patch(
                "app.workflows.content_pipeline.create_analyzer_agent",
                return_value=MagicMock(),
            )
        )
        stack.enter_context(
            patch(
                "app.workflows.content_pipeline.create_strategist_agent",
                return_value=MagicMock(),
            )
        )
        stack.enter_context(
            patch(
                "app.workflows.content_pipeline.create_copywriter_agent",
                return_value=MagicMock(),
            )
        )
        stack.enter_context(
            patch(
                "app.workflows.content_pipeline.create_editor_agent",
                return_value=MagicMock(),
            )
        )
        mocked_analyze = stack.enter_context(
            patch(
                "app.workflows.content_pipeline.create_analyze_task",
                return_value=MagicMock(),
            )
        )
        mocked_strategize = stack.enter_context(
            patch(
                "app.workflows.content_pipeline.create_strategize_task",
                return_value=MagicMock(),
            )
        )
        mocked_write = stack.enter_context(
            patch(
                "app.workflows.content_pipeline.create_write_task",
                return_value=MagicMock(),
            )
        )
        mocked_review = stack.enter_context(
            patch(
                "app.workflows.content_pipeline.create_review_task",
                return_value=MagicMock(),
            )
        )
        stack.enter_context(crew_patch)
        service.process(content_planning_input_with_context)

    assert mocked_analyze.call_args.args[2] == "en"
    assert mocked_strategize.call_args.args[1] == "en"
    assert mocked_write.call_args.args[1] == "en"
    assert mocked_review.call_args.args[1] == "en"


def test_process_uses_empty_string_when_additional_context_is_none(
    service: ContentPlanningService,
    content_planning_input: ContentPlanningInput,
    fake_draft_analysis: DraftAnalysis,
    fake_social_posts_bundle: SocialPostsBundle,
) -> None:
    """process() sends '' as additional_context when input.additional_context is None."""
    captured_tasks: list = []
    captured_inputs: dict = {}

    crew_patch = patch(
        "app.workflows.content_pipeline.Crew",
        side_effect=_make_capture_crew(
            fake_draft_analysis,
            fake_social_posts_bundle,
            captured_tasks,
            captured_inputs,
        ),
    )

    with ExitStack() as stack:
        for p in _ALL_PATCHES:
            stack.enter_context(p)
        stack.enter_context(crew_patch)
        service.process(content_planning_input)

    assert captured_inputs.get("url") == content_planning_input.url
    assert captured_inputs.get("additional_context") == ""


def test_process_passes_selected_model_to_agent_factories(
    service: ContentPlanningService,
    content_planning_input: ContentPlanningInput,
    fake_draft_analysis: DraftAnalysis,
    fake_social_posts_bundle: SocialPostsBundle,
) -> None:
    """process() forwards selected_model to all agent factories."""
    captured_tasks: list = []
    selected_model = "claude-sonnet-4-6"
    input_with_model = ContentPlanningInput(
        url=content_planning_input.url,
        additional_context=content_planning_input.additional_context,
        selected_model=selected_model,
    )

    crew_patch = patch(
        "app.workflows.content_pipeline.Crew",
        side_effect=_make_capture_crew(
            fake_draft_analysis, fake_social_posts_bundle, captured_tasks
        ),
    )
    analyzer_patch = patch(
        "app.workflows.content_pipeline.create_analyzer_agent", return_value=MagicMock()
    )
    strategist_patch = patch(
        "app.workflows.content_pipeline.create_strategist_agent",
        return_value=MagicMock(),
    )
    copywriter_patch = patch(
        "app.workflows.content_pipeline.create_copywriter_agent",
        return_value=MagicMock(),
    )
    editor_patch = patch(
        "app.workflows.content_pipeline.create_editor_agent", return_value=MagicMock()
    )

    with ExitStack() as stack:
        for p in _TASK_PATCHES:
            stack.enter_context(p)
        mocked_analyzer = stack.enter_context(analyzer_patch)
        mocked_strategist = stack.enter_context(strategist_patch)
        mocked_copywriter = stack.enter_context(copywriter_patch)
        mocked_editor = stack.enter_context(editor_patch)
        stack.enter_context(crew_patch)
        result = service.process(input_with_model)

    assert result.status is True
    assert mocked_analyzer.call_count == 1
    assert mocked_strategist.call_count == 1
    assert mocked_copywriter.call_count == 1
    assert mocked_editor.call_count == 1

    assert mocked_analyzer.call_args.kwargs.get("model_override") == selected_model
    assert mocked_strategist.call_args.kwargs.get("model_override") == selected_model
    assert mocked_copywriter.call_args.kwargs.get("model_override") == selected_model
    assert mocked_editor.call_args.kwargs.get("model_override") == selected_model
    assert "crew_settings" in mocked_analyzer.call_args.kwargs
    assert "crew_settings" in mocked_strategist.call_args.kwargs
    assert "crew_settings" in mocked_copywriter.call_args.kwargs
    assert "crew_settings" in mocked_editor.call_args.kwargs


def test_process_returns_failure_and_error_message_when_kickoff_raises(
    service: ContentPlanningService,
    content_planning_input: ContentPlanningInput,
) -> None:
    """process() returns status=False with error message when crew.kickoff raises."""
    crew_patch = patch("app.workflows.content_pipeline.Crew")

    with ExitStack() as stack:
        for p in _ALL_PATCHES:
            stack.enter_context(p)
        MockCrew = stack.enter_context(crew_patch)
        mock_crew = MagicMock()
        mock_crew.kickoff.side_effect = RuntimeError("API rate limit exceeded")
        MockCrew.return_value = mock_crew

        result = service.process(content_planning_input)

    assert result.status is False
    assert result.data is None
    assert result.error is not None
    assert "API rate limit exceeded" in result.error


def test_process_returns_400_when_selected_model_is_not_supported(
    service: ContentPlanningService,
    content_planning_input: ContentPlanningInput,
) -> None:
    """process() returns code=400 when agent creation rejects selected model."""
    bad_input = ContentPlanningInput(
        url=content_planning_input.url,
        additional_context=content_planning_input.additional_context,
        selected_model="grok-4.20-reasoning",
    )

    with patch(
        "app.workflows.content_pipeline.create_analyzer_agent",
        side_effect=UnsupportedModelError("Unsupported model prefix."),
    ):
        result = service.process(bad_input)

    assert result.status is False
    assert result.code == 400
    assert result.error == "Unsupported model prefix."


def test_process_uses_short_term_cache_for_identical_success_requests(
    service: ContentPlanningService,
    content_planning_input: ContentPlanningInput,
    fake_draft_analysis: DraftAnalysis,
    fake_social_posts_bundle: SocialPostsBundle,
) -> None:
    """Second identical request should hit cache and avoid rebuilding Crew."""
    captured_tasks: list = []
    crew_patch = patch(
        "app.workflows.content_pipeline.Crew",
        side_effect=_make_capture_crew(
            fake_draft_analysis, fake_social_posts_bundle, captured_tasks
        ),
    )

    with ExitStack() as stack:
        for p in _ALL_PATCHES:
            stack.enter_context(p)
        mocked_crew = stack.enter_context(crew_patch)
        first = service.process(content_planning_input)
        second = service.process(content_planning_input)

    assert first.status is True
    assert second.status is True
    assert mocked_crew.call_count == 1


def test_process_returns_429_when_rate_limit_is_exceeded(
    service: ContentPlanningService,
    content_planning_input: ContentPlanningInput,
    fake_draft_analysis: DraftAnalysis,
    fake_social_posts_bundle: SocialPostsBundle,
) -> None:
    """With default window, the 4th rapid request is rate-limited."""
    captured_tasks: list = []
    crew_patch = patch(
        "app.workflows.content_pipeline.Crew",
        side_effect=_make_capture_crew(
            fake_draft_analysis, fake_social_posts_bundle, captured_tasks
        ),
    )

    with ExitStack() as stack:
        for p in _ALL_PATCHES:
            stack.enter_context(p)
        stack.enter_context(crew_patch)
        outputs = [service.process(content_planning_input) for _ in range(4)]

    assert outputs[0].status is True
    assert outputs[1].status is True
    assert outputs[2].status is True
    assert outputs[3].status is False
    assert outputs[3].code == 429
