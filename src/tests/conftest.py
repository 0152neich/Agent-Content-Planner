"""Shared pytest fixtures for Agent-Content-Planner tests."""

from __future__ import annotations

import pytest

from domain.models.models import (
    DraftAnalysis,
    Platform,
    SocialPost,
    SocialPostsBundle,
)
from app.workflows.content_pipeline import ContentPlanningInput


@pytest.fixture
def sample_url() -> str:
    """Sample article URL for pipeline input."""
    return "https://example.com/sample-article"


@pytest.fixture
def content_planning_input(sample_url: str) -> ContentPlanningInput:
    """Minimal valid input for ContentPlanningService.process()."""
    return ContentPlanningInput(url=sample_url, additional_context=None)


@pytest.fixture
def content_planning_input_with_context(sample_url: str) -> ContentPlanningInput:
    """Input with optional additional_context."""
    return ContentPlanningInput(
        url=sample_url,
        additional_context="Focus on B2B audience.",
    )


@pytest.fixture
def fake_draft_analysis() -> DraftAnalysis:
    """Fake analyzer task output (API giả lập đúng)."""
    return DraftAnalysis(
        core_message="The article explains best practices for content planning.",
        key_takeaways=[
            "Define clear goals before creating content.",
            "Use a consistent tone across platforms.",
            "Review and iterate based on metrics.",
        ],
        target_audience="Marketing teams and content managers",
        tone_of_voice="Professional and instructive",
    )


@pytest.fixture
def fake_social_posts_bundle() -> SocialPostsBundle:
    """Fake review task output: bundle of posts (API giả lập đúng)."""
    return SocialPostsBundle(
        posts=[
            SocialPost(
                platform=Platform.LINKEDIN,
                hook="Did you know?",
                body_content="Short professional post for LinkedIn.",
                call_to_action="Read the full article.",
                hashtags=["#ContentStrategy", "#Marketing", "#LinkedIn"],
            ),
            SocialPost(
                platform=Platform.FACEBOOK,
                hook="Here's a quick tip:",
                body_content="Engaging post for Facebook audience.",
                call_to_action="Share if you found this useful.",
                hashtags=["#ContentPlanning", "#SocialMedia", "#Tips"],
            ),
        ]
    )
