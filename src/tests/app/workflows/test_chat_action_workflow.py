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
from domain.models.models import (
    ContentPlanOutput,
    DraftAnalysis,
    Platform,
    SocialPost,
    SocialPostsBundle,
)


def _mock_settings() -> SimpleNamespace:
    return SimpleNamespace(crew=SimpleNamespace(verbose=False))


def test_compose_action_assistant_reply_returns_llm_output_with_guardrails() -> None:
    with patch(
        "app.workflows.chat_action_workflow.stream_llm_text",
        return_value="Mình đã cập nhật đúng theo yêu cầu của bạn.",
    ) as stream_reply:
        text = ChatActionWorkflowService._compose_action_assistant_reply(
            action=ChatAction.FULL_REGENERATE,
            prompt="Làm mới toàn bộ theo hướng chuyên gia",
            target_language="vi",
            selected_model="gpt-4o-mini",
            affected_sections=["analysis", "social_posts"],
            context_summary="Regenerated full snapshot with 2 social posts.",
        )

    assert text == "Mình đã cập nhật đúng theo yêu cầu của bạn."
    stream_prompt = stream_reply.call_args.kwargs["prompt"]
    assert "Resolved action: FULL_REGENERATE" in stream_prompt
    assert "User prompt (raw): Làm mới toàn bộ theo hướng chuyên gia" in stream_prompt
    assert "Use exactly Vietnamese." in stream_prompt


def test_compose_action_assistant_reply_falls_back_when_llm_fails() -> None:
    with patch(
        "app.workflows.chat_action_workflow.stream_llm_text",
        side_effect=RuntimeError("upstream timeout"),
    ):
        text = ChatActionWorkflowService._compose_action_assistant_reply(
            action=ChatAction.REWRITE_LINKEDIN_ONLY,
            prompt="thêm phần dẫn dắt",
            target_language="vi",
            selected_model=None,
            affected_sections=["social_posts.linkedin"],
            platform=Platform.LINKEDIN,
            context_summary="Hook after: ...",
        )

    assert text
    assert "Mình đã cập nhật" in text


def test_process_general_qa_small_talk_uses_composer() -> None:
    service = ChatActionWorkflowService()
    with (
        patch(
            "app.workflows.chat_action_workflow.Settings", return_value=_mock_settings()
        ),
        patch.object(
            ChatActionWorkflowService,
            "_compose_action_assistant_reply",
            return_value="Hi there, what would you like to refine next?",
        ) as compose_reply,
    ):
        result = service.process(
            ChatActionWorkflowInput(
                action=ChatAction.GENERAL_QA,
                prompt="hello",
                owner_user_id="user-1",
            )
        )

    assert result.status is True
    assert "refine next" in result.assistant_text
    assert compose_reply.call_args.kwargs["action"] == ChatAction.GENERAL_QA


def test_process_general_qa_small_talk_follows_prompt_language_vi() -> None:
    service = ChatActionWorkflowService()
    with (
        patch(
            "app.workflows.chat_action_workflow.Settings", return_value=_mock_settings()
        ),
        patch.object(
            ChatActionWorkflowService,
            "_compose_action_assistant_reply",
            side_effect=lambda **kwargs: f"lang={kwargs['target_language']}",
        ),
    ):
        result = service.process(
            ChatActionWorkflowInput(
                action=ChatAction.GENERAL_QA,
                prompt="xin chào",
                owner_user_id="user-1",
            )
        )

    assert result.status is True
    assert result.assistant_text == "lang=vi"


def test_process_general_qa_small_talk_follows_prompt_language_en() -> None:
    service = ChatActionWorkflowService()
    with (
        patch(
            "app.workflows.chat_action_workflow.Settings", return_value=_mock_settings()
        ),
        patch.object(
            ChatActionWorkflowService,
            "_compose_action_assistant_reply",
            side_effect=lambda **kwargs: f"lang={kwargs['target_language']}",
        ),
    ):
        result = service.process(
            ChatActionWorkflowInput(
                action=ChatAction.GENERAL_QA,
                prompt="hello",
                owner_user_id="user-1",
            )
        )

    assert result.status is True
    assert result.assistant_text == "lang=en"


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
        patch.object(
            ChatActionWorkflowService,
            "_compose_action_assistant_reply",
            return_value="Natural reply",
        ) as compose_reply,
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
    assert result.assistant_text == "Natural reply"
    assert result.patch.full_snapshot is not None
    assert result.affected_sections == ["analysis", "social_posts"]
    assert compose_reply.call_args.kwargs["action"] == ChatAction.FULL_REGENERATE
    assert compose_reply.call_args.kwargs["prompt"] == "regenerate all"


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


def test_inject_source_url_if_requested_appends_url_when_missing() -> None:
    service = ChatActionWorkflowService()
    post = SocialPost(
        platform=Platform.LINKEDIN,
        hook="Hook",
        body_content="Body",
        call_to_action="Comment your pain point.",
        hashtags=["ai", "content", "linkedin"],
    )

    updated = service._inject_source_url_if_requested(
        prompt="viet bai linkedin va cuoi bai co dinh kem link blog",
        source_url="https://example.com/blog",
        post=post,
    )

    assert updated.call_to_action.endswith("https://example.com/blog")


def test_inject_source_url_if_requested_keeps_post_when_no_link_request() -> None:
    service = ChatActionWorkflowService()
    post = SocialPost(
        platform=Platform.LINKEDIN,
        hook="Hook",
        body_content="Body",
        call_to_action="Comment your pain point.",
        hashtags=["ai", "content", "linkedin"],
    )

    updated = service._inject_source_url_if_requested(
        prompt="viet lai bai linkedin chuyen nghiep hon",
        source_url="https://example.com/blog",
        post=post,
    )

    assert updated.call_to_action == post.call_to_action
