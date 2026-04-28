from __future__ import annotations

from unittest.mock import patch

from app.services.chat_contracts import ChatAction, ChatIntent, IntentContext
from app.services.chat_intent_router import ChatIntentRouter


def test_route_rewrite_facebook_only() -> None:
    router = ChatIntentRouter()
    intent = router.route("sua bai facebook ngan gon hon")
    assert intent.action == ChatAction.REWRITE_FACEBOOK_ONLY
    assert intent.target_platform == "facebook"


def test_route_rewrite_linkedin_only() -> None:
    router = ChatIntentRouter()
    intent = router.route("viet lai bai linkedin chuyen nghiep hon")
    assert intent.action == ChatAction.REWRITE_LINKEDIN_ONLY
    assert intent.target_platform == "linkedin"


def test_route_reanalyze_only() -> None:
    router = ChatIntentRouter()
    intent = router.route("phan tich lai bai viet tu url")
    assert intent.action == ChatAction.REANALYZE_ONLY


def test_route_reanalyze_only_with_accented_vietnamese() -> None:
    router = ChatIntentRouter()
    intent = router.route("Bạn hãy viết lại bài phân tích sang ngôn ngữ tiếng Việt")
    assert intent.action == ChatAction.REANALYZE_ONLY


def test_route_rewrite_strategy_only() -> None:
    router = ChatIntentRouter()
    intent = router.route("cap nhat strategy cho campaign")
    assert intent.action == ChatAction.REWRITE_STRATEGY_ONLY


def test_route_full_regenerate() -> None:
    router = ChatIntentRouter()
    intent = router.route("regenerate all")
    assert intent.action == ChatAction.FULL_REGENERATE


def test_route_clarify_question() -> None:
    router = ChatIntentRouter()
    intent = router.route("tai sao bai linkedin nay chua on?")
    assert intent.action == ChatAction.CLARIFY


def test_route_ambiguous_followup_inherits_linkedin_from_intent_context() -> None:
    router = ChatIntentRouter()
    intent = router.route(
        "them phan dan dat truoc khi vao 3 y chinh",
        intent_context=IntentContext(
            last_target_platform="linkedin",
            last_action=ChatAction.REWRITE_LINKEDIN_ONLY.value,
            last_language="vi",
        ),
    )
    assert intent.action == ChatAction.REWRITE_LINKEDIN_ONLY
    assert intent.target_platform == "linkedin"


def test_route_ambiguous_followup_inherits_facebook_from_intent_context() -> None:
    router = ChatIntentRouter()
    intent = router.route(
        "add a stronger opening before the key points",
        intent_context=IntentContext(
            last_target_platform="facebook",
            last_action=ChatAction.REWRITE_FACEBOOK_ONLY.value,
            last_language="en",
        ),
    )
    assert intent.action == ChatAction.REWRITE_FACEBOOK_ONLY
    assert intent.target_platform == "facebook"


def test_route_explicit_platform_overrides_intent_context() -> None:
    router = ChatIntentRouter()
    intent = router.route(
        "rewrite facebook post with shorter CTA",
        intent_context=IntentContext(
            last_target_platform="linkedin",
            last_action=ChatAction.REWRITE_LINKEDIN_ONLY.value,
            last_language="en",
        ),
    )
    assert intent.action == ChatAction.REWRITE_FACEBOOK_ONLY
    assert intent.target_platform == "facebook"


def test_route_ambiguous_without_context_uses_fallback_path() -> None:
    router = ChatIntentRouter()
    fallback_intent = ChatIntent(
        action=ChatAction.GENERAL_QA,
        normalized_prompt="them phan dan dat truoc khi vao 3 y chinh",
        confidence=0.5,
        reason="fallback",
    )
    with patch.object(
        ChatIntentRouter,
        "_fallback_llm_intent",
        return_value=fallback_intent,
    ) as mocked_fallback:
        intent = router.route("them phan dan dat truoc khi vao 3 y chinh")

    assert mocked_fallback.call_count == 1
    assert intent.action == fallback_intent.action
