from __future__ import annotations

from enum import Enum

from shared.base import BaseModel


class PolicyDecision(str, Enum):
    ALLOW = "ALLOW"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"
    HARD_BLOCK = "HARD_BLOCK"


class PolicySeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class PolicyCheckResult(BaseModel):
    decision: PolicyDecision
    reason: str
    severity: PolicySeverity = PolicySeverity.LOW
    suggested_reply: str | None = None


class ChatPolicyService(BaseModel):
    _BLOCK_MARKERS = {
        "how to make bomb",
        "make a bomb",
        "build bomb",
        "hack tài khoản",
        "hack account",
        "malware",
        "ransomware",
        "hate speech",
        "child sexual",
        "terrorist",
        "giết người",
    }
    _OUT_OF_SCOPE_MARKERS = {
        "kể chuyện cười",
        "tell me a joke",
        "xem bói",
        "predict lottery",
        "giải toán hộ",
        "homework answer",
        "viết malware",
        "crack wifi",
    }
    _UNSAFE_OUTPUT_MARKERS = {
        "how to make bomb",
        "build a bomb",
        "ransomware",
        "child sexual",
        "hate speech",
        "giết người",
    }
    _IN_SCOPE_MARKERS = {
        "facebook",
        "linkedin",
        "content",
        "bài viết",
        "bai viet",
        "hook",
        "cta",
        "chiến lược",
        "chien luoc",
        "rewrite",
        "reanalyze",
        "regenerate",
        "marketing",
        "campaign",
    }

    @staticmethod
    def _normalize(value: str | None) -> str:
        return " ".join((value or "").strip().lower().split())

    @staticmethod
    def _contains_any(text: str, markers: set[str]) -> bool:
        return any(marker in text for marker in markers)

    def evaluate_user_prompt(self, prompt: str) -> PolicyCheckResult:
        normalized = self._normalize(prompt)
        if not normalized:
            return PolicyCheckResult(
                decision=PolicyDecision.OUT_OF_SCOPE,
                severity=PolicySeverity.LOW,
                reason="Prompt is blank.",
                suggested_reply=(
                    "Mình cần thêm nội dung cụ thể để hỗ trợ. "
                    "Bạn có thể yêu cầu chỉnh Facebook, LinkedIn hoặc chiến lược."
                ),
            )
        if self._contains_any(normalized, self._BLOCK_MARKERS):
            return PolicyCheckResult(
                decision=PolicyDecision.HARD_BLOCK,
                severity=PolicySeverity.HIGH,
                reason="Prompt matches blocked safety policy markers.",
                suggested_reply=(
                    "Mình không thể hỗ trợ yêu cầu này. "
                    "Mình có thể giúp chỉnh nội dung marketing an toàn nếu bạn muốn."
                ),
            )
        if (
            self._contains_any(normalized, self._OUT_OF_SCOPE_MARKERS)
            and not self._contains_any(normalized, self._IN_SCOPE_MARKERS)
        ):
            return PolicyCheckResult(
                decision=PolicyDecision.OUT_OF_SCOPE,
                severity=PolicySeverity.MEDIUM,
                reason="Prompt is out of project scope.",
                suggested_reply=(
                    "Yêu cầu này chưa đúng phạm vi trợ lý content marketing. "
                    "Bạn có thể hỏi: 'Viết lại bài LinkedIn theo tone chuyên gia' "
                    "hoặc 'Chỉnh CTA cho bài Facebook'."
                ),
            )
        return PolicyCheckResult(
            decision=PolicyDecision.ALLOW,
            severity=PolicySeverity.LOW,
            reason="Prompt allowed by policy gate.",
        )

    def evaluate_generated_text(self, text: str) -> PolicyCheckResult:
        normalized = self._normalize(text)
        if not normalized:
            return PolicyCheckResult(
                decision=PolicyDecision.ALLOW,
                severity=PolicySeverity.LOW,
                reason="Empty generated text.",
            )
        if self._contains_any(normalized, self._UNSAFE_OUTPUT_MARKERS):
            return PolicyCheckResult(
                decision=PolicyDecision.HARD_BLOCK,
                severity=PolicySeverity.HIGH,
                reason="Generated output contains unsafe markers.",
                suggested_reply=(
                    "Mình không thể trả về nội dung này vì không phù hợp chính sách an toàn. "
                    "Mình có thể giúp viết lại theo hướng an toàn và phù hợp marketing."
                ),
            )
        return PolicyCheckResult(
            decision=PolicyDecision.ALLOW,
            severity=PolicySeverity.LOW,
            reason="Generated output allowed by policy gate.",
        )
