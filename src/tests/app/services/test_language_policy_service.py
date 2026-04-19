from __future__ import annotations

from shared.language_policy import LanguagePolicyService


def test_detect_target_language_returns_vietnamese_for_vietnamese_prompt() -> None:
    service = LanguagePolicyService()
    assert (
        service.detect_target_language(
            "Hãy viết lại bài đăng này tự nhiên và dễ đọc hơn."
        )
        == "vi"
    )


def test_detect_target_language_returns_english_for_english_prompt() -> None:
    service = LanguagePolicyService()
    assert (
        service.detect_target_language(
            "Please rewrite this post to sound smoother and more complete."
        )
        == "en"
    )


def test_detect_target_language_defaults_to_vietnamese_when_ambiguous() -> None:
    service = LanguagePolicyService()
    assert service.detect_target_language("b2b") == "vi"
