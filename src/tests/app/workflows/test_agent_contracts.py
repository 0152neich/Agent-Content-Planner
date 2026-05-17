from __future__ import annotations

import pytest

from app.workflows.agent_contracts import AgentContractGateway, WorkflowContractError
from domain.models.models import Platform, SocialPost, SocialPostsBundle


def test_validate_social_post_repairs_hashtags_without_content_injection() -> None:
    gateway = AgentContractGateway()
    post = SocialPost(
        platform=Platform.LINKEDIN,
        hook="Professional hook for a B2B audience.",
        body_content="This is a long English body with enough detail to pass language checks safely.",
        call_to_action="Try it today for your team.",
        hashtags=[" #AI ", "#ai", " marketing ", "growth"],
    )

    repaired, repair_applied = gateway.validate_social_post(
        post,
        target_language="en",
        stage="unit_social_post",
        expected_platform=Platform.LINKEDIN,
    )

    assert repair_applied is True
    assert repaired.platform == Platform.LINKEDIN
    assert repaired.hashtags == ["AI", "marketing", "growth"]
    assert all("#" not in tag for tag in repaired.hashtags)


def test_validate_social_post_fails_when_hashtag_count_is_still_invalid_after_repair() -> (
    None
):
    gateway = AgentContractGateway()
    post = SocialPost(
        platform=Platform.FACEBOOK,
        hook="A short hook",
        body_content="Enough English content to avoid any language detector ambiguity in this test.",
        call_to_action="Read more now",
        hashtags=["ai", "marketing"],
    )

    with pytest.raises(WorkflowContractError) as exc:
        gateway.validate_social_post(
            post,
            target_language="en",
            stage="unit_social_post_invalid_hashtags",
            expected_platform=Platform.FACEBOOK,
        )

    assert exc.value.code == "WORKFLOW_CONTRACT_REPAIR_FAILED"
    assert exc.value.stage == "unit_social_post_invalid_hashtags"


def test_validate_social_posts_bundle_fails_for_missing_platform() -> None:
    gateway = AgentContractGateway()
    bundle = SocialPostsBundle(
        posts=[
            SocialPost(
                platform=Platform.LINKEDIN,
                hook="Hook for LinkedIn audience",
                body_content="This is valid English content for LinkedIn and is long enough for language checks.",
                call_to_action="Go now",
                hashtags=["ai", "content", "marketing"],
            )
        ]
    )

    with pytest.raises(WorkflowContractError) as exc:
        gateway.validate_social_posts_bundle(
            bundle,
            target_language="en",
            stage="unit_bundle",
        )
    assert exc.value.code == "WORKFLOW_CONTRACT_REPAIR_FAILED"


def test_validate_social_post_fails_for_platform_mismatch() -> None:
    gateway = AgentContractGateway()
    post = SocialPost(
        platform=Platform.LINKEDIN,
        hook="Hook for LinkedIn",
        body_content="This is valid English content and should pass language checks by itself.",
        call_to_action="Go now",
        hashtags=["ai", "content", "marketing"],
    )

    with pytest.raises(WorkflowContractError) as exc:
        gateway.validate_social_post(
            post,
            target_language="en",
            stage="unit_platform_mismatch",
            expected_platform=Platform.FACEBOOK,
        )

    assert exc.value.code == "WORKFLOW_CONTRACT_REPAIR_FAILED"
