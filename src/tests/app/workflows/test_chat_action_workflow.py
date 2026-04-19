from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from app.services.chat_contracts import ChatAction
from app.workflows.agent_contracts import WorkflowContractError
from app.workflows.chat_action_workflow import (
    ChatActionWorkflowInput,
    ChatActionWorkflowOutput,
    ChatActionWorkflowService,
)
from app.workflows.chat_snapshot import ContentPlanSnapshot
from app.workflows.content_pipeline import ContentPlanningOutput, ContentPlanningService
from domain.models.models import ContentPlanOutput, DraftAnalysis, SocialPostsBundle


def _mock_settings() -> SimpleNamespace:
    return SimpleNamespace(crew=SimpleNamespace(verbose=False))


def test_build_action_assistant_text_vi_is_readable() -> None:
    text = ChatActionWorkflowService._build_action_assistant_text(
        action=ChatAction.FULL_REGENERATE,
        target_language="vi",
        affected_sections=["analysis", "social_posts"],
    )

    assert "Mình đã làm mới toàn bộ nội dung" in text
    assert "MÃ" not in text


def test_process_general_qa_small_talk_returns_short_friendly_reply() -> None:
    service = ChatActionWorkflowService()
    with patch(
        "app.workflows.chat_action_workflow.Settings", return_value=_mock_settings()
    ):
        result = service.process(
            ChatActionWorkflowInput(
                action=ChatAction.GENERAL_QA,
                prompt="xin chào",
                owner_user_id="user-1",
            )
        )

    assert result.status is True
    assert "Chào bạn" in result.assistant_text


def test_process_full_regenerate_requires_source_url() -> None:
    service = ChatActionWorkflowService()
    with patch(
        "app.workflows.chat_action_workflow.Settings", return_value=_mock_settings()
    ):
        result = service.process(
            ChatActionWorkflowInput(
                action=ChatAction.FULL_REGENERATE,
                prompt="refresh all",
                owner_user_id="user-1",
            )
        )

    assert result.status is False
    assert result.code == 409
    assert result.error == "Missing source URL for full regenerate."


def test_process_full_regenerate_success_returns_full_snapshot(
    fake_draft_analysis: DraftAnalysis,
    fake_social_posts_bundle: SocialPostsBundle,
) -> None:
    service = ChatActionWorkflowService()
    content_plan = ContentPlanOutput(
        source_url="https://example.com",
        analysis=fake_draft_analysis,
        social_posts=fake_social_posts_bundle.posts,
    )

    with (
        patch(
            "app.workflows.chat_action_workflow.Settings", return_value=_mock_settings()
        ),
        patch.object(
            ContentPlanningService,
            "process",
            return_value=ContentPlanningOutput(
                status=True, data=content_plan, code=200
            ),
        ),
    ):
        result = service.process(
            ChatActionWorkflowInput(
                action=ChatAction.FULL_REGENERATE,
                prompt="regenerate all",
                source_url="https://example.com",
                owner_user_id="user-1",
            )
        )

    assert result.status is True
    assert result.code == 200
    assert result.patch.full_snapshot is not None
    assert result.affected_sections == ["analysis", "social_posts"]


def test_process_full_regenerate_returns_500_when_output_schema_is_invalid() -> None:
    service = ChatActionWorkflowService()
    with (
        patch(
            "app.workflows.chat_action_workflow.Settings", return_value=_mock_settings()
        ),
        patch.object(
            ContentPlanningService,
            "process",
            return_value=ContentPlanningOutput(
                status=True, data={"unexpected": "shape"}, code=200
            ),
        ),
    ):
        result = service.process(
            ChatActionWorkflowInput(
                action=ChatAction.FULL_REGENERATE,
                prompt="regenerate all",
                source_url="https://example.com",
                owner_user_id="user-1",
            )
        )

    assert result.status is False
    assert result.code == 500
    assert "expected schema" in (result.error or "")


def test_process_returns_422_with_contract_error_metadata(
    fake_draft_analysis: DraftAnalysis,
    fake_social_posts_bundle: SocialPostsBundle,
) -> None:
    service = ChatActionWorkflowService()
    content_plan = ContentPlanOutput(
        source_url="https://example.com",
        analysis=fake_draft_analysis,
        social_posts=fake_social_posts_bundle.posts,
    )

    with (
        patch(
            "app.workflows.chat_action_workflow.Settings", return_value=_mock_settings()
        ),
        patch.object(
            ContentPlanningService,
            "process",
            return_value=ContentPlanningOutput(
                status=True, data=content_plan, code=200
            ),
        ),
        patch.object(
            ChatActionWorkflowService,
            "_log_stage",
            return_value=None,
        ),
        patch(
            "app.workflows.chat_action_workflow.AgentContractGateway.validate_analysis",
            side_effect=WorkflowContractError(
                code="WORKFLOW_CONTRACT_REPAIR_FAILED",
                stage="chat_full_regenerate_analysis",
                detail="analysis invalid",
            ),
        ),
    ):
        result = service.process(
            ChatActionWorkflowInput(
                action=ChatAction.FULL_REGENERATE,
                prompt="regenerate all",
                source_url="https://example.com",
                owner_user_id="user-1",
            )
        )

    assert result.status is False
    assert result.code == 422
    assert (
        result.metadata["contract_error"]["code"] == "WORKFLOW_CONTRACT_REPAIR_FAILED"
    )
    assert result.metadata["contract_error"]["stage"] == "chat_full_regenerate_analysis"


def test_process_reanalyze_only_requires_source_url() -> None:
    service = ChatActionWorkflowService()
    with patch(
        "app.workflows.chat_action_workflow.Settings", return_value=_mock_settings()
    ):
        result = service.process(
            ChatActionWorkflowInput(
                action=ChatAction.REANALYZE_ONLY,
                prompt="reanalyze",
                owner_user_id="user-1",
            )
        )

    assert result.status is False
    assert result.code == 409
    assert result.error == "Missing source URL for reanalyze action."


def test_process_rewrite_facebook_requires_snapshot() -> None:
    service = ChatActionWorkflowService()
    with patch(
        "app.workflows.chat_action_workflow.Settings", return_value=_mock_settings()
    ):
        result = service.process(
            ChatActionWorkflowInput(
                action=ChatAction.REWRITE_FACEBOOK_ONLY,
                prompt="rewrite facebook",
                owner_user_id="user-1",
            )
        )

    assert result.status is False
    assert result.code == 409
    assert result.error == "Snapshot is required for facebook rewrite."


def test_process_rewrite_linkedin_requires_snapshot() -> None:
    service = ChatActionWorkflowService()
    with patch(
        "app.workflows.chat_action_workflow.Settings", return_value=_mock_settings()
    ):
        result = service.process(
            ChatActionWorkflowInput(
                action=ChatAction.REWRITE_LINKEDIN_ONLY,
                prompt="rewrite linkedin",
                owner_user_id="user-1",
            )
        )

    assert result.status is False
    assert result.code == 409
    assert result.error == "Snapshot is required for linkedin rewrite."


def test_process_rewrite_strategy_requires_snapshot() -> None:
    service = ChatActionWorkflowService()
    with patch(
        "app.workflows.chat_action_workflow.Settings", return_value=_mock_settings()
    ):
        result = service.process(
            ChatActionWorkflowInput(
                action=ChatAction.REWRITE_STRATEGY_ONLY,
                prompt="rewrite strategy",
                owner_user_id="user-1",
            )
        )

    assert result.status is False
    assert result.code == 409
    assert result.error == "Snapshot is required for strategy rewrite."


def test_process_general_qa_dispatches_without_snapshot(
    fake_draft_analysis: DraftAnalysis,
    fake_social_posts_bundle: SocialPostsBundle,
) -> None:
    service = ChatActionWorkflowService()
    snapshot = ContentPlanSnapshot(
        source_url="https://example.com",
        analysis=fake_draft_analysis,
        social_posts=fake_social_posts_bundle.posts,
        meta={},
    )
    mocked_output = ChatActionWorkflowOutput(
        status=True,
        assistant_text="ok",
        code=200,
    )

    with (
        patch(
            "app.workflows.chat_action_workflow.Settings", return_value=_mock_settings()
        ),
        patch.object(
            ChatActionWorkflowService,
            "_run_general_qa",
            return_value=mocked_output,
        ) as run_general_qa,
    ):
        result = service.process(
            ChatActionWorkflowInput(
                action=ChatAction.GENERAL_QA,
                prompt="help me improve this",
                snapshot=snapshot,
                owner_user_id="user-1",
            )
        )

    assert result.status is True
    assert result.assistant_text == "ok"
    run_general_qa.assert_called_once()
