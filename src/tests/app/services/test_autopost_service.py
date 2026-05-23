from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

from app.services.autopost_service import AutopostService
from app.services.chat_policy_service import (
    ChatPolicyService,
    PolicyCheckResult,
    PolicyDecision,
    PolicySeverity,
)
from infra.database.pg.schemas import AutopostJob, ConversationRun


def _service_without_runtime_init() -> AutopostService:
    return AutopostService.model_construct()


def test_derive_next_action_mapping() -> None:
    assert AutopostService._derive_next_action("FAILED") == "RETRY"
    assert AutopostService._derive_next_action("NEEDS_RECONNECT") == "RECONNECT"
    assert AutopostService._derive_next_action("NEEDS_REVIEW") == "REVIEW"
    assert AutopostService._derive_next_action("READY") == "PUBLISH"
    assert AutopostService._derive_next_action("PUBLISHED") is None


def test_looks_like_timeout_error_detects_timeout() -> None:
    assert AutopostService._looks_like_timeout_error(
        "SOCIAL_TIMEOUT", "provider timeout"
    )
    assert AutopostService._looks_like_timeout_error(None, "request timed out")
    assert not AutopostService._looks_like_timeout_error(
        "SOCIAL_PROVIDER_ERROR", "invalid token"
    )


def test_evaluate_quality_flags_missing_cta_and_short_content() -> None:
    service = _service_without_runtime_init()
    score, flags = service._evaluate_quality(
        content="Bài ngắn quá.",
        platform="facebook",
        expected_language="vi",
    )
    assert score < 1.0
    assert "too_short" in flags
    assert "missing_cta" in flags


def test_evaluate_quality_flags_risky_claim() -> None:
    service = _service_without_runtime_init()
    score, flags = service._evaluate_quality(
        content=(
            "Đảm bảo 100% hiệu quả nếu bạn click ngay bây giờ để đăng ký nhận tư vấn."
        ),
        platform="linkedin",
        expected_language="vi",
    )
    assert score < 1.0
    assert "risky_claim" in flags


def test_build_job_idempotency_key_returns_non_empty_key() -> None:
    job = AutopostJob(
        id="job-1",
        project_id="project-1",
        user_id="user-1",
        platform="linkedin",
        keyword="growth strategy",
        timezone="UTC",
        scheduled_at=datetime(2026, 5, 1, 8, 0, tzinfo=timezone.utc),
        status="READY",
        retry_count=0,
    )
    key = AutopostService._build_job_idempotency_key(job)
    assert key
    assert len(key) == 64


def test_publish_ready_job_moves_to_needs_review_when_policy_blocks() -> None:
    service = _service_without_runtime_init()
    job = AutopostJob(
        id="job-1",
        project_id="project-1",
        user_id="user-1",
        platform="linkedin",
        keyword="growth strategy",
        timezone="UTC",
        scheduled_at=datetime(2026, 5, 1, 8, 0, tzinfo=timezone.utc),
        status="READY",
        retry_count=0,
        quality_flags=[],
    )
    object.__setattr__(service, "_policy_service", ChatPolicyService())
    with (
        patch(
            "app.services.autopost_service.Settings",
            return_value=type(
                "S",
                (),
                {"crew": type("C", (), {"enable_policy_gate": True})()},
            )(),
        ),
        patch.object(
            service,
            "_set_job_status",
            return_value=job.model_copy(update={"status": "NEEDS_REVIEW"}),
        ) as set_status,
        patch.object(
            service._policy_service,
            "evaluate_generated_text",
            return_value=PolicyCheckResult(
                decision=PolicyDecision.HARD_BLOCK,
                reason="Unsafe content",
                severity=PolicySeverity.HIGH,
                suggested_reply="Blocked",
            ),
        ),
    ):
        result = service._publish_ready_job(
            session=object(),
            job=job,
            final_text="unsafe content",
        )

    assert result.status is True
    assert getattr(result.data, "status", "") == "NEEDS_REVIEW"
    assert set_status.call_count == 1


def _build_snapshot_payload(*, platform: str) -> dict:
    return {
        "source_url": "https://example.com",
        "analysis": {},
        "social_posts": [
            {
                "platform": platform,
                "hook": "Hook",
                "body_content": "Body content with enough context and contact now for support.",
                "call_to_action": "Contact us today",
                "hashtags": ["tag1", "tag2", "tag3"],
            }
        ],
    }


def test_extract_snapshot_from_response_payload_reads_content_plan_snapshot() -> None:
    service = _service_without_runtime_init()
    payload = {"content_plan_snapshot": _build_snapshot_payload(platform="linkedin")}
    snapshot = service._extract_snapshot_from_response_payload(payload)
    assert snapshot is not None
    assert snapshot.source_url == "https://example.com"
    assert snapshot.social_posts[0].platform.value == "linkedin"


def test_extract_snapshot_from_response_payload_normalizes_platform_alias() -> None:
    service = _service_without_runtime_init()
    payload = {
        "content_plan_snapshot": _build_snapshot_payload(platform="FACEBOOK Post")
    }
    snapshot = service._extract_snapshot_from_response_payload(payload)
    assert snapshot is not None
    assert snapshot.social_posts[0].platform.value == "facebook"


def test_extract_snapshot_from_response_payload_accepts_analysis_without_social_posts() -> None:
    service = _service_without_runtime_init()
    payload = {
        "content_plan_snapshot": {
            "source_url": "https://example.com",
            "analysis": {},
            "social_posts": [],
        }
    }
    snapshot = service._extract_snapshot_from_response_payload(payload)
    assert snapshot is not None
    assert snapshot.source_url == "https://example.com"
    assert snapshot.social_posts == []


def test_pick_snapshot_from_runs_prefers_non_autopost_publish_trigger() -> None:
    service = _service_without_runtime_init()
    now = datetime(2026, 5, 1, 8, 0, tzinfo=timezone.utc)
    publish_run = ConversationRun(
        id="run-publish",
        conversation_id="conv-1",
        project_id="project-1",
        request_payload={"trigger": "autopost_publish"},
        response_payload={
            "content_plan_snapshot": _build_snapshot_payload(platform="linkedin")
        },
        started_at=now,
        finished_at=now,
        status="completed",
    )
    content_run = ConversationRun(
        id="run-content",
        conversation_id="conv-1",
        project_id="project-1",
        request_payload={"trigger": "content_plan"},
        response_payload={
            "content_plan_snapshot": _build_snapshot_payload(platform="linkedin")
        },
        started_at=now,
        finished_at=now,
        status="completed",
    )

    snapshot, run = service._pick_snapshot_from_runs(
        runs=[publish_run, content_run],
        platform="linkedin",
    )
    assert snapshot is not None
    assert run is not None
    assert run.id == "run-content"


def test_pick_snapshot_from_runs_falls_back_to_analysis_when_platform_missing() -> None:
    service = _service_without_runtime_init()
    now = datetime(2026, 5, 1, 8, 0, tzinfo=timezone.utc)
    run = ConversationRun(
        id="run-linkedin-only",
        conversation_id="conv-1",
        project_id="project-1",
        request_payload={"trigger": "content_plan"},
        response_payload={
            "content_plan_snapshot": _build_snapshot_payload(platform="linkedin")
        },
        started_at=now,
        finished_at=now,
        status="completed",
    )

    snapshot, matched_run = service._pick_snapshot_from_runs(
        runs=[run],
        platform="facebook",
    )
    assert snapshot is not None
    assert matched_run is not None
    assert matched_run.id == "run-linkedin-only"
