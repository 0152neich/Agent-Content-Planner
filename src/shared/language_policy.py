from __future__ import annotations

import re
from typing import Literal

TargetLanguage = Literal["vi", "en"]

_VI_MARKER_WORDS = {
    "và",
    "của",
    "cho",
    "là",
    "với",
    "không",
    "người",
    "bạn",
    "nội",
    "dung",
    "bài",
    "viết",
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
    r"[ăâđêôơưáàảãạấầẩẫậắằẳẵặéèẻẽẹếềểễệíìỉĩịóòỏõọốồổỗộớờởỡợúùủũụứừửữựýỳỷỹỵ]",
    flags=re.IGNORECASE,
)
_TOKEN_PATTERN = re.compile(r"[a-zA-ZÀ-ỹ']+")


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
