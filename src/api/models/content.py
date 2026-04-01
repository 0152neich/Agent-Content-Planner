from __future__ import annotations

from typing import List, Optional

from pydantic import AnyHttpUrl, Field
from pydantic import field_validator
from pydantic import model_validator

from domain.models.models import ContentPlanOutput, DraftAnalysis, Platform, SocialPost
from shared.base import BaseModel


class ContentPlanAPIInput(BaseModel):
    """Request body for POST /api/v1/content-plan."""

    url: AnyHttpUrl = Field(
        ...,
        description="URL of the article/blog post to generate content from.",
        examples=["https://example.com/my-blog-post"],
    )
    additional_context: Optional[str] = Field(
        None,
        description="Optional extra context to guide the AI (target audience, tone, restrictions…)",
        examples=["Focus on B2B SaaS audience, keep it professional."],
    )
    selected_model: Optional[str] = Field(
        None,
        max_length=128,
        description="Optional model selected from FE; provider is inferred from model prefix.",
        examples=["gpt-5.4", "claude-sonnet-4-6", "gemini-2.5-pro"],
    )
    project_id: Optional[str] = Field(
        None,
        max_length=64,
        description="Optional project id to persist content plan snapshot into run history.",
    )
    conversation_id: Optional[str] = Field(
        None,
        max_length=64,
        description="Optional conversation id to persist content plan snapshot into run history.",
    )

    @field_validator("selected_model")
    @classmethod
    def validate_selected_model(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("project_id", "conversation_id")
    @classmethod
    def validate_optional_ids(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @model_validator(mode="after")
    def validate_snapshot_binding(self) -> "ContentPlanAPIInput":
        has_project = bool(self.project_id)
        has_conversation = bool(self.conversation_id)
        if has_project != has_conversation:
            raise ValueError("project_id and conversation_id must be provided together.")
        return self


class SocialPostResponse(BaseModel):
    """Single platform post in the API response."""

    platform: Platform
    hook: str
    body_content: str
    call_to_action: str
    hashtags: List[str]

    @classmethod
    def from_domain(cls, post: SocialPost) -> "SocialPostResponse":
        return cls(
            platform=post.platform,
            hook=post.hook,
            body_content=post.body_content,
            call_to_action=post.call_to_action,
            hashtags=post.hashtags,
        )


class ContentPlanAPIData(BaseModel):
    """Payload inside a successful response."""

    source_url: str
    analysis: DraftAnalysis
    social_posts: List[SocialPostResponse]

    @classmethod
    def from_domain(cls, output: ContentPlanOutput) -> "ContentPlanAPIData":
        return cls(
            source_url=output.source_url,
            analysis=output.analysis,
            social_posts=[
                SocialPostResponse.from_domain(p) for p in output.social_posts
            ],
        )


class ContentPlanAPIOutput(BaseModel):
    """Unified HTTP response envelope for POST /api/v1/content-plan."""

    success: bool = Field(
        ..., description="True if the pipeline finished without error."
    )
    data: Optional[ContentPlanAPIData] = Field(
        None, description="Result payload on success."
    )
    error: Optional[str] = Field(None, description="Error message on failure.")
