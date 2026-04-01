from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from hashlib import sha256
from threading import Event, Lock
from time import monotonic
from typing import Any, Deque, Optional, Union

from crewai import Crew, Process
from pydantic import PrivateAttr

from app.agents import (
    create_analyzer_agent,
    create_copywriter_agent,
    create_editor_agent,
    create_strategist_agent,
)
from app.tasks import (
    create_analyze_task,
    create_review_task,
    create_strategize_task,
    create_write_task,
)
from domain.models.models import ContentPlanOutput, DraftAnalysis, SocialPostsBundle
from infra.tools.scraper import ScraperToolError
from infra.tools.tools import UnsupportedModelError
from shared.base import BaseModel, BaseService
from shared.logging import get_logger
from shared.logging import redact_message
from shared.settings import Settings
from shared.settings.models import CrewSettings

logger = get_logger(__name__)


@dataclass
class _InFlightRequest:
    event: Event = field(default_factory=Event)
    result: ContentPlanningOutput | None = None


@dataclass
class _CachedResult:
    result: ContentPlanningOutput
    expires_at: float


class ContentPlanningInput(BaseModel):
    url: str
    additional_context: Optional[str] = None
    selected_model: Optional[str] = None
    requester_user_id: Optional[str] = None


class ContentPlanningOutput(BaseModel):
    status: bool
    data: Optional[Union[ContentPlanOutput, Any]] = None
    error: Optional[str] = None
    code: int = 200


class ContentPlanningService(BaseService):
    @staticmethod
    def _classify_runtime_error_code(exc: Exception) -> int:
        message = redact_message(str(exc)).lower()
        timeout_markers = [
            "request timed out",
            "timeout",
            "timed out",
            "read timeout",
            "connect timeout",
        ]
        upstream_markers = [
            "failed to connect to openai api",
            "connectionerror",
            "api connection",
            "temporary failure in name resolution",
        ]
        if any(marker in message for marker in timeout_markers):
            return 504
        if any(marker in message for marker in upstream_markers):
            return 502
        return 500

    _state_lock: Lock = PrivateAttr(default_factory=Lock)
    _inflight_requests: dict[str, _InFlightRequest] = PrivateAttr(default_factory=dict)
    _cached_results: dict[str, _CachedResult] = PrivateAttr(default_factory=dict)
    _rate_limit_windows: dict[str, Deque[float]] = PrivateAttr(
        default_factory=lambda: defaultdict(deque)
    )

    @staticmethod
    def _normalize_text(value: str | None) -> str:
        if value is None:
            return ""
        return " ".join(value.strip().split())

    @classmethod
    def _build_request_key(
        cls,
        *,
        requester_user_id: str,
        url: str,
        additional_context: str,
        selected_model: str | None,
    ) -> str:
        payload = "|".join(
            [
                requester_user_id,
                cls._normalize_text(url),
                cls._normalize_text(additional_context),
                cls._normalize_text(selected_model),
            ]
        )
        return sha256(payload.encode("utf-8")).hexdigest()

    def _apply_rate_limit(
        self,
        *,
        requester_user_id: str,
        crew_cfg: CrewSettings,
    ) -> ContentPlanningOutput | None:
        if crew_cfg.rate_limit_max_requests <= 0:
            return None

        now = monotonic()
        window = float(crew_cfg.rate_limit_window_seconds)
        with self._state_lock:
            hits = self._rate_limit_windows[requester_user_id]
            while hits and now - hits[0] > window:
                hits.popleft()

            if len(hits) >= crew_cfg.rate_limit_max_requests:
                retry_after = max(1, int(window - (now - hits[0])))
                return ContentPlanningOutput(
                    status=False,
                    data=None,
                    error=(
                        "Too many content generation requests. "
                        f"Please retry after {retry_after}s."
                    ),
                    code=429,
                )
            hits.append(now)
        return None

    def _get_cached_result(self, *, request_key: str) -> ContentPlanningOutput | None:
        now = monotonic()
        with self._state_lock:
            expired_keys = [
                key
                for key, cache_entry in self._cached_results.items()
                if cache_entry.expires_at <= now
            ]
            for key in expired_keys:
                self._cached_results.pop(key, None)

            cache_entry = self._cached_results.get(request_key)
            if cache_entry is None:
                return None
            return cache_entry.result

    def _set_cached_result(
        self,
        *,
        request_key: str,
        result: ContentPlanningOutput,
        ttl_seconds: int,
    ) -> None:
        if ttl_seconds <= 0 or not result.status:
            return
        with self._state_lock:
            self._cached_results[request_key] = _CachedResult(
                result=result,
                expires_at=monotonic() + float(ttl_seconds),
            )

    def _acquire_inflight_slot(
        self, *, request_key: str
    ) -> tuple[_InFlightRequest, bool]:
        with self._state_lock:
            existing = self._inflight_requests.get(request_key)
            if existing is not None:
                return existing, False
            entry = _InFlightRequest()
            self._inflight_requests[request_key] = entry
            return entry, True

    def _release_inflight_slot(
        self,
        *,
        request_key: str,
        entry: _InFlightRequest,
        result: ContentPlanningOutput,
    ) -> None:
        with self._state_lock:
            entry.result = result
            entry.event.set()
            self._inflight_requests.pop(request_key, None)

    def process(self, inputs: ContentPlanningInput) -> ContentPlanningOutput:
        selected_model = (inputs.selected_model or "").strip() or None
        requester_user_id = (
            inputs.requester_user_id or "anonymous"
        ).strip() or "anonymous"
        crew_cfg = Settings().crew

        rate_limit_error = self._apply_rate_limit(
            requester_user_id=requester_user_id,
            crew_cfg=crew_cfg,
        )
        if rate_limit_error is not None:
            logger.warning(
                "content_plan_rate_limited",
                requester_user_id=requester_user_id,
                url=inputs.url,
            )
            return rate_limit_error

        request_key = self._build_request_key(
            requester_user_id=requester_user_id,
            url=inputs.url,
            additional_context=inputs.additional_context or "",
            selected_model=selected_model,
        )

        cached_result = self._get_cached_result(request_key=request_key)
        if cached_result is not None:
            logger.info(
                "content_plan_cache_hit",
                requester_user_id=requester_user_id,
                url=inputs.url,
            )
            return cached_result

        inflight_entry, is_owner = self._acquire_inflight_slot(request_key=request_key)
        if not is_owner:
            logger.info(
                "content_plan_inflight_dedup_wait",
                requester_user_id=requester_user_id,
                url=inputs.url,
            )
            waited = inflight_entry.event.wait(
                timeout=float(crew_cfg.inflight_wait_timeout_seconds)
            )
            if not waited:
                return ContentPlanningOutput(
                    status=False,
                    data=None,
                    error=(
                        "An identical content generation request is already running. "
                        "Please retry shortly."
                    ),
                    code=409,
                )
            if inflight_entry.result is not None:
                return inflight_entry.result
            return ContentPlanningOutput(
                status=False,
                data=None,
                error="In-flight request finished without result.",
                code=500,
            )

        final_result = ContentPlanningOutput(
            status=False,
            data=None,
            error="Unexpected content planning failure.",
            code=500,
        )
        try:
            analyzer_agent = create_analyzer_agent(
                model_override=selected_model, crew_settings=crew_cfg
            )
            strategist_agent = create_strategist_agent(
                model_override=selected_model, crew_settings=crew_cfg
            )
            copywriter_agent = create_copywriter_agent(
                model_override=selected_model, crew_settings=crew_cfg
            )
            editor_agent = create_editor_agent(
                model_override=selected_model, crew_settings=crew_cfg
            )

            analyze_task = create_analyze_task(analyzer_agent, inputs.url)
            strategize_task = create_strategize_task(strategist_agent)
            write_task = create_write_task(copywriter_agent)
            review_task = create_review_task(editor_agent)

            strategize_task.context = [analyze_task]
            write_task.context = [analyze_task, strategize_task]
            review_task.context = [write_task]

            crew = Crew(
                agents=[
                    analyzer_agent,
                    strategist_agent,
                    copywriter_agent,
                    editor_agent,
                ],
                tasks=[analyze_task, strategize_task, write_task, review_task],
                process=Process.sequential,
                verbose=crew_cfg.verbose,
            )

            crew.kickoff(
                inputs={
                    "url": inputs.url,
                    "additional_context": inputs.additional_context or "",
                }
            )

            analysis: DraftAnalysis = analyze_task.output.pydantic
            reviewed_posts: SocialPostsBundle = review_task.output.pydantic

            final_output = ContentPlanOutput(
                source_url=inputs.url,
                analysis=analysis,
                social_posts=reviewed_posts.posts,
            )
            final_result = ContentPlanningOutput(
                status=True, data=final_output, error=None, code=200
            )
            self._set_cached_result(
                request_key=request_key,
                result=final_result,
                ttl_seconds=crew_cfg.result_cache_ttl_seconds,
            )
            return final_result
        except UnsupportedModelError as exc:
            logger.warning(
                "Unsupported model selected for content planning.", error=str(exc)
            )
            final_result = ContentPlanningOutput(
                status=False,
                data=None,
                error=str(exc),
                code=400,
            )
            return final_result
        except ScraperToolError as exc:
            logger.warning(
                "Content planning aborted due to scraper failure.",
                error=str(exc),
                url=inputs.url,
            )
            final_result = ContentPlanningOutput(
                status=False,
                data=None,
                error=redact_message(str(exc)),
                code=502,
            )
            return final_result
        except Exception as exc:
            logger.exception("Content planning pipeline failed")
            error_code = self._classify_runtime_error_code(exc)
            final_result = ContentPlanningOutput(
                status=False,
                data=None,
                error=redact_message(str(exc)),
                code=error_code,
            )
            return final_result
        finally:
            self._release_inflight_slot(
                request_key=request_key,
                entry=inflight_entry,
                result=final_result,
            )
