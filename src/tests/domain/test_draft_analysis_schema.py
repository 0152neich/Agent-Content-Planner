from __future__ import annotations

import pytest
from pydantic import ValidationError

from domain.models.models import DraftAnalysis


def _valid_payload() -> dict:
    return {
        "core_message": "Core message",
        "value_proposition": "Value proposition",
        "reader_intent": "learn",
        "funnel_stage": "awareness",
        "target_audience": "B2B marketers",
        "audience_pain_points": ["Pain 1", "Pain 2", "Pain 3"],
        "audience_desired_outcomes": ["Outcome 1", "Outcome 2", "Outcome 3"],
        "key_takeaways": ["Takeaway 1", "Takeaway 2", "Takeaway 3"],
        "supporting_claims": [
            {
                "claim": "Claim 1",
                "evidence_excerpt": "Excerpt 1",
                "evidence_reason": "Reason 1",
            },
            {
                "claim": "Claim 2",
                "evidence_excerpt": "Excerpt 2",
                "evidence_reason": "Reason 2",
            },
            {
                "claim": "Claim 3",
                "evidence_excerpt": "Excerpt 3",
                "evidence_reason": "Reason 3",
            },
        ],
        "tone_of_voice": "Professional",
        "voice_guidelines": ["Guideline 1", "Guideline 2", "Guideline 3"],
        "primary_cta": "Start now",
        "cta_reasoning": "Clear next step",
        "risk_flags": ["Risk 1", "Risk 2"],
        "confidence_score": 0.72,
        "missing_information": ["No benchmark data."],
    }


def test_draft_analysis_validation_passes_for_new_schema() -> None:
    model = DraftAnalysis.model_validate(_valid_payload())
    assert model.confidence_score == 0.72
    assert len(model.supporting_claims) == 3


def test_draft_analysis_validation_fails_when_claim_lacks_evidence_excerpt() -> None:
    payload = _valid_payload()
    payload["supporting_claims"][0]["evidence_excerpt"] = ""
    with pytest.raises(ValidationError):
        DraftAnalysis.model_validate(payload)


def test_draft_analysis_validation_fails_for_confidence_out_of_range() -> None:
    payload = _valid_payload()
    payload["confidence_score"] = 1.5
    with pytest.raises(ValidationError):
        DraftAnalysis.model_validate(payload)


def test_draft_analysis_from_payload_handles_legacy_shape() -> None:
    legacy = {
        "core_message": "Legacy core",
        "key_takeaways": [
            "Legacy takeaway 1",
            "Legacy takeaway 2",
            "Legacy takeaway 3",
        ],
        "target_audience": "Legacy audience",
        "tone_of_voice": "Legacy tone",
    }
    model = DraftAnalysis.from_payload(legacy)
    assert model.core_message == "Legacy core"
    assert model.value_proposition
    assert len(model.supporting_claims) >= 3
