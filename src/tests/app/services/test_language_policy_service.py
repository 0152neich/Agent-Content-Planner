from __future__ import annotations

from shared.language_policy import LanguagePolicyService


def test_detect_target_language_returns_vietnamese_for_vietnamese_prompt() -> None:
    service = LanguagePolicyService()
    assert (
        service.detect_target_language(
            "H\u00e3y vi\u1ebft l\u1ea1i b\u00e0i \u0111\u0103ng n\u00e0y t\u1ef1 nhi\u00ean v\u00e0 d\u1ec5 \u0111\u1ecdc h\u01a1n."
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
