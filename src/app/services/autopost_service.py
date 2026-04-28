from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from app.workflows.content_pipeline import ContentPlanningInput, ContentPlanningService
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
from shared.settings.models import PostgresSettings

from .social_publish_service import SocialPublishInput, SocialPublishService

logger = get_logger(__name__)


JOB_STATUS = {
    "QUEUED",
    "GENERATING",
    "READY",
    "SCHEDULED",
    "PUBLISHED",
    "FAILED",
    "NEEDS_RECONNECT",
    "CANCELLED",
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
    keyword: str
    scheduled_at: datetime
    publish_mode: str = "schedule"
    page_id: str | None = None


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
        self._content_planner = ContentPlanningService()
        self._social_publish_service = SocialPublishService()

    @staticmethod
    def _utc_now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _normalize_platform(value: str | None) -> str:
        return (value or "").strip().lower()

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
            selected_model="gpt-4o-mini",
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

    def create_job(self, inputs: CreateAutopostJobInput) -> AutopostServiceOutput:
        try:
            platform = self._normalize_platform(inputs.platform)
            if platform not in {"linkedin", "facebook"}:
                return AutopostServiceOutput(
                    status=False,
                    error="Unsupported platform. Allowed: linkedin, facebook.",
                    code=400,
                )
            keyword = inputs.keyword.strip()
            if not keyword:
                return AutopostServiceOutput(
                    status=False,
                    error="Keyword must not be blank.",
                    code=400,
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
                        retry_count=0,
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
                if job.status in {"PUBLISHED", "CANCELLED"}:
                    return AutopostServiceOutput(
                        status=False,
                        error=f"Cannot cancel job in status {job.status}.",
                        code=409,
                    )
                updated = self._db.update_autopost_job(
                    session=session,
                    model=AutopostJob(
                        id=job.id,
                        project_id=job.project_id,
                        user_id=job.user_id,
                        platform=job.platform,
                        keyword=job.keyword,
                        timezone=job.timezone,
                        scheduled_at=job.scheduled_at,
                        status="CANCELLED",
                        page_id=job.page_id,
                        draft_content=job.draft_content,
                        final_content=job.final_content,
                        provider_post_id=job.provider_post_id,
                        provider_schedule_id=job.provider_schedule_id,
                        error_code=job.error_code,
                        error_message=job.error_message,
                        retry_count=job.retry_count,
                        conversation_run_id=job.conversation_run_id,
                    ),
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
                if job.status not in {"FAILED", "NEEDS_RECONNECT"}:
                    return AutopostServiceOutput(
                        status=False,
                        error="Retry is only allowed for FAILED or NEEDS_RECONNECT jobs.",
                        code=409,
                    )
                updated = self._db.update_autopost_job(
                    session=session,
                    model=AutopostJob(
                        id=job.id,
                        project_id=job.project_id,
                        user_id=job.user_id,
                        platform=job.platform,
                        keyword=job.keyword,
                        timezone=job.timezone,
                        scheduled_at=job.scheduled_at,
                        status="QUEUED",
                        page_id=job.page_id,
                        draft_content=job.draft_content,
                        final_content=job.final_content,
                        provider_post_id=job.provider_post_id,
                        provider_schedule_id=job.provider_schedule_id,
                        error_code=None,
                        error_message=None,
                        retry_count=job.retry_count + 1,
                        conversation_run_id=job.conversation_run_id,
                    ),
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
    ) -> AutopostJob | None:
        return self._db.update_autopost_job(
            session=session,
            model=AutopostJob(
                id=job.id,
                project_id=job.project_id,
                user_id=job.user_id,
                platform=job.platform,
                keyword=job.keyword,
                timezone=job.timezone,
                scheduled_at=job.scheduled_at,
                status=status,
                page_id=job.page_id,
                draft_content=draft_content
                if draft_content is not None
                else job.draft_content,
                final_content=final_content
                if final_content is not None
                else job.final_content,
                provider_post_id=provider_post_id
                if provider_post_id is not None
                else job.provider_post_id,
                provider_schedule_id=provider_schedule_id
                if provider_schedule_id is not None
                else job.provider_schedule_id,
                error_code=error_code,
                error_message=error_message,
                retry_count=job.retry_count,
                conversation_run_id=conversation_run_id
                if conversation_run_id is not None
                else job.conversation_run_id,
            ),
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
                if not (project.source_url or "").strip():
                    self._set_job_status(
                        session=session,
                        job=job,
                        status="FAILED",
                        error_code="SOURCE_URL_REQUIRED",
                        error_message="Project source_url is required for auto-post generation.",
                    )
                    return AutopostServiceOutput(
                        status=False,
                        error="Project source_url is required for auto-post generation.",
                        code=409,
                    )
                updated_job = self._set_job_status(
                    session=session,
                    job=job,
                    status="GENERATING",
                    error_code=None,
                    error_message=None,
                )
                if updated_job is not None:
                    job = updated_job

                content_result = self._content_planner.process(
                    ContentPlanningInput(
                        url=project.source_url or "",
                        additional_context=(
                            f"Keyword focus: {job.keyword}\n"
                            f"Generate high-quality content for platform: {job.platform}."
                        ),
                        requester_user_id=job.user_id,
                    )
                )
                content_data = content_result.data
                if (
                    not content_result.status
                    or content_data is None
                    or not hasattr(content_data, "social_posts")
                ):
                    run_conversation = self._upsert_single_project_conversation(
                        project_id=job.project_id, session=session
                    )
                    run = self._create_run(
                        session=session,
                        project_id=job.project_id,
                        conversation_id=run_conversation.id or "",
                        status="failed",
                        request_payload={
                            "trigger": "autopost",
                            "job_id": job.id,
                            "platform": job.platform,
                            "keyword": job.keyword,
                        },
                        response_payload={
                            "error": content_result.error
                            or "Failed to generate content.",
                        },
                        source_url=project.source_url,
                        platforms=[job.platform],
                    )
                    self._set_job_status(
                        session=session,
                        job=job,
                        status="FAILED",
                        error_code="AUTPOST_GENERATION_FAILED",
                        error_message=content_result.error
                        or "Failed to generate content.",
                        conversation_run_id=run.id,
                    )
                    return AutopostServiceOutput(
                        status=False,
                        error=content_result.error or "Failed to generate content.",
                        code=400,
                    )

                posts = getattr(content_data, "social_posts", [])
                selected_post = None
                for post in posts:
                    post_platform = str(getattr(post, "platform", "")).strip().lower()
                    if post_platform == job.platform:
                        selected_post = post
                        break
                if selected_post is None:
                    self._set_job_status(
                        session=session,
                        job=job,
                        status="FAILED",
                        error_code="PLATFORM_POST_NOT_FOUND",
                        error_message=f"No generated content for {job.platform}.",
                    )
                    return AutopostServiceOutput(
                        status=False,
                        error=f"No generated content for {job.platform}.",
                        code=409,
                    )

                post_payload = selected_post.model_dump(mode="json")
                final_text = self._build_post_text(post_payload)
                run_conversation = self._upsert_single_project_conversation(
                    project_id=job.project_id, session=session
                )
                run = self._create_run(
                    session=session,
                    project_id=job.project_id,
                    conversation_id=run_conversation.id or "",
                    status="completed",
                    request_payload={
                        "trigger": "autopost",
                        "job_id": job.id,
                        "platform": job.platform,
                        "keyword": job.keyword,
                        "scheduled_at": job.scheduled_at.isoformat(),
                    },
                    response_payload={
                        "content_plan_snapshot": content_data.model_dump(mode="json"),
                        "selected_post": post_payload,
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
                    conversation_run_id=run.id,
                )
                if updated_job is None:
                    return AutopostServiceOutput(
                        status=False, error="Job not found.", code=404
                    )
                job = updated_job

                if job.platform == "facebook":
                    if job.scheduled_at <= self._utc_now():
                        publish_result = self._social_publish_service.publish(
                            SocialPublishInput(
                                user_id=job.user_id,
                                platform="facebook",
                                content=final_text,
                                page_id=(job.page_id or "").strip(),
                            )
                        )
                        if not publish_result.status:
                            status_value = (
                                "NEEDS_RECONNECT"
                                if publish_result.error_code == "SOCIAL_TOKEN_EXPIRED"
                                else "FAILED"
                            )
                            self._set_job_status(
                                session=session,
                                job=job,
                                status=status_value,
                                error_code=publish_result.error_code,
                                error_message=publish_result.error,
                            )
                            return AutopostServiceOutput(
                                status=False,
                                error=publish_result.error,
                                code=publish_result.code,
                            )
                        payload = (
                            publish_result.data
                            if isinstance(publish_result.data, dict)
                            else {}
                        )
                        final_job = self._set_job_status(
                            session=session,
                            job=job,
                            status="PUBLISHED",
                            provider_post_id=str(
                                payload.get("provider_post_id") or ""
                            ).strip()
                            or None,
                            provider_schedule_id=str(
                                payload.get("provider_schedule_id") or ""
                            ).strip()
                            or None,
                            error_code=None,
                            error_message=None,
                        )
                        return AutopostServiceOutput(
                            status=True, data=final_job, code=200
                        )

                    schedule_result = self._social_publish_service.schedule_facebook(
                        user_id=job.user_id,
                        content=final_text,
                        page_id=(job.page_id or "").strip(),
                        scheduled_at=job.scheduled_at,
                    )
                    if not schedule_result.status:
                        status_value = (
                            "NEEDS_RECONNECT"
                            if schedule_result.error_code == "SOCIAL_TOKEN_EXPIRED"
                            else "FAILED"
                        )
                        self._set_job_status(
                            session=session,
                            job=job,
                            status=status_value,
                            error_code=schedule_result.error_code,
                            error_message=schedule_result.error,
                        )
                        return AutopostServiceOutput(
                            status=False,
                            error=schedule_result.error,
                            code=schedule_result.code,
                        )
                    payload = (
                        schedule_result.data
                        if isinstance(schedule_result.data, dict)
                        else {}
                    )
                    final_job = self._set_job_status(
                        session=session,
                        job=job,
                        status="SCHEDULED",
                        provider_post_id=str(
                            payload.get("provider_post_id") or ""
                        ).strip()
                        or None,
                        provider_schedule_id=str(
                            payload.get("provider_schedule_id") or ""
                        ).strip()
                        or None,
                        error_code=None,
                        error_message=None,
                    )
                    return AutopostServiceOutput(status=True, data=final_job, code=200)

                # LinkedIn uses internal scheduler.
                final_status = (
                    "PUBLISHED" if job.scheduled_at <= self._utc_now() else "SCHEDULED"
                )
                if final_status == "SCHEDULED":
                    final_job = self._set_job_status(
                        session=session,
                        job=job,
                        status="SCHEDULED",
                        error_code=None,
                        error_message=None,
                    )
                    return AutopostServiceOutput(status=True, data=final_job, code=200)

            # Immediate linkedin publish path after session commit.
            return self.publish_linkedin_job(
                ProcessAutopostJobInput(job_id=inputs.job_id)
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
                publish_result = self._social_publish_service.publish(
                    SocialPublishInput(
                        user_id=job.user_id,
                        platform="linkedin",
                        content=job.final_content or "",
                    )
                )
                if not publish_result.status:
                    status_value = (
                        "NEEDS_RECONNECT"
                        if publish_result.error_code == "SOCIAL_TOKEN_EXPIRED"
                        else "FAILED"
                    )
                    updated = self._set_job_status(
                        session=session,
                        job=job,
                        status=status_value,
                        error_code=publish_result.error_code,
                        error_message=publish_result.error,
                    )
                    return AutopostServiceOutput(
                        status=False,
                        data=updated,
                        error=publish_result.error,
                        code=publish_result.code,
                    )
                payload = (
                    publish_result.data if isinstance(publish_result.data, dict) else {}
                )
                updated = self._set_job_status(
                    session=session,
                    job=job,
                    status="PUBLISHED",
                    provider_post_id=str(payload.get("provider_post_id") or "").strip()
                    or None,
                    provider_schedule_id=str(
                        payload.get("provider_schedule_id") or ""
                    ).strip()
                    or None,
                    error_code=None,
                    error_message=None,
                )
                if updated is None:
                    return AutopostServiceOutput(
                        status=False, error="Job not found.", code=404
                    )
                conversation = self._upsert_single_project_conversation(
                    project_id=job.project_id, session=session
                )
                run = self._create_run(
                    session=session,
                    project_id=job.project_id,
                    conversation_id=conversation.id or "",
                    status="completed",
                    request_payload={
                        "trigger": "autopost_publish",
                        "job_id": job.id,
                        "platform": "linkedin",
                    },
                    response_payload=payload,
                    source_url=None,
                    platforms=["linkedin"],
                )
                updated = self._set_job_status(
                    session=session,
                    job=updated,
                    status=updated.status,
                    conversation_run_id=run.id,
                )
                return AutopostServiceOutput(status=True, data=updated, code=200)
        except Exception as exc:
            logger.exception(
                "autopost_publish_linkedin_failed", error=redact_message(str(exc))
            )
            return AutopostServiceOutput(
                status=False,
                error="Unexpected error while publishing LinkedIn job.",
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
