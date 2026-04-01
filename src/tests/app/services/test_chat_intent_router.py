from __future__ import annotations

from app.services.chat_contracts import ChatAction
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
