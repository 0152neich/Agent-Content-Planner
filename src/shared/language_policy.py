from __future__ import annotations

import re
from typing import Literal

TargetLanguage = Literal["vi", "en"]

_VI_MARKER_WORDS = {
    "va",
    "v\u00e0",
    "cua",
    "c\u1ee7a",
    "cho",
    "la",
    "l\u00e0",
    "voi",
    "v\u1edbi",
    "khong",
    "kh\u00f4ng",
    "nguoi",
    "ng\u01b0\u1eddi",
    "ban",
    "b\u1ea1n",
    "noi",
    "n\u1ed9i",
    "dung",
    "bai",
    "b\u00e0i",
    "viet",
    "vi\u1ebft",
}
_EN_MARKER_WORDS = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "that",
    "this",
    "you",
    "your",
    "post",
    "content",
    "please",
    "rewrite",
    "focus",
    "audience",
}
_VI_DIACRITIC_PATTERN = re.compile(
    r"[\u0103\u00e2\u0111\u00ea\u00f4\u01a1\u01b0\u00e1\u00e0\u1ea3\u00e3\u1ea1\u1ea5\u1ea7\u1ea9\u1eab\u1ead\u1eaf\u1eb1\u1eb3\u1eb5\u1eb7\u00e9\u00e8\u1ebb\u1ebd\u1eb9\u1ebf\u1ec1\u1ec3\u1ec5\u1ec7\u00ed\u00ec\u1ec9\u0129\u1ecb\u00f3\u00f2\u1ecf\u00f5\u1ecd\u1ed1\u1ed3\u1ed5\u1ed7\u1ed9\u1edb\u1edd\u1edf\u1ee1\u1ee3\u00fa\u00f9\u1ee7\u0169\u1ee5\u1ee9\u1eeb\u1eed\u1eef\u1ef1\u00fd\u1ef3\u1ef7\u1ef9\u1ef5]",
    flags=re.IGNORECASE,
)
_TOKEN_PATTERN = re.compile(r"[a-zA-Z\u00C0-\u1EF9']+")


class LanguagePolicyService:
    """Deterministic language selector for current prompt context."""

    @staticmethod
    def detect_target_language(prompt: str | None) -> TargetLanguage:
        normalized = (prompt or "").strip()
        if not normalized:
            return "vi"

        lowered = normalized.lower()
        tokens = _TOKEN_PATTERN.findall(lowered)
        vi_score = len(_VI_DIACRITIC_PATTERN.findall(lowered))
        en_score = 0

        for token in tokens:
            if token in _VI_MARKER_WORDS:
                vi_score += 1
            if token in _EN_MARKER_WORDS:
                en_score += 1

        if vi_score == 0 and en_score == 0:
            # Ambiguous short prompts should keep existing product default.
            return "vi"
        return "vi" if vi_score >= en_score else "en"

    @staticmethod
    def language_name(target_language: TargetLanguage) -> str:
        return "Vietnamese" if target_language == "vi" else "English"
