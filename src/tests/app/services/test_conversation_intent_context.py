from __future__ import annotations

from datetime import datetime, timezone

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
