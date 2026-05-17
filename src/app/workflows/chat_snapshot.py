from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import Field

from app.services.chat_contracts import ChatAction
from domain.models.models import ContentPlanOutput, DraftAnalysis, SocialPost
from shared.base import BaseModel


class ContentPlanSnapshot(BaseModel):
    source_url: str
    analysis: DraftAnalysis
    social_posts: list[SocialPost]
    meta: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_content_plan(cls, output: ContentPlanOutput) -> "ContentPlanSnapshot":
        return cls(
            source_url=output.source_url,
            analysis=output.analysis,
            social_posts=output.social_posts,
            meta={},
        )

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "ContentPlanSnapshot":
        if not isinstance(payload, dict):
            raise ValueError("Snapshot payload must be an object.")

        normalized = dict(payload)
        analysis_raw = normalized.get("analysis")
        if isinstance(analysis_raw, dict):
            normalized["analysis"] = DraftAnalysis.from_payload(analysis_raw)

        return cls.model_validate(normalized)


class SnapshotPatch(BaseModel):
    full_snapshot: ContentPlanSnapshot | None = None
    analysis: DraftAnalysis | None = None
    social_post: SocialPost | None = None
    strategy: str | None = None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _upsert_social_post(
    posts: list[SocialPost],
    updated: SocialPost,
) -> list[SocialPost]:
    next_posts: list[SocialPost] = []
    replaced = False
    for post in posts:
        if post.platform == updated.platform:
            next_posts.append(updated)
            replaced = True
        else:
            next_posts.append(post)
    if not replaced:
        next_posts.append(updated)
    return next_posts


def apply_partial_update(
    snapshot: ContentPlanSnapshot,
    patch: SnapshotPatch,
    action: ChatAction,
) -> tuple[ContentPlanSnapshot, list[str]]:
    if action == ChatAction.FULL_REGENERATE:
        if patch.full_snapshot is None:
            raise ValueError("FULL_REGENERATE requires full_snapshot patch.")
        updated = patch.full_snapshot.model_copy(deep=True)
        updated.meta["updated_at"] = _now_iso()
        updated.meta["last_action"] = action.value
        return ContentPlanSnapshot.model_validate(updated.model_dump()), [
            "analysis",
            "social_posts",
        ]

    updated = snapshot.model_copy(deep=True)
    affected_sections: list[str] = []

    if action == ChatAction.REANALYZE_ONLY:
        if patch.analysis is None:
            raise ValueError("REANALYZE_ONLY requires analysis patch.")
        updated.analysis = patch.analysis
        affected_sections.append("analysis")
    elif action == ChatAction.REWRITE_FACEBOOK_ONLY:
        if patch.social_post is None:
            raise ValueError("REWRITE_FACEBOOK_ONLY requires social_post patch.")
        if patch.social_post.platform.value != "facebook":
            raise ValueError("REWRITE_FACEBOOK_ONLY patch must target facebook.")
        updated.social_posts = _upsert_social_post(
            updated.social_posts, patch.social_post
        )
        affected_sections.append("social_posts.facebook")
    elif action == ChatAction.REWRITE_LINKEDIN_ONLY:
        if patch.social_post is None:
            raise ValueError("REWRITE_LINKEDIN_ONLY requires social_post patch.")
        if patch.social_post.platform.value != "linkedin":
            raise ValueError("REWRITE_LINKEDIN_ONLY patch must target linkedin.")
        updated.social_posts = _upsert_social_post(
            updated.social_posts, patch.social_post
        )
        affected_sections.append("social_posts.linkedin")
    elif action == ChatAction.REWRITE_STRATEGY_ONLY:
        if patch.strategy is None or not patch.strategy.strip():
            raise ValueError("REWRITE_STRATEGY_ONLY requires strategy patch.")
        updated.meta["strategy"] = patch.strategy.strip()
        affected_sections.append("meta.strategy")
    elif action in (ChatAction.CLARIFY, ChatAction.GENERAL_QA):
        # Non-mutating actions keep snapshot unchanged.
        return ContentPlanSnapshot.model_validate(updated.model_dump()), []
    else:
        raise ValueError(f"Unsupported chat action: {action.value}")

    updated.meta["updated_at"] = _now_iso()
    updated.meta["last_action"] = action.value
    return ContentPlanSnapshot.model_validate(updated.model_dump()), affected_sections
