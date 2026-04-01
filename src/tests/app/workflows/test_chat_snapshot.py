from __future__ import annotations

from app.services.chat_contracts import ChatAction
from app.workflows.chat_snapshot import (
    ContentPlanSnapshot,
    SnapshotPatch,
    apply_partial_update,
)
from domain.models.models import DraftAnalysis, Platform, SocialPost


def _base_snapshot() -> ContentPlanSnapshot:
    return ContentPlanSnapshot(
        source_url="https://example.com/post",
        analysis=DraftAnalysis(
            core_message="Core A",
            key_takeaways=["A1", "A2", "A3"],
            target_audience="Developers",
            tone_of_voice="Professional",
        ),
        social_posts=[
            SocialPost(
                platform=Platform.LINKEDIN,
                hook="L hook",
                body_content="L body",
                call_to_action="L cta",
                hashtags=["ai", "content"],
            ),
            SocialPost(
                platform=Platform.FACEBOOK,
                hook="F hook",
                body_content="F body",
                call_to_action="F cta",
                hashtags=["social", "marketing"],
            ),
        ],
        meta={"strategy": "old strategy"},
    )


def test_apply_partial_update_facebook_only_changes_facebook_post() -> None:
    snapshot = _base_snapshot()
    linkedin_before = next(
        post for post in snapshot.social_posts if post.platform == Platform.LINKEDIN
    )

    updated, affected = apply_partial_update(
        snapshot=snapshot,
        patch=SnapshotPatch(
            social_post=SocialPost(
                platform=Platform.FACEBOOK,
                hook="F hook new",
                body_content="F body new",
                call_to_action="F cta new",
                hashtags=["new"],
            )
        ),
        action=ChatAction.REWRITE_FACEBOOK_ONLY,
    )

    linkedin_after = next(
        post for post in updated.social_posts if post.platform == Platform.LINKEDIN
    )
    facebook_after = next(
        post for post in updated.social_posts if post.platform == Platform.FACEBOOK
    )

    assert affected == ["social_posts.facebook"]
    assert linkedin_after == linkedin_before
    assert facebook_after.hook == "F hook new"
    assert facebook_after.body_content == "F body new"


def test_apply_partial_update_reanalyze_only_keeps_social_posts() -> None:
    snapshot = _base_snapshot()
    social_before = list(snapshot.social_posts)

    updated, affected = apply_partial_update(
        snapshot=snapshot,
        patch=SnapshotPatch(
            analysis=DraftAnalysis(
                core_message="Core B",
                key_takeaways=["B1", "B2", "B3"],
                target_audience="Marketers",
                tone_of_voice="Friendly",
            )
        ),
        action=ChatAction.REANALYZE_ONLY,
    )

    assert affected == ["analysis"]
    assert updated.analysis.core_message == "Core B"
    assert updated.social_posts == social_before


def test_apply_partial_update_strategy_only_changes_meta_strategy() -> None:
    snapshot = _base_snapshot()
    social_before = list(snapshot.social_posts)

    updated, affected = apply_partial_update(
        snapshot=snapshot,
        patch=SnapshotPatch(strategy="new strategy"),
        action=ChatAction.REWRITE_STRATEGY_ONLY,
    )

    assert affected == ["meta.strategy"]
    assert updated.meta.get("strategy") == "new strategy"
    assert updated.social_posts == social_before


def test_apply_partial_update_clarify_is_non_mutating() -> None:
    snapshot = _base_snapshot()
    updated, affected = apply_partial_update(
        snapshot=snapshot,
        patch=SnapshotPatch(),
        action=ChatAction.CLARIFY,
    )

    assert affected == []
    assert updated.model_dump(mode="json") == snapshot.model_dump(mode="json")
