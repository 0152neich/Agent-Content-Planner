from __future__ import annotations

from hashlib import sha256
from uuid import uuid4
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from app.services.chat_contracts import ChatAction
from app.workflows.chat_action_workflow import (
    ChatActionWorkflowInput,
    ChatActionWorkflowService,
)
from app.workflows.chat_snapshot import ContentPlanSnapshot, apply_partial_update
from domain.models.models import SocialPost
from infra.database.pg import SQLDatabase
from infra.database.pg.schemas import (
    AutopostJob,
    Conversation,
    ConversationRun,
    Project,
    User,
)
from shared.base import BaseModel
from shared.logging import get_logger, redact_message
from shared.language_policy import LanguagePolicyService
from shared.settings import Settings
from shared.settings.models import PostgresSettings

from .social_publish_service import SocialPublishInput, SocialPublishService
from .chat_policy_service import ChatPolicyService, PolicyDecision
from .linkedin_connection_service import LinkedInConnectionService
from .facebook_connection_service import FacebookConnectionService

logger = get_logger(__name__)


JOB_STATUS = {
    "QUEUED",
    "GENERATING",
    "READY",
    "NEEDS_REVIEW",
    "SCHEDULED",
    "PUBLISHING",
    "PUBLISHED",
    "PUBLISH_UNKNOWN",
    "FAILED",
    "NEEDS_RECONNECT",
    "CANCELLED",
}

TERMINAL_JOB_STATUS = {"PUBLISHED", "CANCELLED"}
RETRYABLE_JOB_STATUS = {"FAILED", "NEEDS_RECONNECT", "PUBLISH_UNKNOWN"}
RISKY_CONTENT_MARKERS = {
    "100%",
    "cam kết",
    "đảm bảo",
    "guarantee",
    "kỳ diệu",
    "miracle",
}
CTA_MARKERS = {
    "liên hệ",
    "inbox",
    "đăng ký",
    "tìm hiểu",
    "comment",
    "tham gia",
    "learn more",
    "book",
    "click",
    "join",
    "contact",
}


class AutopostServiceOutput(BaseModel):
    status: bool
    data: Any | None = None
    error: str | None = None
    code: int = 200


class CreateAutopostJobInput(BaseModel):
    user_id: str
    project_id: str
    platform: str
    keyword: str | None = None
    scheduled_at: datetime
    publish_mode: str = "schedule"
    page_id: str | None = None
    source_mode: str = "keyword"
    content: str | None = None


class ListAutopostJobsInput(BaseModel):
    user_id: str
    project_id: str
    status: str | None = None
    limit: int = 50


class GetAutopostJobInput(BaseModel):
    user_id: str
    job_id: str


class CancelAutopostJobInput(BaseModel):
    user_id: str
    job_id: str


class RetryAutopostJobInput(BaseModel):
    user_id: str
    job_id: str


class ApproveAutopostJobInput(BaseModel):
    user_id: str
    job_id: str


class UpdateAutopostContentInput(BaseModel):
    user_id: str
    job_id: str
    content: str


class ReconcileAutopostJobInput(BaseModel):
    job_id: str


class ListAutopostCalendarInput(BaseModel):
    user_id: str
    project_id: str
    status: str | None = None
    limit: int = 200


class ProcessAutopostJobInput(BaseModel):
    job_id: str


class AutopostService(BaseModel):
    def __init__(self, **data: Any) -> None:
        super().__init__(**data)
        self._db = SQLDatabase(config=PostgresSettings())
        self._social_publish_service = SocialPublishService()
        self._policy_service = ChatPolicyService()
        self._linkedin_connection_service = LinkedInConnectionService()
        self._facebook_connection_service = FacebookConnectionService()
        self._chat_action_workflow_service = ChatActionWorkflowService()

    @staticmethod
    def _utc_now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _normalize_platform(value: str | None) -> str:
        return (value or "").strip().lower()

    @staticmethod
    def _normalize_source_mode(value: str | None) -> str:
        return (value or "").strip().lower() or "keyword"

    def _resolve_user_timezone(self, user: User) -> str:
        timezone_value = (user.timezone or "").strip()
        if not timezone_value:
            return "UTC"
        try:
            ZoneInfo(timezone_value)
            return timezone_value
        except Exception:
            return "UTC"

    @staticmethod
    def _ensure_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @staticmethod
    def _looks_like_timeout_error(error_code: str | None, error_message: str | None) -> bool:
        if isinstance(error_code, str) and error_code.strip().upper() in {
            "SOCIAL_TIMEOUT",
            "SOCIAL_NETWORK_TIMEOUT",
        }:
            return True
        message = (error_message or "").strip().lower()
        return "timeout" in message or "timed out" in message

    def _get_project_owned(
        self, *, user_id: str, project_id: str, session
    ) -> tuple[Project | None, User | None]:
        project = self._db.get_project_by_id(session=session, id=project_id)
        if project is None or project.owner_user_id != user_id:
            return None, None
        user = self._db.get_user_by_id(session=session, id=user_id)
        if user is None:
            return None, None
        return project, user

    def _get_job_owned(
        self, *, user_id: str, job_id: str, session
    ) -> AutopostJob | None:
        job = self._db.get_autopost_job_by_id(session=session, id=job_id)
        if job is None or job.user_id != user_id:
            return None
        return job

    def _build_platform_connect_url(
        self,
        *,
        user: User,
        platform: str,
    ) -> str | None:
        try:
            if platform == "linkedin":
                result = self._linkedin_connection_service.build_connect_url(
                    user, return_to="/autopost"
                )
            else:
                result = self._facebook_connection_service.build_connect_url(
                    user, return_to="/autopost"
                )
            if not result.status or not isinstance(result.data, dict):
                return None
            connect_url = str(result.data.get("authorize_url") or "").strip()
            return connect_url or None
        except Exception:
            return None

    def _ensure_platform_connected(
        self,
        *,
        session,
        user: User,
        platform: str,
    ) -> AutopostServiceOutput | None:
        provider_name = "LinkedIn" if platform == "linkedin" else "Facebook"
        rows = self._db.get_social_connections(
            session=session,
            filter={"user_id": str(user.id or ""), "provider": platform},
            limit=1,
        )
        connection = rows[0] if rows else None
        connect_url = self._build_platform_connect_url(user=user, platform=platform)
        if connection is None or connection.revoked_at is not None:
            return AutopostServiceOutput(
                status=False,
                error=f"Tài khoản {provider_name} chưa kết nối. Vui lòng kết nối để tiếp tục.",
                data={
                    "connect_required": True,
                    "platform": platform,
                    "reason": "SOCIAL_NOT_CONNECTED",
                    "connect_url": connect_url,
                },
                code=400,
            )
        if not str(connection.access_token_encrypted or "").strip():
            return AutopostServiceOutput(
                status=False,
                error=f"Tài khoản {provider_name} chưa kết nối. Vui lòng kết nối để tiếp tục.",
                data={
                    "connect_required": True,
                    "platform": platform,
                    "reason": "SOCIAL_NOT_CONNECTED",
                    "connect_url": connect_url,
                },
                code=400,
            )
        expires_at = connection.token_expires_at
        if expires_at is not None:
            expires_at_utc = (
                expires_at.replace(tzinfo=timezone.utc)
                if expires_at.tzinfo is None
                else expires_at.astimezone(timezone.utc)
            )
            if expires_at_utc <= self._utc_now():
                return AutopostServiceOutput(
                    status=False,
                    error=f"Phiên kết nối {provider_name} đã hết hạn. Vui lòng kết nối lại.",
                    data={
                        "connect_required": True,
                        "platform": platform,
                        "reason": "SOCIAL_TOKEN_EXPIRED",
                        "connect_url": connect_url,
                    },
                    code=401,
                )
        return None

    @staticmethod
    def _derive_next_action(status: str) -> str | None:
        normalized = status.strip().upper()
        if normalized == "NEEDS_RECONNECT":
            return "RECONNECT"
        if normalized in {"FAILED", "PUBLISH_UNKNOWN"}:
            return "RETRY"
        if normalized == "NEEDS_REVIEW":
            return "REVIEW"
        if normalized in {"QUEUED", "GENERATING", "READY", "SCHEDULED"}:
            return "PUBLISH"
        return None

    @staticmethod
    def _normalize_content(text: str | None) -> str:
        if not isinstance(text, str):
            return ""
        return " ".join(text.strip().split())

    @classmethod
    def _build_manual_content_keyword(cls, *, platform: str, content: str) -> str:
        normalized = cls._normalize_content(content)
        if not normalized:
            return f"Manual content ({platform})"
        digest = sha256(normalized.encode("utf-8")).hexdigest()[:10]
        snippet = normalized[:72].strip()
        return f"Manual content ({platform}) [{digest}] {snippet}"

    @staticmethod
    def _build_job_idempotency_key(job: AutopostJob) -> str:
        payload = "|".join(
            [
                str(job.id or ""),
                job.platform,
                job.project_id,
                job.user_id,
                str(job.retry_count),
                str(job.scheduled_at.isoformat()),
                str(uuid4()),
            ]
        )
        return sha256(payload.encode("utf-8")).hexdigest()[:64]

    def _evaluate_quality(
        self,
        *,
        content: str,
        platform: str,
        expected_language: str | None = None,
    ) -> tuple[float, list[str]]:
        normalized = self._normalize_content(content)
        flags: list[str] = []
        if not normalized:
            return 0.0, ["empty_content"]

        length = len(normalized)
        max_len = 3000 if platform == "linkedin" else 2000
        min_len = 60 if platform == "linkedin" else 40
        if length < min_len:
            flags.append("too_short")
        if length > max_len:
            flags.append("too_long")

        lowered = normalized.lower()
        if not any(marker in lowered for marker in CTA_MARKERS):
            flags.append("missing_cta")
        if any(marker in lowered for marker in RISKY_CONTENT_MARKERS):
            flags.append("risky_claim")

        if expected_language in {"vi", "en"}:
            detected = LanguagePolicyService().detect_target_language(normalized)
            if detected != expected_language:
                flags.append("language_mismatch")

        score = max(0.0, 1.0 - (0.2 * len(flags)))
        return score, flags

    def _upsert_single_project_conversation(
        self, *, project_id: str, session
    ) -> Conversation:
        conversations = (
            self._db.get_conversations(
                session=session, filter={"project_id": project_id}
            )
            or []
        )
        if conversations:
            return conversations[0]
        now = self._utc_now()
        conversation = Conversation(
            project_id=project_id,
            title="Auto-Post",
            selected_model="gpt-5.4",
            status="active",
            message_count=0,
            last_message_at=now,
        )
        return self._db.insert_conversation(session=session, model=conversation)

    def _create_run(
        self,
        *,
        session,
        project_id: str,
        conversation_id: str,
        status: str,
        request_payload: dict[str, Any],
        response_payload: dict[str, Any],
        source_url: str | None,
        platforms: list[str],
    ) -> ConversationRun:
        now = self._utc_now()
        return self._db.insert_conversation_run(
            session=session,
            model=ConversationRun(
                conversation_id=conversation_id,
                project_id=project_id,
                request_payload=request_payload,
                response_payload=response_payload,
                status=status,
                started_at=now,
                finished_at=now,
                source_url=source_url,
                platforms=platforms,
            ),
        )

    @staticmethod
    def _normalize_snapshot_platform(value: Any) -> str | None:
        raw = str(value or "").strip().lower()
        if raw in {"linkedin", "facebook"}:
            return raw
        if "linkedin" in raw:
            return "linkedin"
        if "facebook" in raw:
            return "facebook"
        return None

    @classmethod
    def _coerce_snapshot_payload(
        cls,
        payload: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        if not isinstance(payload, dict):
            return None
        analysis_raw = payload.get("analysis")
        posts_raw = payload.get("social_posts")
        if not isinstance(analysis_raw, dict) or not isinstance(posts_raw, list):
            return None

        normalized_posts: list[dict[str, Any]] = []
        for raw_post in posts_raw:
            if not isinstance(raw_post, dict):
                continue
            normalized_platform = cls._normalize_snapshot_platform(raw_post.get("platform"))
            if not normalized_platform:
                continue
            hashtags_raw = raw_post.get("hashtags")
            hashtags: list[str] = []
            if isinstance(hashtags_raw, list):
                hashtags = [str(item).strip() for item in hashtags_raw if str(item).strip()]
            normalized_posts.append(
                {
                    "platform": normalized_platform,
                    "hook": str(raw_post.get("hook") or "").strip(),
                    "body_content": str(raw_post.get("body_content") or "").strip(),
                    "call_to_action": str(raw_post.get("call_to_action") or "").strip(),
                    "hashtags": hashtags,
                }
            )

        return {
            "source_url": str(payload.get("source_url") or "").strip(),
            "analysis": analysis_raw,
            "social_posts": normalized_posts,
            "meta": payload.get("meta") if isinstance(payload.get("meta"), dict) else {},
        }

    @classmethod
    def _extract_snapshot_from_response_payload(
        cls,
        payload: dict[str, Any] | None,
    ) -> ContentPlanSnapshot | None:
        if not isinstance(payload, dict):
            return None

        candidates: list[dict[str, Any]] = []
        raw_snapshot = payload.get("content_plan_snapshot")
        if isinstance(raw_snapshot, dict):
            candidates.append(raw_snapshot)
        candidates.append(payload)

        for candidate in candidates:
            coerced = cls._coerce_snapshot_payload(candidate)
            if coerced is None:
                continue
            try:
                return ContentPlanSnapshot.from_payload(coerced)
            except Exception:
                continue
        return None

    def _extract_snapshot_from_run(
        self,
        run: ConversationRun,
    ) -> ContentPlanSnapshot | None:
        payload = run.response_payload if isinstance(run.response_payload, dict) else {}
        return self._extract_snapshot_from_response_payload(payload)

    @staticmethod
    def _find_snapshot_post(
        snapshot: ContentPlanSnapshot,
        platform: str,
    ) -> SocialPost | None:
        normalized = platform.strip().lower()
        for post in snapshot.social_posts:
            if post.platform.value.strip().lower() == normalized:
                return post
        return None

    def _pick_snapshot_from_runs(
        self,
        *,
        runs: list[ConversationRun],
        platform: str,
    ) -> tuple[ContentPlanSnapshot | None, ConversationRun | None]:
        non_publish_platform_snapshot: ContentPlanSnapshot | None = None
        non_publish_platform_run: ConversationRun | None = None
        non_publish_any_snapshot: ContentPlanSnapshot | None = None
        non_publish_any_run: ConversationRun | None = None
        publish_platform_snapshot: ContentPlanSnapshot | None = None
        publish_platform_run: ConversationRun | None = None
        publish_any_snapshot: ContentPlanSnapshot | None = None
        publish_any_run: ConversationRun | None = None

        for run in runs:
            snapshot = self._extract_snapshot_from_run(run)
            if snapshot is None:
                continue
            trigger = str((run.request_payload or {}).get("trigger") or "").strip().lower()
            is_autopost_publish = trigger == "autopost_publish"
            has_platform_post = self._find_snapshot_post(snapshot, platform) is not None

            if not is_autopost_publish and has_platform_post:
                non_publish_platform_snapshot = snapshot
                non_publish_platform_run = run
                break

            if not is_autopost_publish and non_publish_any_snapshot is None:
                non_publish_any_snapshot = snapshot
                non_publish_any_run = run

            if is_autopost_publish and has_platform_post and publish_platform_snapshot is None:
                publish_platform_snapshot = snapshot
                publish_platform_run = run

            if is_autopost_publish and publish_any_snapshot is None:
                publish_any_snapshot = snapshot
                publish_any_run = run

        if non_publish_platform_snapshot is not None:
            return non_publish_platform_snapshot, non_publish_platform_run
        if non_publish_any_snapshot is not None:
            return non_publish_any_snapshot, non_publish_any_run
        if publish_platform_snapshot is not None:
            return publish_platform_snapshot, publish_platform_run
        if publish_any_snapshot is not None:
            return publish_any_snapshot, publish_any_run

        return None, None

    def _resolve_latest_snapshot_for_platform(
        self,
        *,
        session,
        project_id: str,
        platform: str,
    ) -> tuple[ContentPlanSnapshot | None, ConversationRun | None]:
        runs = (
            self._db.list_project_runs_by_cursor(
                session=session,
                project_id=project_id,
                status=None,
                cursor_created_at=None,
                cursor_id=None,
                limit=200,
            )
            or []
        )
        return self._pick_snapshot_from_runs(runs=runs, platform=platform)

    def _publish_ready_job(
        self,
        *,
        session,
        job: AutopostJob,
        final_text: str,
    ) -> AutopostServiceOutput:
        normalized_text = self._normalize_content(final_text)
        if not normalized_text:
            failed = self._set_job_status(
                session=session,
                job=job,
                status="FAILED",
                error_code="EMPTY_CONTENT",
                error_message="Final content is empty.",
                expected_statuses=[job.status],
            )
            return AutopostServiceOutput(
                status=False,
                data=failed,
                error="Final content is empty.",
                code=409,
            )

        if bool(getattr(Settings().crew, "enable_policy_gate", True)):
            policy_result = self._policy_service.evaluate_generated_text(normalized_text)
            if policy_result.decision == PolicyDecision.HARD_BLOCK:
                updated = self._set_job_status(
                    session=session,
                    job=job,
                    status="NEEDS_REVIEW",
                    error_code="POLICY_GATE_BLOCKED",
                    error_message=policy_result.reason,
                    quality_flags=list((job.quality_flags or []))
                    + ["policy_violation"],
                    expected_statuses=[job.status],
                )
                return AutopostServiceOutput(
                    status=True,
                    data=updated or job,
                    error=policy_result.suggested_reply
                    or "Content requires manual review due to policy safety checks.",
                    code=200,
                )

        now = self._utc_now()
        if job.platform == "linkedin" and job.scheduled_at > now:
            scheduled = self._set_job_status(
                session=session,
                job=job,
                status="SCHEDULED",
                error_code=None,
                error_message=None,
                expected_statuses=["READY", "SCHEDULED"],
            )
            if scheduled is None:
                return AutopostServiceOutput(
                    status=False,
                    error="Job status changed while scheduling.",
                    code=409,
                )
            return AutopostServiceOutput(status=True, data=scheduled, code=200)

        publishing_job = self._set_job_status(
            session=session,
            job=job,
            status="PUBLISHING",
            final_content=normalized_text,
            idempotency_key=job.idempotency_key or self._build_job_idempotency_key(job),
            error_code=None,
            error_message=None,
            expected_statuses=["READY", "SCHEDULED", "PUBLISH_UNKNOWN"],
        )
        if publishing_job is None:
            return AutopostServiceOutput(
                status=False,
                error="Job is being processed by another worker.",
                code=409,
            )

        publish_result = None
        if publishing_job.platform == "facebook":
            if publishing_job.scheduled_at <= now:
                publish_result = self._social_publish_service.publish(
                    SocialPublishInput(
                        user_id=publishing_job.user_id,
                        platform="facebook",
                        content=normalized_text,
                        page_id=(publishing_job.page_id or "").strip(),
                        idempotency_key=publishing_job.idempotency_key,
                    )
                )
                success_status = "PUBLISHED"
            else:
                publish_result = self._social_publish_service.schedule_facebook(
                    user_id=publishing_job.user_id,
                    content=normalized_text,
                    page_id=(publishing_job.page_id or "").strip(),
                    scheduled_at=publishing_job.scheduled_at,
                    idempotency_key=publishing_job.idempotency_key,
                )
                success_status = "SCHEDULED"
        else:
            publish_result = self._social_publish_service.publish(
                SocialPublishInput(
                    user_id=publishing_job.user_id,
                    platform="linkedin",
                    content=normalized_text,
                    idempotency_key=publishing_job.idempotency_key,
                )
            )
            success_status = "PUBLISHED"

        if not publish_result.status:
            if publish_result.error_code == "SOCIAL_TOKEN_EXPIRED":
                failed_status = "NEEDS_RECONNECT"
            elif self._looks_like_timeout_error(
                publish_result.error_code,
                publish_result.error,
            ):
                failed_status = "PUBLISH_UNKNOWN"
            else:
                failed_status = "FAILED"
            failed = self._set_job_status(
                session=session,
                job=publishing_job,
                status=failed_status,
                error_code=publish_result.error_code,
                error_message=publish_result.error,
                expected_statuses=["PUBLISHING"],
            )
            return AutopostServiceOutput(
                status=False,
                data=failed,
                error=publish_result.error,
                code=publish_result.code,
            )

        payload = publish_result.data if isinstance(publish_result.data, dict) else {}
        updated = self._set_job_status(
            session=session,
            job=publishing_job,
            status=success_status,
            provider_post_id=str(payload.get("provider_post_id") or "").strip() or None,
            provider_schedule_id=str(payload.get("provider_schedule_id") or "").strip()
            or None,
            error_code=None,
            error_message=None,
            expected_statuses=["PUBLISHING"],
        )
        if updated is None:
            return AutopostServiceOutput(
                status=False,
                error="Job status changed after publish.",
                code=409,
            )

        if updated.status == "PUBLISHED":
            conversation = self._upsert_single_project_conversation(
                project_id=updated.project_id, session=session
            )
            run = self._create_run(
                session=session,
                project_id=updated.project_id,
                conversation_id=conversation.id or "",
                status="completed",
                request_payload={
                    "trigger": "autopost_publish",
                    "job_id": updated.id,
                    "platform": updated.platform,
                    "idempotency_key": updated.idempotency_key,
                },
                response_payload=payload,
                source_url=None,
                platforms=[updated.platform],
            )
            updated = self._set_job_status(
                session=session,
                job=updated,
                status=updated.status,
                conversation_run_id=run.id,
                expected_statuses=[updated.status],
            ) or updated

        return AutopostServiceOutput(status=True, data=updated, code=200)

    def _find_duplicate_job(
        self,
        *,
        session,
        user_id: str,
        project_id: str,
        platform: str,
        keyword: str,
        scheduled_at: datetime,
    ) -> AutopostJob | None:
        if not Settings().autopost.enable_duplicate_guard:
            return None
        window = timedelta(minutes=Settings().autopost.duplicate_window_minutes)
        jobs = (
            self._db.list_autopost_jobs(
                session=session,
                project_id=project_id,
                user_id=user_id,
                status=None,
                limit=200,
            )
            or []
        )
        for item in jobs:
            if item.platform != platform:
                continue
            if self._normalize_content(item.keyword) != self._normalize_content(keyword):
                continue
            if item.status in {"CANCELLED", "FAILED", "PUBLISHED"}:
                continue
            if abs((item.scheduled_at - scheduled_at).total_seconds()) <= window.total_seconds():
                return item
        return None

    def create_job(self, inputs: CreateAutopostJobInput) -> AutopostServiceOutput:
        try:
            platform = self._normalize_platform(inputs.platform)
            if platform not in {"linkedin", "facebook"}:
                return AutopostServiceOutput(
                    status=False,
                    error="Unsupported platform. Allowed: linkedin, facebook.",
                    code=400,
                )
            source_mode = self._normalize_source_mode(inputs.source_mode)
            if source_mode not in {"keyword", "content"}:
                return AutopostServiceOutput(
                    status=False,
                    error="Unsupported source mode. Allowed: keyword, content.",
                    code=400,
                )
            keyword = (inputs.keyword or "").strip()
            manual_content = (inputs.content or "").strip()
            if source_mode == "keyword" and not keyword:
                return AutopostServiceOutput(
                    status=False,
                    error="Keyword must not be blank when source_mode=keyword.",
                    code=400,
                )
            if source_mode == "content" and not manual_content:
                return AutopostServiceOutput(
                    status=False,
                    error="Content must not be blank when source_mode=content.",
                    code=400,
                )
            if source_mode == "content" and not keyword:
                keyword = self._build_manual_content_keyword(
                    platform=platform, content=manual_content
                )
            scheduled_at = self._ensure_utc(inputs.scheduled_at)
            now = self._utc_now()
            publish_mode = (inputs.publish_mode or "").strip().lower() or "schedule"
            if publish_mode not in {"now", "schedule"}:
                return AutopostServiceOutput(
                    status=False,
                    error="Unsupported publish mode. Allowed: now, schedule.",
                    code=400,
                )
            if publish_mode == "now":
                scheduled_at = now
            elif scheduled_at < now + timedelta(minutes=30):
                return AutopostServiceOutput(
                    status=False,
                    error="Scheduled time must be at least 30 minutes from now.",
                    code=400,
                )

            if platform == "facebook":
                max_time = now + timedelta(days=75)
                if publish_mode == "schedule" and scheduled_at > max_time:
                    return AutopostServiceOutput(
                        status=False,
                        error=(
                            "Facebook scheduled time must be between 30 minutes and "
                            "75 days from now."
                        ),
                        code=400,
                    )
                if not (inputs.page_id or "").strip():
                    return AutopostServiceOutput(
                        status=False,
                        error="page_id is required for facebook scheduling.",
                        code=400,
                    )

            with self._db.get_session() as session:
                project, user = self._get_project_owned(
                    user_id=inputs.user_id,
                    project_id=inputs.project_id,
                    session=session,
                )
                if project is None or user is None:
                    return AutopostServiceOutput(
                        status=False,
                        error="Project not found.",
                        code=404,
                    )
                if publish_mode in {"now", "schedule"}:
                    connection_error = self._ensure_platform_connected(
                        session=session,
                        user=user,
                        platform=platform,
                    )
                    if connection_error is not None:
                        return connection_error
                duplicate_job = self._find_duplicate_job(
                    session=session,
                    user_id=inputs.user_id,
                    project_id=project.id or "",
                    platform=platform,
                    keyword=keyword,
                    scheduled_at=scheduled_at,
                )
                if duplicate_job is not None:
                    return AutopostServiceOutput(
                        status=False,
                        data={"id": duplicate_job.id, "status": duplicate_job.status},
                        error="A similar auto-post job already exists in the active window.",
                        code=409,
                    )
                user_timezone = self._resolve_user_timezone(user)
                job = self._db.insert_autopost_job(
                    session=session,
                    model=AutopostJob(
                        project_id=project.id or "",
                        user_id=inputs.user_id,
                        platform=platform,
                        keyword=keyword,
                        timezone=user_timezone,
                        scheduled_at=scheduled_at,
                        status="QUEUED",
                        page_id=(inputs.page_id or "").strip() or None,
                        draft_content=manual_content or None,
                        final_content=manual_content or None,
                        retry_count=0,
                        quality_score=None,
                        quality_flags=[],
                        next_action="PUBLISH",
                        job_version=0,
                        idempotency_key=None,
                    ),
                )

            try:
                from app.autopost_tasks import process_autopost_job

                process_autopost_job.delay(str(job.id))
            except Exception as exc:
                logger.exception(
                    "autopost_enqueue_failed",
                    job_id=job.id,
                    error=redact_message(str(exc)),
                )
                with self._db.get_session() as session:
                    failed = self._db.get_autopost_job_by_id(
                        session=session, id=job.id or ""
                    )
                    if failed is not None:
                        self._db.update_autopost_job(
                            session=session,
                            model=AutopostJob(
                                id=failed.id,
                                project_id=failed.project_id,
                                user_id=failed.user_id,
                                platform=failed.platform,
                                keyword=failed.keyword,
                                timezone=failed.timezone,
                                scheduled_at=failed.scheduled_at,
                                status="FAILED",
                                page_id=failed.page_id,
                                draft_content=failed.draft_content,
                                final_content=failed.final_content,
                                provider_post_id=failed.provider_post_id,
                                provider_schedule_id=failed.provider_schedule_id,
                                error_code="QUEUE_ENQUEUE_FAILED",
                                error_message="Could not enqueue background job.",
                                retry_count=failed.retry_count,
                                conversation_run_id=failed.conversation_run_id,
                                quality_score=failed.quality_score,
                                quality_flags=failed.quality_flags,
                                next_action="RETRY",
                                job_version=failed.job_version,
                                idempotency_key=failed.idempotency_key,
                            ),
                        )
                return AutopostServiceOutput(
                    status=False,
                    error="Could not enqueue background job.",
                    code=500,
                )

            return AutopostServiceOutput(
                status=True,
                data={"id": str(job.id), "status": "QUEUED"},
                code=202,
            )
        except Exception as exc:
            logger.exception(
                "autopost_create_job_failed", error=redact_message(str(exc))
            )
            return AutopostServiceOutput(
                status=False,
                error=f"Unexpected error while creating job: {redact_message(str(exc))}",
                code=500,
            )

    def list_jobs(self, inputs: ListAutopostJobsInput) -> AutopostServiceOutput:
        try:
            status_filter = (inputs.status or "").strip().upper() or None
            if status_filter and status_filter not in JOB_STATUS:
                return AutopostServiceOutput(
                    status=False, error="Unsupported status filter.", code=400
                )
            with self._db.get_session() as session:
                project, user = self._get_project_owned(
                    user_id=inputs.user_id,
                    project_id=inputs.project_id,
                    session=session,
                )
                if project is None or user is None:
                    return AutopostServiceOutput(
                        status=False, error="Project not found.", code=404
                    )
                jobs = self._db.list_autopost_jobs(
                    session=session,
                    project_id=inputs.project_id,
                    user_id=inputs.user_id,
                    status=status_filter,
                    limit=inputs.limit,
                )
            return AutopostServiceOutput(status=True, data=jobs, code=200)
        except Exception as exc:
            logger.exception(
                "autopost_list_jobs_failed", error=redact_message(str(exc))
            )
            return AutopostServiceOutput(
                status=False,
                error="Unexpected error while listing jobs.",
                code=500,
            )

    def get_job(self, inputs: GetAutopostJobInput) -> AutopostServiceOutput:
        try:
            with self._db.get_session() as session:
                job = self._get_job_owned(
                    user_id=inputs.user_id,
                    job_id=inputs.job_id,
                    session=session,
                )
                if job is None:
                    return AutopostServiceOutput(
                        status=False, error="Job not found.", code=404
                    )
                project = self._db.get_project_by_id(session=session, id=job.project_id)
                if project is None or project.owner_user_id != inputs.user_id:
                    return AutopostServiceOutput(
                        status=False, error="Job not found.", code=404
                    )
                return AutopostServiceOutput(status=True, data=job, code=200)
        except Exception as exc:
            logger.exception("autopost_get_job_failed", error=redact_message(str(exc)))
            return AutopostServiceOutput(
                status=False,
                error="Unexpected error while getting job.",
                code=500,
            )

    def cancel_job(self, inputs: CancelAutopostJobInput) -> AutopostServiceOutput:
        try:
            with self._db.get_session() as session:
                job = self._get_job_owned(
                    user_id=inputs.user_id,
                    job_id=inputs.job_id,
                    session=session,
                )
                if job is None:
                    return AutopostServiceOutput(
                        status=False, error="Job not found.", code=404
                    )
                if job.status in {"PUBLISHED", "CANCELLED", "PUBLISHING"}:
                    return AutopostServiceOutput(
                        status=False,
                        error=f"Cannot cancel job in status {job.status}.",
                        code=409,
                    )
                updated = self._set_job_status(
                    session=session,
                    job=job,
                    status="CANCELLED",
                    expected_statuses=[
                        "QUEUED",
                        "GENERATING",
                        "READY",
                        "SCHEDULED",
                        "FAILED",
                        "NEEDS_RECONNECT",
                        "PUBLISH_UNKNOWN",
                        "NEEDS_REVIEW",
                    ],
                )
                if updated is None:
                    return AutopostServiceOutput(
                        status=False, error="Job not found.", code=404
                    )
                return AutopostServiceOutput(
                    status=True,
                    data={"id": updated.id, "status": updated.status},
                    code=200,
                )
        except Exception as exc:
            logger.exception(
                "autopost_cancel_job_failed", error=redact_message(str(exc))
            )
            return AutopostServiceOutput(
                status=False,
                error="Unexpected error while cancelling job.",
                code=500,
            )

    def retry_job(self, inputs: RetryAutopostJobInput) -> AutopostServiceOutput:
        try:
            with self._db.get_session() as session:
                job = self._get_job_owned(
                    user_id=inputs.user_id,
                    job_id=inputs.job_id,
                    session=session,
                )
                if job is None:
                    return AutopostServiceOutput(
                        status=False, error="Job not found.", code=404
                    )
                if job.status not in RETRYABLE_JOB_STATUS:
                    return AutopostServiceOutput(
                        status=False,
                        error=(
                            "Retry is only allowed for FAILED, NEEDS_RECONNECT "
                            "or PUBLISH_UNKNOWN jobs."
                        ),
                        code=409,
                    )
                updated = self._set_job_status(
                    session=session,
                    job=job,
                    status="QUEUED",
                    error_code=None,
                    error_message=None,
                    idempotency_key=None,
                    retry_count=job.retry_count + 1,
                    expected_statuses=list(RETRYABLE_JOB_STATUS),
                )
                if updated is None:
                    return AutopostServiceOutput(
                        status=False, error="Job not found.", code=404
                    )

            from app.autopost_tasks import process_autopost_job

            process_autopost_job.delay(str(updated.id))
            return AutopostServiceOutput(
                status=True, data={"id": updated.id, "status": updated.status}, code=200
            )
        except Exception as exc:
            logger.exception(
                "autopost_retry_job_failed", error=redact_message(str(exc))
            )
            return AutopostServiceOutput(
                status=False,
                error="Unexpected error while retrying job.",
                code=500,
            )

    def list_calendar(self, inputs: ListAutopostCalendarInput) -> AutopostServiceOutput:
        return self.list_jobs(
            ListAutopostJobsInput(
                user_id=inputs.user_id,
                project_id=inputs.project_id,
                status=inputs.status,
                limit=inputs.limit,
            )
        )

    @staticmethod
    def _build_post_text(post: dict[str, Any]) -> str:
        sections: list[str] = []
        for key in ("hook", "body_content", "call_to_action"):
            value = post.get(key)
            if isinstance(value, str) and value.strip():
                sections.append(value.strip())
        hashtags = post.get("hashtags")
        if isinstance(hashtags, list):
            tag_text = " ".join(
                [f"#{str(tag).lstrip('#')}" for tag in hashtags if str(tag).strip()]
            ).strip()
            if tag_text:
                sections.append(tag_text)
        return "\n\n".join(sections).strip()

    def _set_job_status(
        self,
        *,
        session,
        job: AutopostJob,
        status: str,
        draft_content: str | None = None,
        final_content: str | None = None,
        provider_post_id: str | None = None,
        provider_schedule_id: str | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
        conversation_run_id: str | None = None,
        retry_count: int | None = None,
        quality_score: float | None = None,
        quality_flags: list[str] | None = None,
        next_action: str | None = None,
        idempotency_key: str | None = None,
        expected_statuses: list[str] | None = None,
    ) -> AutopostJob | None:
        updates: dict[str, object] = {
            "status": status,
            "draft_content": draft_content
            if draft_content is not None
            else job.draft_content,
            "final_content": final_content
            if final_content is not None
            else job.final_content,
            "provider_post_id": provider_post_id
            if provider_post_id is not None
            else job.provider_post_id,
            "provider_schedule_id": provider_schedule_id
            if provider_schedule_id is not None
            else job.provider_schedule_id,
            "error_code": error_code,
            "error_message": error_message,
            "conversation_run_id": conversation_run_id
            if conversation_run_id is not None
            else job.conversation_run_id,
            "retry_count": retry_count if retry_count is not None else job.retry_count,
            "quality_score": quality_score
            if quality_score is not None
            else job.quality_score,
            "quality_flags": quality_flags
            if quality_flags is not None
            else list(job.quality_flags or []),
            "next_action": (
                next_action
                if next_action is not None
                else self._derive_next_action(status)
            ),
            "idempotency_key": idempotency_key
            if idempotency_key is not None
            else job.idempotency_key,
        }
        return self._db.update_autopost_job_with_guard(
            session=session,
            job_id=job.id or "",
            expected_job_version=job.job_version,
            expected_statuses=expected_statuses,
            updates=updates,
        )

    def process_job(self, inputs: ProcessAutopostJobInput) -> AutopostServiceOutput:
        try:
            with self._db.get_session() as session:
                job = self._db.get_autopost_job_by_id(session=session, id=inputs.job_id)
                if job is None:
                    return AutopostServiceOutput(
                        status=False, error="Job not found.", code=404
                    )
                if job.status in {"CANCELLED", "PUBLISHED"}:
                    return AutopostServiceOutput(status=True, data=job, code=200)
                if job.status == "PUBLISHING":
                    return AutopostServiceOutput(
                        status=False,
                        data=job,
                        error="Job is currently being published.",
                        code=409,
                    )
                project = self._db.get_project_by_id(session=session, id=job.project_id)
                if project is None:
                    self._set_job_status(
                        session=session,
                        job=job,
                        status="FAILED",
                        error_code="PROJECT_NOT_FOUND",
                        error_message="Project not found.",
                    )
                    return AutopostServiceOutput(
                        status=False, error="Project not found.", code=404
                    )
                prepared_content = (job.final_content or job.draft_content or "").strip()
                if prepared_content:
                    expected_language = LanguagePolicyService().detect_target_language(
                        job.keyword
                    )
                    quality_score, quality_flags = self._evaluate_quality(
                        content=prepared_content,
                        platform=job.platform,
                        expected_language=expected_language,
                    )
                    run_conversation = self._upsert_single_project_conversation(
                        project_id=job.project_id, session=session
                    )
                    run = self._create_run(
                        session=session,
                        project_id=job.project_id,
                        conversation_id=run_conversation.id or "",
                        status="completed",
                        request_payload={
                            "trigger": "autopost_manual",
                            "job_id": job.id,
                            "platform": job.platform,
                            "keyword": job.keyword,
                            "scheduled_at": job.scheduled_at.isoformat(),
                        },
                        response_payload={"selected_post_text": prepared_content},
                        source_url=project.source_url,
                        platforms=[job.platform],
                    )
                    updated_job = self._set_job_status(
                        session=session,
                        job=job,
                        status="READY",
                        draft_content=prepared_content,
                        final_content=prepared_content,
                        quality_score=quality_score,
                        quality_flags=quality_flags,
                        conversation_run_id=run.id,
                        error_code=None,
                        error_message=None,
                        expected_statuses=[
                            "QUEUED",
                            "READY",
                            "PUBLISH_UNKNOWN",
                            "FAILED",
                            "NEEDS_RECONNECT",
                            "SCHEDULED",
                            "NEEDS_REVIEW",
                        ],
                    )
                    if updated_job is None:
                        return AutopostServiceOutput(
                            status=False, error="Job not found.", code=404
                        )
                    if (
                        Settings().autopost.enable_quality_gate
                        and Settings().autopost.require_review_on_quality_failure
                        and quality_score < Settings().autopost.quality_min_score
                    ):
                        review_job = self._set_job_status(
                            session=session,
                            job=updated_job,
                            status="NEEDS_REVIEW",
                            error_code="QUALITY_GATE_FAILED",
                            error_message=(
                                "Content requires manual review before publishing."
                            ),
                            expected_statuses=["READY"],
                        )
                        return AutopostServiceOutput(
                            status=True,
                            data=review_job or updated_job,
                            code=200,
                        )
                    return self._publish_ready_job(
                        session=session,
                        job=updated_job,
                        final_text=prepared_content,
                    )

                rewrite_prompt = (job.keyword or "").strip()
                if not rewrite_prompt:
                    self._set_job_status(
                        session=session,
                        job=job,
                        status="FAILED",
                        error_code="REWRITE_PROMPT_REQUIRED",
                        error_message="Rewrite prompt must not be blank.",
                    )
                    return AutopostServiceOutput(
                        status=False,
                        error="Rewrite prompt must not be blank.",
                        code=400,
                    )
                updated_job = self._set_job_status(
                    session=session,
                    job=job,
                    status="GENERATING",
                    error_code=None,
                    error_message=None,
                    expected_statuses=["QUEUED", "FAILED", "PUBLISH_UNKNOWN"],
                )
                if updated_job is not None:
                    job = updated_job

                snapshot, source_run = self._resolve_latest_snapshot_for_platform(
                    session=session,
                    project_id=job.project_id,
                    platform=job.platform,
                )
                snapshot_source = "history"

                if snapshot is None:
                    run_conversation = self._upsert_single_project_conversation(
                        project_id=job.project_id, session=session
                    )
                    run = self._create_run(
                        session=session,
                        project_id=job.project_id,
                        conversation_id=run_conversation.id or "",
                        status="failed",
                        request_payload={
                            "trigger": "autopost_rewrite",
                            "job_id": job.id,
                            "platform": job.platform,
                            "keyword": job.keyword,
                            "scheduled_at": job.scheduled_at.isoformat(),
                        },
                        response_payload={
                            "error": (
                                "No analysis snapshot found for this project/platform. "
                                "Please run project analysis first."
                            ),
                        },
                        source_url=project.source_url,
                        platforms=[job.platform],
                    )
                    self._set_job_status(
                        session=session,
                        job=job,
                        status="FAILED",
                        error_code="SNAPSHOT_REQUIRED",
                        error_message=(
                            "No analysis snapshot found for this project/platform. "
                            "Please run project analysis first."
                        ),
                        conversation_run_id=run.id,
                    )
                    return AutopostServiceOutput(
                        status=False,
                        error=(
                            "No analysis snapshot found for this project/platform. "
                            "Please run project analysis first."
                        ),
                        code=409,
                    )

                rewrite_action = (
                    ChatAction.REWRITE_FACEBOOK_ONLY
                    if job.platform == "facebook"
                    else ChatAction.REWRITE_LINKEDIN_ONLY
                )
                rewrite_result = self._chat_action_workflow_service.process(
                    ChatActionWorkflowInput(
                        action=rewrite_action,
                        prompt=rewrite_prompt,
                        selected_model=None,
                        source_url=(snapshot.source_url or project.source_url or None),
                        snapshot=snapshot,
                        owner_user_id=job.user_id,
                    )
                )
                if not rewrite_result.status:
                    run_conversation = self._upsert_single_project_conversation(
                        project_id=job.project_id, session=session
                    )
                    run = self._create_run(
                        session=session,
                        project_id=job.project_id,
                        conversation_id=run_conversation.id or "",
                        status="failed",
                        request_payload={
                            "trigger": "autopost_rewrite",
                            "job_id": job.id,
                            "platform": job.platform,
                            "keyword": job.keyword,
                            "scheduled_at": job.scheduled_at.isoformat(),
                        },
                        response_payload={
                            "error": rewrite_result.error
                            or "Failed to rewrite content from snapshot.",
                            "source_snapshot_run_id": (
                                source_run.id if source_run is not None else None
                            ),
                            "source_snapshot_type": snapshot_source,
                        },
                        source_url=project.source_url,
                        platforms=[job.platform],
                    )
                    self._set_job_status(
                        session=session,
                        job=job,
                        status="FAILED",
                        error_code="AUTOPOST_REWRITE_FAILED",
                        error_message=rewrite_result.error
                        or "Failed to rewrite content from snapshot.",
                        conversation_run_id=run.id,
                    )
                    return AutopostServiceOutput(
                        status=False,
                        error=rewrite_result.error
                        or "Failed to rewrite content from snapshot.",
                        code=rewrite_result.code,
                    )

                updated_snapshot = snapshot
                selected_post = rewrite_result.patch.social_post
                try:
                    updated_snapshot, _ = apply_partial_update(
                        snapshot=snapshot,
                        patch=rewrite_result.patch,
                        action=rewrite_action,
                    )
                except Exception:
                    updated_snapshot = snapshot
                if selected_post is None:
                    selected_post = self._find_snapshot_post(
                        updated_snapshot,
                        job.platform,
                    )
                if selected_post is None:
                    self._set_job_status(
                        session=session,
                        job=job,
                        status="FAILED",
                        error_code="PLATFORM_POST_NOT_FOUND",
                        error_message=f"No rewritten content for {job.platform}.",
                    )
                    return AutopostServiceOutput(
                        status=False,
                        error=f"No rewritten content for {job.platform}.",
                        code=409,
                    )

                post_payload = selected_post.model_dump(mode="json")
                final_text = self._build_post_text(post_payload)
                expected_language = LanguagePolicyService().detect_target_language(
                    rewrite_prompt
                )
                quality_score, quality_flags = self._evaluate_quality(
                    content=final_text,
                    platform=job.platform,
                    expected_language=expected_language,
                )
                run_conversation = self._upsert_single_project_conversation(
                    project_id=job.project_id, session=session
                )
                run = self._create_run(
                    session=session,
                    project_id=job.project_id,
                    conversation_id=run_conversation.id or "",
                    status="completed",
                    request_payload={
                        "trigger": "autopost_rewrite",
                        "job_id": job.id,
                        "platform": job.platform,
                        "keyword": job.keyword,
                        "scheduled_at": job.scheduled_at.isoformat(),
                    },
                    response_payload={
                        "content_plan_snapshot": updated_snapshot.model_dump(
                            mode="json"
                        ),
                        "selected_post": post_payload,
                        "assistant_text": rewrite_result.assistant_text,
                        "source_snapshot_run_id": (
                            source_run.id if source_run is not None else None
                        ),
                        "source_snapshot_type": snapshot_source,
                    },
                    source_url=project.source_url,
                    platforms=[job.platform],
                )
                updated_job = self._set_job_status(
                    session=session,
                    job=job,
                    status="READY",
                    draft_content=final_text,
                    final_content=final_text,
                    quality_score=quality_score,
                    quality_flags=quality_flags,
                    conversation_run_id=run.id,
                    expected_statuses=["GENERATING"],
                )
                if updated_job is None:
                    return AutopostServiceOutput(
                        status=False, error="Job not found.", code=404
                    )
                if (
                    Settings().autopost.enable_quality_gate
                    and Settings().autopost.require_review_on_quality_failure
                    and quality_score < Settings().autopost.quality_min_score
                ):
                    review_job = self._set_job_status(
                        session=session,
                        job=updated_job,
                        status="NEEDS_REVIEW",
                        error_code="QUALITY_GATE_FAILED",
                        error_message=(
                            "Generated content requires manual review before publishing."
                        ),
                        expected_statuses=["READY"],
                    )
                    return AutopostServiceOutput(
                        status=True,
                        data=review_job or updated_job,
                        code=200,
                    )
                return self._publish_ready_job(
                    session=session,
                    job=updated_job,
                    final_text=final_text,
                )
        except Exception as exc:
            logger.exception(
                "autopost_process_job_failed", error=redact_message(str(exc))
            )
            return AutopostServiceOutput(
                status=False,
                error=f"Unexpected error while processing job: {redact_message(str(exc))}",
                code=500,
            )

    def publish_linkedin_job(
        self, inputs: ProcessAutopostJobInput
    ) -> AutopostServiceOutput:
        try:
            with self._db.get_session() as session:
                job = self._db.get_autopost_job_by_id(session=session, id=inputs.job_id)
                if job is None:
                    return AutopostServiceOutput(
                        status=False, error="Job not found.", code=404
                    )
                if job.platform != "linkedin":
                    return AutopostServiceOutput(
                        status=False, error="Job is not a LinkedIn job.", code=409
                    )
                if job.status in {"CANCELLED", "PUBLISHED"}:
                    return AutopostServiceOutput(status=True, data=job, code=200)
                if not (job.final_content or "").strip():
                    return AutopostServiceOutput(
                        status=False,
                        error="Job has no final content to publish.",
                        code=409,
                    )
                return self._publish_ready_job(
                    session=session,
                    job=job,
                    final_text=job.final_content or "",
                )
        except Exception as exc:
            logger.exception(
                "autopost_publish_linkedin_failed", error=redact_message(str(exc))
            )
            return AutopostServiceOutput(
                status=False,
                error="Unexpected error while publishing LinkedIn job.",
                code=500,
            )

    def approve_and_publish(self, inputs: ApproveAutopostJobInput) -> AutopostServiceOutput:
        try:
            with self._db.get_session() as session:
                job = self._get_job_owned(
                    user_id=inputs.user_id,
                    job_id=inputs.job_id,
                    session=session,
                )
                if job is None:
                    return AutopostServiceOutput(
                        status=False, error="Job not found.", code=404
                    )
                if job.status in TERMINAL_JOB_STATUS:
                    return AutopostServiceOutput(
                        status=False,
                        error=f"Cannot approve job in status {job.status}.",
                        code=409,
                    )
                if not (job.final_content or "").strip():
                    return AutopostServiceOutput(
                        status=False,
                        error="Job has no final content to publish.",
                        code=409,
                    )
                ready_job = self._set_job_status(
                    session=session,
                    job=job,
                    status="READY",
                    error_code=None,
                    error_message=None,
                    expected_statuses=[
                        "NEEDS_REVIEW",
                        "READY",
                        "FAILED",
                        "PUBLISH_UNKNOWN",
                        "SCHEDULED",
                    ],
                )
                if ready_job is None:
                    return AutopostServiceOutput(
                        status=False,
                        error="Job status changed while approving.",
                        code=409,
                    )
                return self._publish_ready_job(
                    session=session,
                    job=ready_job,
                    final_text=ready_job.final_content or "",
                )
        except Exception as exc:
            logger.exception(
                "autopost_approve_publish_failed", error=redact_message(str(exc))
            )
            return AutopostServiceOutput(
                status=False,
                error="Unexpected error while approving auto-post job.",
                code=500,
            )

    def update_content_and_requeue(
        self, inputs: UpdateAutopostContentInput
    ) -> AutopostServiceOutput:
        content = self._normalize_content(inputs.content)
        if not content:
            return AutopostServiceOutput(
                status=False,
                error="Content must not be blank.",
                code=400,
            )
        try:
            with self._db.get_session() as session:
                job = self._get_job_owned(
                    user_id=inputs.user_id,
                    job_id=inputs.job_id,
                    session=session,
                )
                if job is None:
                    return AutopostServiceOutput(
                        status=False, error="Job not found.", code=404
                    )
                if job.status in {"PUBLISHED", "CANCELLED", "PUBLISHING"}:
                    return AutopostServiceOutput(
                        status=False,
                        error=f"Cannot update content in status {job.status}.",
                        code=409,
                    )
                expected_language = LanguagePolicyService().detect_target_language(
                    job.keyword
                )
                quality_score, quality_flags = self._evaluate_quality(
                    content=content,
                    platform=job.platform,
                    expected_language=expected_language,
                )
                target_status = "QUEUED"
                error_code = None
                error_message = None
                if bool(getattr(Settings().crew, "enable_policy_gate", True)):
                    policy_result = self._policy_service.evaluate_generated_text(content)
                    if policy_result.decision == PolicyDecision.HARD_BLOCK:
                        target_status = "NEEDS_REVIEW"
                        error_code = "POLICY_GATE_BLOCKED"
                        error_message = policy_result.reason
                        if "policy_violation" not in quality_flags:
                            quality_flags.append("policy_violation")
                if (
                    Settings().autopost.enable_quality_gate
                    and Settings().autopost.require_review_on_quality_failure
                    and quality_score < Settings().autopost.quality_min_score
                ):
                    target_status = "NEEDS_REVIEW"
                    error_code = "QUALITY_GATE_FAILED"
                    error_message = "Content requires manual review before publishing."
                updated = self._set_job_status(
                    session=session,
                    job=job,
                    status=target_status,
                    draft_content=content,
                    final_content=content,
                    quality_score=quality_score,
                    quality_flags=quality_flags,
                    error_code=error_code,
                    error_message=error_message,
                    idempotency_key=None,
                    expected_statuses=[
                        "FAILED",
                        "NEEDS_RECONNECT",
                        "PUBLISH_UNKNOWN",
                        "NEEDS_REVIEW",
                        "READY",
                        "SCHEDULED",
                        "QUEUED",
                    ],
                )
                if updated is None:
                    return AutopostServiceOutput(
                        status=False,
                        error="Job status changed while updating content.",
                        code=409,
                    )
            if updated.status == "QUEUED":
                from app.autopost_tasks import process_autopost_job

                process_autopost_job.delay(str(updated.id))
            return AutopostServiceOutput(
                status=True,
                data={"id": updated.id, "status": updated.status},
                code=200,
            )
        except Exception as exc:
            logger.exception(
                "autopost_update_content_failed", error=redact_message(str(exc))
            )
            return AutopostServiceOutput(
                status=False,
                error="Unexpected error while updating auto-post content.",
                code=500,
            )

    def reconcile_publish_unknown(self, inputs: ReconcileAutopostJobInput) -> AutopostServiceOutput:
        try:
            with self._db.get_session() as session:
                job = self._db.get_autopost_job_by_id(session=session, id=inputs.job_id)
                if job is None:
                    return AutopostServiceOutput(
                        status=False, error="Job not found.", code=404
                    )
                if job.status != "PUBLISH_UNKNOWN":
                    return AutopostServiceOutput(status=True, data=job, code=200)
                if (job.provider_post_id or "").strip():
                    published = self._set_job_status(
                        session=session,
                        job=job,
                        status="PUBLISHED",
                        error_code=None,
                        error_message=None,
                        expected_statuses=["PUBLISH_UNKNOWN"],
                    )
                    return AutopostServiceOutput(status=True, data=published, code=200)
                failed = self._set_job_status(
                    session=session,
                    job=job,
                    status="FAILED",
                    error_code="RECONCILE_UNCERTAIN",
                    error_message="Could not confirm publish result. Please retry.",
                    expected_statuses=["PUBLISH_UNKNOWN"],
                )
                return AutopostServiceOutput(status=True, data=failed, code=200)
        except Exception as exc:
            logger.exception(
                "autopost_reconcile_publish_unknown_failed",
                error=redact_message(str(exc)),
            )
            return AutopostServiceOutput(
                status=False,
                error="Unexpected error while reconciling publish state.",
                code=500,
            )

    def publish_due_linkedin_jobs(self, limit: int = 100) -> AutopostServiceOutput:
        processed_ids: list[str] = []
        try:
            with self._db.get_session() as session:
                due_jobs = self._db.list_due_linkedin_jobs(
                    session=session,
                    now_utc=self._utc_now(),
                    limit=limit,
                )
            for due_job in due_jobs:
                result = self.publish_linkedin_job(
                    ProcessAutopostJobInput(job_id=str(due_job.id))
                )
                if result.status:
                    processed_ids.append(str(due_job.id))
            return AutopostServiceOutput(
                status=True, data={"processed_job_ids": processed_ids}, code=200
            )
        except Exception as exc:
            logger.exception(
                "autopost_publish_due_linkedin_failed",
                error=redact_message(str(exc)),
            )
            return AutopostServiceOutput(
                status=False,
                error="Unexpected error while publishing due LinkedIn jobs.",
                code=500,
            )
