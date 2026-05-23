from __future__ import annotations

from datetime import datetime, timezone

import tiktoken
from app.services.chat_contracts import RecentChatMessage
from app.services.conversation_service import ConversationService


def test_extract_intent_context_from_payload_returns_context() -> None:
    context = ConversationService._extract_intent_context_from_payload(
        {
            "intent": {
                "action": "REWRITE_LINKEDIN_ONLY",
                "target_platform": "linkedin",
            },
            "action": "REWRITE_LINKEDIN_ONLY",
            "language_used": "en",
        },
        updated_at=datetime(2026, 4, 27, 12, 0, tzinfo=timezone.utc),
    )
    assert context is not None
    assert context.last_target_platform == "linkedin"
    assert context.last_action == "REWRITE_LINKEDIN_ONLY"
    assert context.last_language == "en"
    assert context.updated_at is not None


def test_extract_intent_context_from_payload_handles_missing_values() -> None:
    context = ConversationService._extract_intent_context_from_payload(
        {"intent": {}, "language_used": None}
    )
    assert context is None


def test_truncate_message_tokens_limits_to_1024_tokens() -> None:
    text = "hello " * 2000
    truncated = ConversationService._truncate_message_tokens(text)
    assert truncated
    encoding = tiktoken.get_encoding("cl100k_base")
    token_count = len(encoding.encode(truncated))
    assert token_count <= 1024


def test_recent_messages_digest_changes_when_content_changes() -> None:
    digest_a = ConversationService._recent_messages_digest(
        [RecentChatMessage(role="user", content="a")]
    )
    digest_b = ConversationService._recent_messages_digest(
        [RecentChatMessage(role="user", content="b")]
    )

    assert digest_a != digest_b


def test_next_active_context_clears_for_general_qa() -> None:
    context = ConversationService._next_active_context(
        current_context=None,
        resolved_intent={"action": "GENERAL_QA"},
        language_used="vi",
        updated_at=datetime(2026, 5, 12, 8, 0, tzinfo=timezone.utc),
    )
    assert context is None


def test_next_active_context_updates_for_edit_action() -> None:
    context = ConversationService._next_active_context(
        current_context=None,
        resolved_intent={
            "action": "REWRITE_FACEBOOK_ONLY",
            "target_platform": "facebook",
        },
        language_used="en",
        updated_at=datetime(2026, 5, 12, 8, 0, tzinfo=timezone.utc),
    )
    assert context is not None
    assert context.last_action == "REWRITE_FACEBOOK_ONLY"
    assert context.last_target_platform == "facebook"
    assert context.last_language == "en"
    assert context.updated_at is not None


def test_resolve_next_active_context_keeps_previous_when_refinement_fails() -> None:
    previous = ConversationService._extract_intent_context_from_payload(
        {
            "active_context": {
                "last_action": "REWRITE_LINKEDIN_ONLY",
                "last_target_platform": "linkedin",
                "last_language": "en",
            }
        }
    )
    assert previous is not None

    resolved = ConversationService._resolve_next_active_context_after_refinement(
        current_context=previous,
        refinement_status=False,
        resolved_intent={"action": "GENERAL_QA"},
        language_used="vi",
        updated_at=datetime(2026, 5, 12, 8, 0, tzinfo=timezone.utc),
    )
    assert resolved is not None
    assert resolved.last_action == "REWRITE_LINKEDIN_ONLY"
    assert resolved.last_target_platform == "linkedin"
    assert resolved.last_language == "en"
