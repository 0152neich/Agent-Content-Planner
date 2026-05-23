from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from app.services.chat_contracts import ChatAction
from app.services.chat_intent_router import ChatIntentRouter, _Stage1Output, _Stage2Output


def test_route_returns_general_qa_when_stage1_classifies_general_qa() -> None:
    router = ChatIntentRouter()
    with (
        patch.object(
            ChatIntentRouter,
            "_run_stage1",
            return_value=_Stage1Output(
                intent_class="GENERAL_QA",
                confidence=0.84,
                reason="Casual greeting.",
            ),
        ),
        patch.object(ChatIntentRouter, "_run_stage2") as stage2,
    ):
        intent = router.route("facebook là gì")

    assert intent.action == ChatAction.GENERAL_QA
    assert intent.confidence == 0.84
    assert stage2.call_count == 0


def test_route_forces_general_qa_for_strong_small_talk_prompt() -> None:
    router = ChatIntentRouter()
    with (
        patch.object(ChatIntentRouter, "_run_stage1") as stage1,
        patch.object(ChatIntentRouter, "_run_stage2") as stage2,
    ):
        intent = router.route("ok")

    assert intent.action == ChatAction.GENERAL_QA
    assert intent.reason == "Forced GENERAL_QA by strong small-talk resolver."
    assert stage1.call_count == 0
    assert stage2.call_count == 0


def test_route_returns_clarify_when_stage1_requests_clarification() -> None:
    router = ChatIntentRouter()
    with patch.object(
        ChatIntentRouter,
        "_run_stage1",
        return_value=_Stage1Output(
            intent_class="CLARIFY",
            confidence=0.62,
            reason="Missing target.",
            clarify_question="Bạn muốn mình chỉnh Facebook hay LinkedIn?",
        ),
    ):
        intent = router.route("chinh lai bang tieng anh")

    assert intent.action == ChatAction.CLARIFY
    assert intent.needs_clarification is True
    assert "Facebook" in (intent.clarify_question or "")


def test_route_runs_stage2_for_action_request_and_returns_action() -> None:
    router = ChatIntentRouter()
    with (
        patch.object(
            ChatIntentRouter,
            "_run_stage1",
            return_value=_Stage1Output(
                intent_class="ACTION_REQUEST",
                confidence=0.88,
                reason="Editing request.",
            ),
        ),
        patch.object(
            ChatIntentRouter,
            "_run_stage2",
            return_value=_Stage2Output(
                action=ChatAction.REWRITE_FACEBOOK_ONLY.value,
                target_platform="facebook",
                confidence=0.83,
                needs_clarification=False,
                reason="Resolved to rewrite facebook.",
            ),
        ),
    ):
        intent = router.route("đổi bài này sang tiếng Anh")

    assert intent.action == ChatAction.REWRITE_FACEBOOK_ONLY
    assert intent.target_platform == "facebook"
    assert intent.needs_clarification is False


def test_route_returns_clarify_when_stage2_requires_clarification() -> None:
    router = ChatIntentRouter()
    with (
        patch.object(
            ChatIntentRouter,
            "_run_stage1",
            return_value=_Stage1Output(
                intent_class="ACTION_REQUEST",
                confidence=0.78,
                reason="Likely edit request.",
            ),
        ),
        patch.object(
            ChatIntentRouter,
            "_run_stage2",
            return_value=_Stage2Output(
                action=ChatAction.CLARIFY.value,
                confidence=0.55,
                needs_clarification=True,
                clarify_question="Bạn muốn chỉnh Facebook hay LinkedIn?",
                reason="Target ambiguous.",
            ),
        ),
    ):
        intent = router.route("chinh lai")

    assert intent.action == ChatAction.CLARIFY
    assert intent.needs_clarification is True


def test_route_returns_clarify_on_invalid_stage2_action() -> None:
    router = ChatIntentRouter()
    with (
        patch.object(
            ChatIntentRouter,
            "_run_stage1",
            return_value=_Stage1Output(
                intent_class="ACTION_REQUEST",
                confidence=0.78,
                reason="Likely edit request.",
            ),
        ),
        patch.object(
            ChatIntentRouter,
            "_run_stage2",
            return_value=_Stage2Output(
                action="UNSUPPORTED_ACTION",
                confidence=0.12,
                needs_clarification=False,
                reason="Bad action.",
            ),
        ),
    ):
        intent = router.route("chinh lai")

    assert intent.action == ChatAction.CLARIFY
    assert intent.needs_clarification is True


def test_route_includes_stage1_stage2_routing_metadata_for_action() -> None:
    router = ChatIntentRouter()
    with (
        patch.object(
            ChatIntentRouter,
            "_run_stage1",
            return_value=_Stage1Output(
                intent_class="ACTION_REQUEST",
                confidence=0.91,
                reason="Action request.",
            ),
        ),
        patch.object(
            ChatIntentRouter,
            "_run_stage2",
            return_value=_Stage2Output(
                action=ChatAction.REWRITE_FACEBOOK_ONLY.value,
                target_platform="facebook",
                confidence=0.86,
                needs_clarification=False,
                reason="Resolved.",
            ),
        ),
    ):
        intent = router.route("chuyển bài fb sang tiếng Anh")

    assert intent.action == ChatAction.REWRITE_FACEBOOK_ONLY
    assert intent.routing_metadata.get("stage1", {}).get("intent_class") == "ACTION_REQUEST"
    assert intent.routing_metadata.get("stage2", {}).get("action") == "REWRITE_FACEBOOK_ONLY"
    assert intent.routing_metadata.get("router_policy_version") == "v1"


def test_route_returns_clarify_when_stage1_confidence_below_threshold() -> None:
    router = ChatIntentRouter()
    with patch.object(
        ChatIntentRouter,
        "_run_stage1",
        return_value=_Stage1Output(
            intent_class="ACTION_REQUEST",
            confidence=0.4,
            reason="low confidence",
        ),
    ):
        intent = router.route("viết lại")

    assert intent.action == ChatAction.CLARIFY
    assert intent.routing_metadata.get("ambiguity_type") == "low_confidence_stage1"


def test_route_returns_clarify_when_stage2_confidence_below_threshold() -> None:
    router = ChatIntentRouter()
    with (
        patch.object(
            ChatIntentRouter,
            "_run_stage1",
            return_value=_Stage1Output(
                intent_class="ACTION_REQUEST",
                confidence=0.9,
                reason="Action request.",
            ),
        ),
        patch.object(
            ChatIntentRouter,
            "_run_stage2",
            return_value=_Stage2Output(
                action=ChatAction.REWRITE_FACEBOOK_ONLY.value,
                target_platform="facebook",
                confidence=0.5,
                needs_clarification=False,
                reason="Uncertain",
            ),
        ),
    ):
        intent = router.route("viết lại bài")

    assert intent.action == ChatAction.CLARIFY
    assert intent.routing_metadata.get("ambiguity_type") == "low_confidence_stage2"


def test_route_overrides_platform_by_explicit_prompt_platform() -> None:
    router = ChatIntentRouter()
    with (
        patch.object(
            ChatIntentRouter,
            "_run_stage1",
            return_value=_Stage1Output(
                intent_class="ACTION_REQUEST",
                confidence=0.91,
                reason="Action request.",
            ),
        ),
        patch.object(
            ChatIntentRouter,
            "_run_stage2",
            return_value=_Stage2Output(
                action=ChatAction.REWRITE_FACEBOOK_ONLY.value,
                target_platform="facebook",
                confidence=0.86,
                needs_clarification=False,
                reason="Resolved.",
            ),
        ),
    ):
        intent = router.route("sửa LinkedIn")

    assert intent.action == ChatAction.REWRITE_LINKEDIN_ONLY
    assert intent.target_platform == "linkedin"
    assert intent.routing_metadata.get("resolver", {}).get("platform_override_applied") is True


def test_stage_models_use_explicit_crew_config_when_valid() -> None:
    settings_stub = SimpleNamespace(
        openai=SimpleNamespace(
            allowed_models_list=["gpt-5.4", "gpt-4.1"],
            model="gpt-5.4",
        ),
        crew=SimpleNamespace(
            router_stage1_model="gpt-5.4",
            router_stage2_model="gpt-4.1",
        ),
    )
    with patch("app.services.chat_intent_router.Settings", return_value=settings_stub):
        assert ChatIntentRouter._stage1_model() == "gpt-5.4"
        assert ChatIntentRouter._stage2_model() == "gpt-4.1"


def test_stage_models_fallback_when_explicit_model_invalid() -> None:
    settings_stub = SimpleNamespace(
        openai=SimpleNamespace(
            allowed_models_list=["gpt-4.1-mini", "gpt-4.1"],
            model="gpt-4.1-mini",
        ),
        crew=SimpleNamespace(
            router_stage1_model="gpt-unknown-mini",
            router_stage2_model="gpt-unknown-strong",
        ),
    )
    with patch("app.services.chat_intent_router.Settings", return_value=settings_stub):
        assert ChatIntentRouter._stage1_model() == "gpt-4.1-mini"
        assert ChatIntentRouter._stage2_model() == "gpt-4.1"
