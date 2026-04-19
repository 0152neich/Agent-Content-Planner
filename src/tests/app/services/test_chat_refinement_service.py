from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from app.services.chat_contracts import (
    ChatAction,
    ChatIntent,
    ChatRefinementInput,
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
