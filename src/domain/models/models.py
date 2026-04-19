from enum import Enum
from typing import Any, List, Optional

from pydantic import Field, field_validator, model_validator

from shared.base import BaseModel


class Platform(str, Enum):
    LINKEDIN = "linkedin"
    FACEBOOK = "facebook"


# 1. Input
class ContentInput(BaseModel):
    url: str = Field(
        ..., description="The URL of the original article/blog to be analyzed"
    )
    additional_context: Optional[str] = Field(
        None, description="Additional context from the user (if any)"
    )


class ReaderIntent(str, Enum):
    LEARN = "learn"
    EVALUATE = "evaluate"
    ACT = "act"


class FunnelStage(str, Enum):
    AWARENESS = "awareness"
    CONSIDERATION = "consideration"
    DECISION = "decision"


class SupportingClaim(BaseModel):
    claim: str = Field(..., min_length=1, description="Insight claim from the article")
    evidence_excerpt: str = Field(
        ...,
        min_length=1,
        description="Verbatim or near-verbatim excerpt from source content",
    )
    evidence_reason: str = Field(
        ...,
        min_length=1,
        description="Why this excerpt supports the claim",
    )

    @field_validator("claim", "evidence_excerpt", "evidence_reason")
    @classmethod
    def _normalize_non_blank_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Supporting claim fields must not be blank.")
        return normalized


# 2. Output of Analyzer Agent
class DraftAnalysis(BaseModel):
    core_message: str = Field(
        ..., description="The core message of the article (1 sentence)"
    )
    value_proposition: str = Field(
        ..., description="Main value proposition for target audience"
    )
    reader_intent: ReaderIntent = Field(
        ..., description="Primary reader intent: learn, evaluate, or act"
    )
    funnel_stage: FunnelStage = Field(
        ..., description="Primary funnel stage: awareness, consideration, or decision"
    )
    target_audience: str = Field(..., description="Description of the target audience")
    audience_pain_points: List[str] = Field(
        ..., min_length=3, max_length=5, description="List of 3-5 pain points"
    )
    audience_desired_outcomes: List[str] = Field(
        ..., min_length=3, max_length=5, description="List of 3-5 desired outcomes"
    )
    key_takeaways: List[str] = Field(
        ..., min_length=3, max_length=5, description="List of 3-5 key takeaways"
    )
    supporting_claims: List[SupportingClaim] = Field(
        ...,
        min_length=3,
        max_length=5,
        description="List of 3-5 claims, each with supporting evidence excerpt",
    )
    tone_of_voice: str = Field(
        ...,
        description="Tone of voice of the original article (e.g. Academic, Humorous, Formal...)",
    )
    voice_guidelines: List[str] = Field(
        ...,
        min_length=3,
        max_length=5,
        description="List of 3-5 writing guardrails for future content generation",
    )
    primary_cta: str = Field(..., description="Primary call-to-action direction")
    cta_reasoning: str = Field(..., description="Reasoning behind CTA recommendation")
    risk_flags: List[str] = Field(
        ..., min_length=2, max_length=4, description="List of 2-4 content risks"
    )
    confidence_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score of analysis quality in [0, 1]",
    )
    missing_information: List[str] = Field(
        default_factory=list,
        description="Information gaps that were not inferable from source article",
    )

    @field_validator(
        "core_message",
        "value_proposition",
        "target_audience",
        "tone_of_voice",
        "primary_cta",
        "cta_reasoning",
    )
    @classmethod
    def _normalize_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Required analysis text fields must not be blank.")
        return normalized

    @field_validator(
        "key_takeaways",
        "audience_pain_points",
        "audience_desired_outcomes",
        "voice_guidelines",
        "risk_flags",
        "missing_information",
    )
    @classmethod
    def _normalize_text_list(cls, values: List[str]) -> List[str]:
        normalized = [item.strip() for item in values if item and item.strip()]
        return normalized

    @model_validator(mode="after")
    def _validate_collection_constraints(self) -> "DraftAnalysis":
        if len(self.key_takeaways) < 3 or len(self.key_takeaways) > 5:
            raise ValueError("key_takeaways must contain 3-5 items.")
        if len(self.audience_pain_points) < 3 or len(self.audience_pain_points) > 5:
            raise ValueError("audience_pain_points must contain 3-5 items.")
        if (
            len(self.audience_desired_outcomes) < 3
            or len(self.audience_desired_outcomes) > 5
        ):
            raise ValueError("audience_desired_outcomes must contain 3-5 items.")
        if len(self.supporting_claims) < 3 or len(self.supporting_claims) > 5:
            raise ValueError("supporting_claims must contain 3-5 items.")
        if len(self.voice_guidelines) < 3 or len(self.voice_guidelines) > 5:
            raise ValueError("voice_guidelines must contain 3-5 items.")
        if len(self.risk_flags) < 2 or len(self.risk_flags) > 4:
            raise ValueError("risk_flags must contain 2-4 items.")
        return self

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "DraftAnalysis":
        if not isinstance(payload, dict):
            raise ValueError("Analysis payload must be an object.")

        def _to_text(value: Any) -> str:
            return str(value).strip() if value is not None else ""

        def _to_list(value: Any) -> list[str]:
            if not isinstance(value, list):
                return []
            return [str(item).strip() for item in value if str(item).strip()]

        key_takeaways = _to_list(payload.get("key_takeaways"))
        if not key_takeaways:
            key_takeaways = [
                "The article's key takeaway is not explicitly extractable from current content."
            ]
        while len(key_takeaways) < 3:
            key_takeaways.append(key_takeaways[-1])
        key_takeaways = key_takeaways[:5]

        tone = _to_text(payload.get("tone_of_voice")) or "Informative"
        target_audience = _to_text(payload.get("target_audience")) or "General audience"
        core_message = (
            _to_text(payload.get("core_message")) or "No core message extracted."
        )
        value_proposition = _to_text(payload.get("value_proposition")) or (
            f"This content helps {target_audience.lower()} understand the core topic."
        )

        pain_points = _to_list(payload.get("audience_pain_points"))
        if len(pain_points) < 3:
            pain_points = [
                "Hard to identify what matters most in the topic.",
                "Lack of practical direction for applying insights.",
                "Need faster understanding without reading many sources.",
            ]
        pain_points = pain_points[:5]

        desired_outcomes = _to_list(payload.get("audience_desired_outcomes"))
        if len(desired_outcomes) < 3:
            desired_outcomes = [
                "Understand the topic quickly and accurately.",
                "Apply insights into practical content actions.",
                "Communicate value clearly to their own audience.",
            ]
        desired_outcomes = desired_outcomes[:5]

        claims_raw = payload.get("supporting_claims")
        supporting_claims: list[dict[str, str]] = []
        if isinstance(claims_raw, list):
            for raw in claims_raw:
                if not isinstance(raw, dict):
                    continue
                claim = _to_text(raw.get("claim"))
                excerpt = _to_text(raw.get("evidence_excerpt"))
                reason = _to_text(raw.get("evidence_reason"))
                if claim and excerpt and reason:
                    supporting_claims.append(
                        {
                            "claim": claim,
                            "evidence_excerpt": excerpt,
                            "evidence_reason": reason,
                        }
                    )
        if len(supporting_claims) < 3:
            fallback_claim = key_takeaways[:3]
            supporting_claims = [
                {
                    "claim": item,
                    "evidence_excerpt": item,
                    "evidence_reason": "Derived from available article summary context.",
                }
                for item in fallback_claim
            ]
        supporting_claims = supporting_claims[:5]

        voice_guidelines = _to_list(payload.get("voice_guidelines"))
        if len(voice_guidelines) < 3:
            voice_guidelines = [
                "Keep message concrete and audience-specific.",
                "Use clear, direct language with practical examples.",
                "Maintain consistent tone aligned with source material.",
            ]
        voice_guidelines = voice_guidelines[:5]

        risk_flags = _to_list(payload.get("risk_flags"))
        if len(risk_flags) < 2:
            risk_flags = [
                "Source may not include enough quantified evidence for strong claims.",
                "Some recommendations might require additional business context.",
            ]
        risk_flags = risk_flags[:4]

        missing_information = _to_list(payload.get("missing_information"))
        if not missing_information:
            missing_information = [
                "No explicit conversion benchmark or success metric provided."
            ]

        reader_intent_raw = _to_text(payload.get("reader_intent")).lower()
        funnel_stage_raw = _to_text(payload.get("funnel_stage")).lower()
        if reader_intent_raw not in {"learn", "evaluate", "act"}:
            reader_intent_raw = "learn"
        if funnel_stage_raw not in {"awareness", "consideration", "decision"}:
            funnel_stage_raw = "awareness"

        confidence_raw = payload.get("confidence_score")
        try:
            confidence_score = float(confidence_raw)
        except (TypeError, ValueError):
            confidence_score = 0.6
        confidence_score = max(0.0, min(1.0, confidence_score))

        normalized_payload = {
            "core_message": core_message,
            "value_proposition": value_proposition,
            "reader_intent": reader_intent_raw,
            "funnel_stage": funnel_stage_raw,
            "target_audience": target_audience,
            "audience_pain_points": pain_points,
            "audience_desired_outcomes": desired_outcomes,
            "key_takeaways": key_takeaways,
            "supporting_claims": supporting_claims,
            "tone_of_voice": tone,
            "voice_guidelines": voice_guidelines,
            "primary_cta": _to_text(payload.get("primary_cta"))
            or "Guide readers to the next concrete action relevant to the topic.",
            "cta_reasoning": _to_text(payload.get("cta_reasoning"))
            or "CTA aligns with user intent inferred from article context.",
            "risk_flags": risk_flags,
            "confidence_score": confidence_score,
            "missing_information": missing_information,
        }
        return cls.model_validate(normalized_payload)


# 3. Output of Copywriter Agent for a specific post
class SocialPost(BaseModel):
    platform: Platform = Field(..., description="The social media platform to target")
    hook: str = Field(..., description="The hook of the post (e.g. 'Did you know?')")
    body_content: str = Field(
        ..., description="The main content of the post, segmented into paragraphs"
    )
    call_to_action: str = Field(
        ...,
        description="The call to action of the post (e.g. 'Click here to learn more')",
    )
    hashtags: List[str] = Field(
        ..., description="List of 3-5 hashtags suitable for the post"
    )


# 4. Bundle — output of write_task and review_task (all platforms in one pass)
class SocialPostsBundle(BaseModel):
    posts: List[SocialPost] = Field(
        ...,
        description="List of social media posts, one per platform (linkedin, facebook)",
    )


# 5. Final Deliverable
class ContentPlanOutput(BaseModel):
    source_url: str = Field(
        ..., description="The URL of the original article/blog that has been analyzed"
    )
    analysis: DraftAnalysis = Field(
        ..., description="The detailed analysis of the original article/blog"
    )
    social_posts: List[SocialPost] = Field(
        ..., description="List of posts optimized for each social media platform"
    )
