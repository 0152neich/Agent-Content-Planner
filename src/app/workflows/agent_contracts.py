from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from shared.language_policy import LanguagePolicyService, TargetLanguage
from domain.models.models import DraftAnalysis, Platform, SocialPost, SocialPostsBundle


@dataclass(slots=True)
class WorkflowContractError(Exception):
    code: str
    stage: str
    detail: str

    def __str__(self) -> str:
        return f"{self.code} at {self.stage}: {self.detail}"


class AgentContractGateway:
    def __init__(self) -> None:
        self._language_policy = LanguagePolicyService()

    def validate_analysis(
        self,
        analysis: DraftAnalysis,
        *,
        target_language: TargetLanguage,
        stage: str,
    ) -> tuple[DraftAnalysis, bool]:
        return self._validate_with_single_repair(
            value=analysis,
            stage=stage,
            validator=lambda value: self._validate_analysis_business(
                value, target_language=target_language
            ),
            repairer=self._repair_analysis,
            repair_label="analysis",
        )

    def validate_social_post(
        self,
        post: SocialPost,
        *,
        target_language: TargetLanguage,
        stage: str,
        expected_platform: Platform | None = None,
    ) -> tuple[SocialPost, bool]:
        return self._validate_with_single_repair(
            value=post,
            stage=stage,
            validator=lambda value: self._validate_social_post_business(
                value,
                target_language=target_language,
                expected_platform=expected_platform,
            ),
            repairer=lambda value: self._repair_social_post(
                value, expected_platform=expected_platform
            ),
            repair_label="social_post",
        )

    def validate_social_posts_bundle(
        self,
        bundle: SocialPostsBundle,
        *,
        target_language: TargetLanguage,
        stage: str,
    ) -> tuple[SocialPostsBundle, bool]:
        return self._validate_with_single_repair(
            value=bundle,
            stage=stage,
            validator=lambda value: self._validate_bundle_business(
                value, target_language=target_language
            ),
            repairer=self._repair_bundle,
            repair_label="social_posts_bundle",
        )

    def _validate_with_single_repair(
        self,
        *,
        value,
        stage: str,
        validator: Callable[[object], None],
        repairer: Callable[[object], object],
        repair_label: str,
    ) -> tuple[object, bool]:
        try:
            validator(value)
            return value, False
        except ValueError as first_error:
            repaired = repairer(value)
            try:
                validator(repaired)
                return repaired, True
            except ValueError as second_error:
                raise WorkflowContractError(
                    code="WORKFLOW_CONTRACT_REPAIR_FAILED",
                    stage=stage,
                    detail=(
                        f"{repair_label} failed validation after single repair attempt. "
                        f"first_error={first_error}; second_error={second_error}"
                    ),
                ) from second_error

    def _validate_analysis_business(
        self,
        analysis: DraftAnalysis,
        *,
        target_language: TargetLanguage,
    ) -> None:
        if not analysis.supporting_claims:
            raise ValueError("Analysis must include supporting claims.")

        text_fields = [
            analysis.core_message,
            analysis.value_proposition,
            analysis.target_audience,
            analysis.tone_of_voice,
            analysis.primary_cta,
            analysis.cta_reasoning,
            *analysis.key_takeaways,
            *analysis.audience_pain_points,
            *analysis.audience_desired_outcomes,
            *analysis.voice_guidelines,
            *analysis.risk_flags,
        ]
        for claim in analysis.supporting_claims:
            text_fields.extend(
                [claim.claim, claim.evidence_excerpt, claim.evidence_reason]
            )
        if any(not field.strip() for field in text_fields):
            raise ValueError("Analysis contains blank required fields.")
        if not self._is_language_aligned(
            " ".join(text_fields),
            target_language=target_language,
        ):
            raise ValueError(f"Analysis language mismatch. expected={target_language}.")

    def _validate_bundle_business(
        self,
        bundle: SocialPostsBundle,
        *,
        target_language: TargetLanguage,
    ) -> None:
        if len(bundle.posts) != 2:
            raise ValueError("Bundle must contain exactly 2 posts.")
        platforms = {post.platform for post in bundle.posts}
        if platforms != {Platform.LINKEDIN, Platform.FACEBOOK}:
            raise ValueError("Bundle must include linkedin and facebook posts exactly.")
        for post in bundle.posts:
            self._validate_social_post_business(
                post,
                target_language=target_language,
                expected_platform=post.platform,
            )

    def _validate_social_post_business(
        self,
        post: SocialPost,
        *,
        target_language: TargetLanguage,
        expected_platform: Platform | None,
    ) -> None:
        if expected_platform is not None and post.platform != expected_platform:
            raise ValueError(
                f"Platform mismatch. expected={expected_platform.value}, actual={post.platform.value}."
            )
        required = [post.hook, post.body_content, post.call_to_action]
        if any(not item.strip() for item in required):
            raise ValueError("Social post contains blank required fields.")
        if len(post.hashtags) < 3 or len(post.hashtags) > 5:
            raise ValueError("Social post hashtags must contain 3-5 items.")
        normalized_tags = [self._normalize_hashtag(tag) for tag in post.hashtags]
        if any(not tag for tag in normalized_tags):
            raise ValueError("Social post hashtags must not be blank.")
        if len(set(tag.lower() for tag in normalized_tags)) != len(normalized_tags):
            raise ValueError("Social post hashtags must be unique.")
        char_limit = 3000 if post.platform == Platform.LINKEDIN else 2000
        total_chars = len(post.hook) + len(post.body_content) + len(post.call_to_action)
        if total_chars > char_limit:
            raise ValueError(
                f"Social post exceeds char limit for {post.platform.value}: "
                f"{total_chars}>{char_limit}."
            )
        merged_text = f"{post.hook} {post.body_content} {post.call_to_action}"
        if not self._is_language_aligned(merged_text, target_language=target_language):
            raise ValueError(
                f"Social post language mismatch. expected={target_language}."
            )

    def _repair_analysis(self, analysis: DraftAnalysis) -> DraftAnalysis:
        payload = analysis.model_dump(mode="python")
        text_keys = [
            "core_message",
            "value_proposition",
            "target_audience",
            "tone_of_voice",
            "primary_cta",
            "cta_reasoning",
        ]
        for key in text_keys:
            payload[key] = self._normalize_text(payload.get(key, ""))
        list_keys = [
            "key_takeaways",
            "audience_pain_points",
            "audience_desired_outcomes",
            "voice_guidelines",
            "risk_flags",
            "missing_information",
        ]
        for key in list_keys:
            payload[key] = self._normalize_text_list(payload.get(key, []))
        payload["supporting_claims"] = [
            {
                "claim": self._normalize_text(item.get("claim", "")),
                "evidence_excerpt": self._normalize_text(
                    item.get("evidence_excerpt", "")
                ),
                "evidence_reason": self._normalize_text(
                    item.get("evidence_reason", "")
                ),
            }
            for item in payload.get("supporting_claims", [])
            if isinstance(item, dict)
        ]
        return DraftAnalysis.model_validate(payload)

    def _repair_bundle(self, bundle: SocialPostsBundle) -> SocialPostsBundle:
        posts_by_platform: dict[Platform, SocialPost] = {}
        for post in bundle.posts:
            normalized = self._repair_social_post(post, expected_platform=post.platform)
            posts_by_platform[normalized.platform] = normalized
        normalized_posts = [
            posts_by_platform[Platform.LINKEDIN]
            for _ in [0]
            if Platform.LINKEDIN in posts_by_platform
        ] + [
            posts_by_platform[Platform.FACEBOOK]
            for _ in [0]
            if Platform.FACEBOOK in posts_by_platform
        ]
        return SocialPostsBundle(posts=normalized_posts)

    def _repair_social_post(
        self,
        post: SocialPost,
        *,
        expected_platform: Platform | None,
    ) -> SocialPost:
        del expected_platform
        platform = post.platform
        hook = self._normalize_text(post.hook)
        body_content = self._normalize_text(post.body_content)
        call_to_action = self._normalize_text(post.call_to_action)

        unique_tags: list[str] = []
        seen: set[str] = set()
        for raw_tag in post.hashtags:
            normalized_tag = self._normalize_hashtag(raw_tag)
            if not normalized_tag:
                continue
            lowered = normalized_tag.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            unique_tags.append(normalized_tag)

        unique_tags = unique_tags[:5]

        return SocialPost(
            platform=platform,
            hook=hook,
            body_content=body_content,
            call_to_action=call_to_action,
            hashtags=unique_tags,
        )

    @staticmethod
    def _normalize_text(value: str) -> str:
        return " ".join(str(value or "").strip().split())

    def _normalize_text_list(self, values: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for item in values:
            text = self._normalize_text(item)
            if not text:
                continue
            lowered = text.lower()
            if lowered in seen:
                continue
            normalized.append(text)
            seen.add(lowered)
        return normalized

    @staticmethod
    def _normalize_hashtag(value: str) -> str:
        tag = str(value or "").strip()
        while tag.startswith("#"):
            tag = tag[1:]
        return "".join(tag.split())

    def _is_language_aligned(
        self,
        content: str,
        *,
        target_language: TargetLanguage,
    ) -> bool:
        compact = " ".join(content.strip().split())
        if len(compact) < 20:
            return True
        detected = self._language_policy.detect_target_language(compact)
        return detected == target_language
