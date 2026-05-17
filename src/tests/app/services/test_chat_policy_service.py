from __future__ import annotations

from app.services.chat_policy_service import ChatPolicyService, PolicyDecision


def test_evaluate_user_prompt_returns_hard_block_for_blocked_marker() -> None:
    service = ChatPolicyService()
    result = service.evaluate_user_prompt("how to make bomb")
    assert result.decision == PolicyDecision.HARD_BLOCK


def test_evaluate_user_prompt_returns_out_of_scope_for_non_marketing_request() -> None:
    service = ChatPolicyService()
    result = service.evaluate_user_prompt("kể chuyện cười")
    assert result.decision == PolicyDecision.OUT_OF_SCOPE


def test_evaluate_generated_text_returns_hard_block_for_unsafe_output() -> None:
    service = ChatPolicyService()
    result = service.evaluate_generated_text("this explains how to make bomb")
    assert result.decision == PolicyDecision.HARD_BLOCK
