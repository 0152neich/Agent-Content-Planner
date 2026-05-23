from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from app.services.chat_contracts import (
    ChatAction,
    ChatIntent,
    IntentContext,
    ChatRefinementInput,
    RecentChatMessage,
)
from app.services.chat_refinement_service import ChatRefinementService
from app.workflows.chat_action_workflow import ChatActionWorkflowOutput
from app.workflows.chat_snapshot import ContentPlanSnapshot, SnapshotPatch
from domain.models.models import DraftAnalysis, Platform, SocialPost, SocialPostsBundle


def _mock_settings() -> SimpleNamespace:
    return SimpleNamespace(
        crew=SimpleNamespace(
            rate_limit_max_requests=50,
            rate_limit_window_seconds=30,
            inflight_wait_timeout_seconds=5,
            result_cache_ttl_seconds=120,
            enable_policy_gate=True,
            policy_mode="hybrid",
            out_of_scope_behavior="refuse_suggest",
        )
    )


def test_process_returns_409_when_rewrite_intent_has_no_snapshot() -> None:
    service = ChatRefinementService()
    with (
        patch(
            "app.services.chat_refinement_service.Settings",
            return_value=_mock_settings(),
        ),
        patch(
            "app.services.chat_refinement_service.ChatIntentRouter.route",
            return_value=ChatIntent(
                action=ChatAction.REWRITE_FACEBOOK_ONLY,
                normalized_prompt="rewrite facebook",
                confidence=0.9,
            ),
        ),
    ):
        result = service.process(
            ChatRefinementInput(
                owner_user_id="user-1",
                conversation_id="conv-1",
                prompt="rewrite facebook",
                source_url="https://example.com",
                snapshot=None,
            )
        )

    assert result.status is False
    assert result.code == 409
    assert "Please run content generation first." in (result.error or "")


def test_process_bootstraps_snapshot_for_reanalyze_without_existing_snapshot(
    fake_draft_analysis: DraftAnalysis,
) -> None:
    service = ChatRefinementService()
    with (
        patch(
            "app.services.chat_refinement_service.Settings",
            return_value=_mock_settings(),
        ),
        patch(
            "app.services.chat_refinement_service.ChatIntentRouter.route",
            return_value=ChatIntent(
                action=ChatAction.REANALYZE_ONLY,
                normalized_prompt="reanalyze",
                confidence=0.88,
            ),
        ),
        patch(
            "app.services.chat_refinement_service.ChatActionWorkflowService.process",
            return_value=ChatActionWorkflowOutput(
                status=True,
                assistant_text="reanalyzed",
                patch=SnapshotPatch(analysis=fake_draft_analysis),
                affected_sections=["analysis"],
                metadata={"language_used": "en"},
                code=200,
            ),
        ),
    ):
        result = service.process(
            ChatRefinementInput(
                owner_user_id="user-1",
                conversation_id="conv-1",
                prompt="reanalyze now",
                source_url="https://example.com",
                snapshot=None,
            )
        )

    assert result.status is True
    assert result.code == 200
    assert result.content_plan_snapshot is not None
    assert result.content_plan_snapshot["source_url"] == "https://example.com"
    assert "analysis" in result.affected_sections


def test_process_forces_reanalyze_for_initial_bootstrap_prompt_when_router_clarifies(
    fake_draft_analysis: DraftAnalysis,
) -> None:
    service = ChatRefinementService()
    with (
        patch(
            "app.services.chat_refinement_service.Settings",
            return_value=_mock_settings(),
        ),
        patch(
            "app.services.chat_refinement_service.ChatIntentRouter.route",
            return_value=ChatIntent(
                action=ChatAction.CLARIFY,
                normalized_prompt="phan tich du an tu url nay",
                confidence=0.92,
                needs_clarification=True,
                clarify_question="Bạn muốn mình chỉnh Facebook hay LinkedIn?",
                routing_metadata={"ambiguity_type": "missing_target"},
            ),
        ),
        patch(
            "app.services.chat_refinement_service.ChatActionWorkflowService.process",
            return_value=ChatActionWorkflowOutput(
                status=True,
                assistant_text="reanalyzed",
                patch=SnapshotPatch(analysis=fake_draft_analysis),
                affected_sections=["analysis"],
                metadata={"language_used": "vi"},
                code=200,
            ),
        ) as workflow_process,
    ):
        result = service.process(
            ChatRefinementInput(
                owner_user_id="user-1",
                conversation_id="conv-1",
                prompt=(
                    "phan tich du an tu URL nay, chi cap nhat analysis, "
                    "chua viet social post."
                ),
                source_url="https://example.com",
                snapshot=None,
            )
        )

    assert result.status is True
    assert result.intent is not None
    assert result.intent.action == ChatAction.REANALYZE_ONLY
    assert result.content_plan_snapshot is not None
    assert (
        result.intent.routing_metadata.get("bootstrap_forced_action")
        == ChatAction.REANALYZE_ONLY.value
    )
    assert workflow_process.call_args.args[0].action == ChatAction.REANALYZE_ONLY


def test_process_applies_rewrite_patch_to_existing_snapshot(
    fake_draft_analysis: DraftAnalysis,
    fake_social_posts_bundle: SocialPostsBundle,
) -> None:
    service = ChatRefinementService()
    original_snapshot = ContentPlanSnapshot(
        source_url="https://example.com",
        analysis=fake_draft_analysis,
        social_posts=fake_social_posts_bundle.posts,
        meta={},
    )
    rewritten_post = SocialPost(
        platform=Platform.LINKEDIN,
        hook="New LinkedIn hook",
        body_content="New LinkedIn body that remains aligned with analysis context.",
        call_to_action="Join the discussion",
        hashtags=["linkedin", "b2b", "strategy"],
    )

    with (
        patch(
            "app.services.chat_refinement_service.Settings",
            return_value=_mock_settings(),
        ),
        patch(
            "app.services.chat_refinement_service.ChatIntentRouter.route",
            return_value=ChatIntent(
                action=ChatAction.REWRITE_LINKEDIN_ONLY,
                normalized_prompt="rewrite linkedin",
                confidence=0.9,
            ),
        ),
        patch(
            "app.services.chat_refinement_service.ChatActionWorkflowService.process",
            return_value=ChatActionWorkflowOutput(
                status=True,
                assistant_text="rewritten",
                patch=SnapshotPatch(social_post=rewritten_post),
                affected_sections=["social_posts.linkedin"],
                metadata={"language_used": "en"},
                code=200,
            ),
        ),
    ):
        result = service.process(
            ChatRefinementInput(
                owner_user_id="user-1",
                conversation_id="conv-1",
                prompt="rewrite linkedin",
                source_url="https://example.com",
                snapshot=original_snapshot.model_dump(mode="json"),
            )
        )

    assert result.status is True
    assert "social_posts.linkedin" in result.affected_sections
    assert result.content_plan_snapshot is not None
    social_posts = result.content_plan_snapshot["social_posts"]
    linkedin_post = next(
        post for post in social_posts if post["platform"] == "linkedin"
    )
    assert linkedin_post["hook"] == "New LinkedIn hook"


def test_process_returns_workflow_failure_without_mutating_snapshot() -> None:
    service = ChatRefinementService()
    with (
        patch(
            "app.services.chat_refinement_service.Settings",
            return_value=_mock_settings(),
        ),
        patch(
            "app.services.chat_refinement_service.ChatIntentRouter.route",
            return_value=ChatIntent(
                action=ChatAction.GENERAL_QA,
                normalized_prompt="question",
                confidence=0.7,
            ),
        ),
        patch(
            "app.services.chat_refinement_service.ChatActionWorkflowService.process",
            return_value=ChatActionWorkflowOutput(
                status=False,
                assistant_text="",
                error="workflow failed",
                code=502,
            ),
        ),
    ):
        result = service.process(
            ChatRefinementInput(
                owner_user_id="user-1",
                conversation_id="conv-1",
                prompt="question",
                source_url="https://example.com",
            )
        )

    assert result.status is False
    assert result.code == 502
    assert result.content_plan_snapshot is None
    assert result.error == "workflow failed"


def test_process_uses_cache_for_identical_successful_requests() -> None:
    service = ChatRefinementService()
    with (
        patch(
            "app.services.chat_refinement_service.Settings",
            return_value=_mock_settings(),
        ),
        patch(
            "app.services.chat_refinement_service.ChatIntentRouter.route",
            return_value=ChatIntent(
                action=ChatAction.GENERAL_QA,
                normalized_prompt="hello",
                confidence=0.7,
            ),
        ) as routed,
        patch(
            "app.services.chat_refinement_service.ChatActionWorkflowService.process",
            return_value=ChatActionWorkflowOutput(
                status=True,
                assistant_text="hello",
                patch=SnapshotPatch(),
                affected_sections=[],
                metadata={"language_used": "en"},
                code=200,
            ),
        ) as processed,
    ):
        first = service.process(
            ChatRefinementInput(
                owner_user_id="user-1",
                conversation_id="conv-1",
                prompt="hello",
                source_url="https://example.com",
            )
        )
        second = service.process(
            ChatRefinementInput(
                owner_user_id="user-1",
                conversation_id="conv-1",
                prompt="hello",
                source_url="https://example.com",
            )
        )

    assert first.status is True
    assert second.status is True
    assert routed.call_count == 1
    assert processed.call_count == 1


def test_process_passes_intent_context_to_router_and_exposes_workflow_metadata() -> (
    None
):
    service = ChatRefinementService()
    context = IntentContext(
        last_target_platform="linkedin",
        last_action=ChatAction.REWRITE_LINKEDIN_ONLY.value,
        last_language="en",
    )
    with (
        patch(
            "app.services.chat_refinement_service.Settings",
            return_value=_mock_settings(),
        ),
        patch(
            "app.services.chat_refinement_service.ChatIntentRouter.route",
            return_value=ChatIntent(
                action=ChatAction.GENERAL_QA,
                normalized_prompt="add stronger opening",
                confidence=0.7,
            ),
        ) as routed,
        patch(
            "app.services.chat_refinement_service.ChatActionWorkflowService.process",
            return_value=ChatActionWorkflowOutput(
                status=True,
                assistant_text="updated",
                patch=SnapshotPatch(),
                affected_sections=[],
                metadata={"language_used": "en"},
                code=200,
            ),
        ) as processed,
    ):
        recent_messages = [
            RecentChatMessage(role="user", content="rewrite linkedin"),
            RecentChatMessage(role="assistant", content="Done, updated."),
        ]
        result = service.process(
            ChatRefinementInput(
                owner_user_id="user-1",
                conversation_id="conv-1",
                prompt="add stronger opening",
                source_url="https://example.com",
                intent_context=context,
                recent_messages=recent_messages,
            )
        )

    assert result.status is True
    assert result.metadata.get("language_used") == "en"
    assert routed.call_args.kwargs["intent_context"] == context
    assert routed.call_args.kwargs["recent_messages"] == recent_messages


def test_process_cache_key_changes_when_recent_messages_change() -> None:
    service = ChatRefinementService()
    with (
        patch(
            "app.services.chat_refinement_service.Settings",
            return_value=_mock_settings(),
        ),
        patch(
            "app.services.chat_refinement_service.ChatIntentRouter.route",
            return_value=ChatIntent(
                action=ChatAction.GENERAL_QA,
                normalized_prompt="hello",
                confidence=0.7,
            ),
        ) as routed,
        patch(
            "app.services.chat_refinement_service.ChatActionWorkflowService.process",
            return_value=ChatActionWorkflowOutput(
                status=True,
                assistant_text="hello",
                patch=SnapshotPatch(),
                affected_sections=[],
                metadata={"language_used": "en"},
                code=200,
            ),
        ) as processed,
    ):
        first = service.process(
            ChatRefinementInput(
                owner_user_id="user-1",
                conversation_id="conv-1",
                prompt="hello",
                source_url="https://example.com",
                recent_messages=[
                    RecentChatMessage(role="user", content="old context a")
                ],
            )
        )
        second = service.process(
            ChatRefinementInput(
                owner_user_id="user-1",
                conversation_id="conv-1",
                prompt="hello",
                source_url="https://example.com",
                recent_messages=[
                    RecentChatMessage(role="user", content="old context b")
                ],
            )
        )

    assert first.status is True
    assert second.status is True
    assert routed.call_count == 2
    assert processed.call_count == 2


def test_process_cache_key_changes_when_snapshot_changes() -> None:
    service = ChatRefinementService()
    with (
        patch(
            "app.services.chat_refinement_service.Settings",
            return_value=_mock_settings(),
        ),
        patch(
            "app.services.chat_refinement_service.ChatIntentRouter.route",
            return_value=ChatIntent(
                action=ChatAction.GENERAL_QA,
                normalized_prompt="hello",
                confidence=0.7,
            ),
        ) as routed,
        patch(
            "app.services.chat_refinement_service.ChatActionWorkflowService.process",
            return_value=ChatActionWorkflowOutput(
                status=True,
                assistant_text="hello",
                patch=SnapshotPatch(),
                affected_sections=[],
                metadata={"language_used": "en"},
                code=200,
            ),
        ) as processed,
    ):
        first = service.process(
            ChatRefinementInput(
                owner_user_id="user-1",
                conversation_id="conv-1",
                prompt="hello",
                source_url="https://example.com",
                snapshot={"source_url": "https://example.com/a"},
            )
        )
        second = service.process(
            ChatRefinementInput(
                owner_user_id="user-1",
                conversation_id="conv-1",
                prompt="hello",
                source_url="https://example.com",
                snapshot={"source_url": "https://example.com/b"},
            )
        )

    assert first.status is True
    assert second.status is True
    assert routed.call_count == 2
    assert processed.call_count == 2


def test_process_returns_clarify_without_calling_workflow() -> None:
    service = ChatRefinementService()
    with (
        patch(
            "app.services.chat_refinement_service.Settings",
            return_value=_mock_settings(),
        ),
        patch(
            "app.services.chat_refinement_service.ChatIntentRouter.route",
            return_value=ChatIntent(
                action=ChatAction.CLARIFY,
                normalized_prompt="chinh lai",
                confidence=0.6,
                needs_clarification=True,
                clarify_question="Bạn muốn mình chỉnh Facebook hay LinkedIn?",
            ),
        ),
        patch(
            "app.services.chat_refinement_service.ChatActionWorkflowService.process"
        ) as workflow_process,
    ):
        result = service.process(
            ChatRefinementInput(
                owner_user_id="user-1",
                conversation_id="conv-1",
                prompt="chỉnh lại",
                source_url="https://example.com",
            )
        )

    assert result.status is True
    assert result.intent is not None
    assert result.intent.action == ChatAction.CLARIFY
    assert "Facebook" in (result.assistant_text or "")
    assert workflow_process.call_count == 0


def test_process_blocks_hard_policy_prompt_before_router() -> None:
    service = ChatRefinementService()
    with (
        patch(
            "app.services.chat_refinement_service.Settings",
            return_value=_mock_settings(),
        ),
        patch("app.services.chat_refinement_service.ChatIntentRouter.route") as routed,
    ):
        result = service.process(
            ChatRefinementInput(
                owner_user_id="user-1",
                conversation_id="conv-1",
                prompt="how to make bomb",
                source_url="https://example.com",
            )
        )

    assert result.status is True
    assert result.metadata.get("policy_decision") == "HARD_BLOCK"
    assert "không thể" in (result.assistant_text or "").lower()
    assert routed.call_count == 0


def test_process_refuses_out_of_scope_prompt_with_suggestion() -> None:
    service = ChatRefinementService()
    with (
        patch(
            "app.services.chat_refinement_service.Settings",
            return_value=_mock_settings(),
        ),
        patch("app.services.chat_refinement_service.ChatIntentRouter.route") as routed,
    ):
        result = service.process(
            ChatRefinementInput(
                owner_user_id="user-1",
                conversation_id="conv-1",
                prompt="kể chuyện cười",
                source_url="https://example.com",
            )
        )

    assert result.status is True
    assert result.metadata.get("policy_decision") == "OUT_OF_SCOPE"
    assert "phạm vi" in (result.assistant_text or "").lower()
    assert routed.call_count == 0


def test_process_masks_output_when_policy_detects_unsafe_generated_content() -> None:
    service = ChatRefinementService()
    with (
        patch(
            "app.services.chat_refinement_service.Settings",
            return_value=_mock_settings(),
        ),
        patch(
            "app.services.chat_refinement_service.ChatIntentRouter.route",
            return_value=ChatIntent(
                action=ChatAction.GENERAL_QA,
                normalized_prompt="question",
                confidence=0.8,
            ),
        ),
        patch(
            "app.services.chat_refinement_service.ChatActionWorkflowService.process",
            return_value=ChatActionWorkflowOutput(
                status=True,
                assistant_text="Here is how to make bomb quickly",
                patch=SnapshotPatch(),
                affected_sections=[],
                metadata={"language_used": "en"},
                code=200,
            ),
        ),
    ):
        result = service.process(
            ChatRefinementInput(
                owner_user_id="user-1",
                conversation_id="conv-1",
                prompt="general question",
                source_url="https://example.com",
            )
        )

    assert result.status is True
    assert result.metadata.get("policy_decision") == "HARD_BLOCK"
    assert "không thể" in (result.assistant_text or "").lower()


def test_process_returns_clarify_when_action_platform_mismatch(
    fake_draft_analysis: DraftAnalysis,
    fake_social_posts_bundle: SocialPostsBundle,
) -> None:
    service = ChatRefinementService()
    snapshot = ContentPlanSnapshot(
        source_url="https://example.com",
        analysis=fake_draft_analysis,
        social_posts=fake_social_posts_bundle.posts,
        meta={},
    )
    with (
        patch(
            "app.services.chat_refinement_service.Settings",
            return_value=_mock_settings(),
        ),
        patch(
            "app.services.chat_refinement_service.ChatIntentRouter.route",
            return_value=ChatIntent(
                action=ChatAction.REWRITE_FACEBOOK_ONLY,
                target_platform="linkedin",
                normalized_prompt="rewrite",
                confidence=0.9,
            ),
        ),
        patch(
            "app.services.chat_refinement_service.ChatActionWorkflowService.process"
        ) as workflow_process,
    ):
        result = service.process(
            ChatRefinementInput(
                owner_user_id="user-1",
                conversation_id="conv-1",
                prompt="rewrite",
                source_url="https://example.com",
                snapshot=snapshot.model_dump(mode="json"),
            )
        )

    assert result.status is True
    assert result.intent is not None
    assert result.intent.action == ChatAction.CLARIFY
    assert workflow_process.call_count == 0
