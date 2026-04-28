from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from crewai import Agent, Crew, Process, Task
from pydantic import Field

from app.agents import (
    create_analyzer_agent,
    create_copywriter_agent,
    create_strategist_agent,
)
from app.services.chat_contracts import ChatAction
from app.workflows.agent_contracts import AgentContractGateway, WorkflowContractError
from app.workflows.chat_snapshot import ContentPlanSnapshot, SnapshotPatch
from app.workflows.content_pipeline import ContentPlanningInput, ContentPlanningService
from app.tasks import create_analyze_task
from domain.models.models import (
    ContentPlanOutput,
    DraftAnalysis,
    Platform,
    SocialPost,
    SocialPostsBundle,
)
from infra.tools.tools import get_crewai_llm
from infra.tools.tools import stream_llm_text
from shared.base import BaseModel
from shared.language_policy import LanguagePolicyService, TargetLanguage
from shared.exceptions import ScraperToolError, UnsupportedModelError
from shared.logging import get_logger, redact_message
from shared.settings import Settings
from shared.settings.models import CrewSettings

logger = get_logger(__name__)


class ChatActionWorkflowInput(BaseModel):
    action: ChatAction
    prompt: str
    selected_model: str | None = None
    source_url: str | None = None
    snapshot: ContentPlanSnapshot | None = None
    owner_user_id: str
    assistant_token_callback: Callable[[str], None] | None = None


class ChatActionWorkflowOutput(BaseModel):
    status: bool
    assistant_text: str
    patch: SnapshotPatch = Field(default_factory=SnapshotPatch)
    affected_sections: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    code: int = 200


class _StrategyOutput(BaseModel):
    strategy: str


class _ChatReplyOutput(BaseModel):
    reply: str


class ChatActionWorkflowService(BaseModel):
    @staticmethod
    def _is_small_talk_prompt(prompt: str) -> bool:
        normalized = " ".join(prompt.strip().lower().split())
        if not normalized:
            return False
        return bool(
            re.fullmatch(
                r"(xin chào|chào|chao|hello|hi|hey|alo|good morning|good afternoon|good evening)[!. ]*",
                normalized,
            )
        )

    @staticmethod
    def _normalize_prompt(prompt: str) -> str:
        return " ".join(prompt.strip().lower().split())

    @staticmethod
    def _truncate_text(value: str, limit: int = 180) -> str:
        normalized = " ".join(value.strip().split())
        if len(normalized) <= limit:
            return normalized
        return f"{normalized[:limit].rstrip()}..."

    @staticmethod
    def _fallback_assistant_reply(
        *,
        target_language: TargetLanguage,
        action: ChatAction,
    ) -> str:
        if target_language == "vi":
            if action == ChatAction.GENERAL_QA:
                return "Mình đã nhận yêu cầu. Bạn muốn mình chỉnh phần nào tiếp theo?"
            return "Mình đã cập nhật theo yêu cầu mới của bạn."
        if action == ChatAction.GENERAL_QA:
            return "I got your message. What should I refine next?"
        return "I updated the output based on your latest request."

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

    @staticmethod
    def _log_stage(
        *,
        status: str,
        stage: str,
        owner_user_id: str,
        action: ChatAction,
        language_used: TargetLanguage,
        conversation_id: str | None = None,
        **extra: Any,
    ) -> None:
        log_payload: dict[str, Any] = {
            "stage": stage,
            "status": status,
            "owner_user_id": owner_user_id,
            "conversation_id": conversation_id,
            "action": action.value,
            "language_used": language_used,
        }
        log_payload.update(extra)
        if status == "failed":
            logger.warning("chat_action_stage_failed", **log_payload)
            return
        logger.info("chat_action_stage_lifecycle", **log_payload)

    @staticmethod
    def _prompt_requests_link(prompt: str) -> bool:
        normalized = " ".join(prompt.strip().lower().split())
        if not normalized:
            return False
        markers = [
            "link",
            "url",
            "source",
            "blog",
            "nguon",
            "duong dan",
            "cuoi bai",
        ]
        return any(marker in normalized for marker in markers)

    @staticmethod
    def _inject_source_url_if_requested(
        *,
        prompt: str,
        source_url: str,
        post: SocialPost,
    ) -> SocialPost:
        if not source_url.strip():
            return post
        if not ChatActionWorkflowService._prompt_requests_link(prompt):
            return post
        merged_text = f"{post.hook}\n{post.body_content}\n{post.call_to_action}"
        if source_url in merged_text:
            return post
        cta = post.call_to_action.strip()
        updated_cta = f"{cta}\n{source_url}" if cta else source_url
        return post.model_copy(update={"call_to_action": updated_cta})

    @staticmethod
    def _compose_action_assistant_reply(
        *,
        action: ChatAction,
        prompt: str,
        target_language: TargetLanguage,
        selected_model: str | None,
        affected_sections: list[str],
        platform: Platform | None = None,
        repair_applied: bool = False,
        context_summary: str = "",
    ) -> str:
        sections = ", ".join(affected_sections) if affected_sections else "snapshot"
        language_name = "Vietnamese" if target_language == "vi" else "English"
        prompt_raw = " ".join(prompt.strip().split())
        prompt_normalized = ChatActionWorkflowService._normalize_prompt(prompt)
        context_line = ChatActionWorkflowService._truncate_text(context_summary, 260)
        platform_name = platform.value if platform is not None else "none"
        guardrail_prompt = (
            "You are an assistant that reports content-refinement outcomes naturally.\n"
            f"Use exactly {language_name}.\n"
            "Write 1-3 natural sentences.\n"
            "Stay grounded in the provided operation result. Do not invent extra changes.\n"
            "Do not output markdown symbols like '**' unless user asked for markdown.\n"
            "Do not output internal field paths unless the user explicitly asks for technical details.\n"
            "Avoid repetitive boilerplate. Keep wording conversational.\n"
            "Only mention normalization if it was actually applied.\n"
            f"Resolved action: {action.value}\n"
            f"Resolved platform: {platform_name}\n"
            f"Affected sections: {sections}\n"
            f"Repair applied: {repair_applied}\n"
            f"User prompt (raw): {prompt_raw}\n"
            f"User prompt (normalized): {prompt_normalized}\n"
            f"Change summary: {context_line or 'No material content delta summary available.'}\n"
            "Return only the assistant reply text."
        )
        try:
            reply_text = stream_llm_text(
                model_override=selected_model,
                prompt=guardrail_prompt,
            ).strip()
            if not reply_text:
                raise ValueError("Assistant reply composer returned empty text.")
            return reply_text
        except Exception as exc:
            logger.warning(
                "chat_action_assistant_reply_fallback",
                action=action.value,
                language_used=target_language,
                error=redact_message(str(exc)),
            )
            return ChatActionWorkflowService._fallback_assistant_reply(
                target_language=target_language,
                action=action,
            )

    def _build_single_post_task(
        self,
        *,
        agent: Agent,
        platform: Platform,
        prompt: str,
        target_language: TargetLanguage,
        snapshot: ContentPlanSnapshot,
        existing_post: SocialPost | None,
    ) -> Task:
        char_limit = 2000 if platform == Platform.FACEBOOK else 3000
        language_name = "Vietnamese" if target_language == "vi" else "English"
        supporting_claims_text = "; ".join(
            [
                f"{claim.claim} | evidence: {claim.evidence_excerpt}"
                for claim in snapshot.analysis.supporting_claims
            ]
        )
        existing_text = (
            f"Hook: {existing_post.hook}\nBody: {existing_post.body_content}\n"
            f"CTA: {existing_post.call_to_action}\nHashtags: {', '.join(existing_post.hashtags)}"
            if existing_post is not None
            else "No existing post for this platform."
        )
        return Task(
            description=(
                f"You must rewrite ONLY the '{platform.value}' post.\n"
                f"User request: {prompt}\n"
                "Hard requirements:\n"
                "- Follow user request exactly; do not ignore requested constraints.\n"
                "- Avoid generic intro-only writing. Deliver concrete value from source context.\n"
                "- Body must cover: Agitation/Interest -> Solution/Value -> Proof.\n"
                "- Include at least one concrete proof from supporting claims/evidence.\n"
                "- Keep exactly one clear CTA.\n"
                "- If user asks to include a link, include source_url at the end of CTA.\n"
                f"Current analysis:\n"
                f"- Core: {snapshot.analysis.core_message}\n"
                f"- Value proposition: {snapshot.analysis.value_proposition}\n"
                f"- Reader intent: {snapshot.analysis.reader_intent.value}\n"
                f"- Funnel stage: {snapshot.analysis.funnel_stage.value}\n"
                f"- Audience: {snapshot.analysis.target_audience}\n"
                f"- Pain points: {', '.join(snapshot.analysis.audience_pain_points)}\n"
                f"- Desired outcomes: {', '.join(snapshot.analysis.audience_desired_outcomes)}\n"
                f"- Tone: {snapshot.analysis.tone_of_voice}\n"
                f"- Voice guidelines: {', '.join(snapshot.analysis.voice_guidelines)}\n"
                f"- Primary CTA: {snapshot.analysis.primary_cta}\n"
                f"- CTA reasoning: {snapshot.analysis.cta_reasoning}\n"
                f"- Risk flags: {', '.join(snapshot.analysis.risk_flags)}\n"
                f"- Source URL: {snapshot.source_url}\n"
                f"- Supporting claims with evidence: {supporting_claims_text}\n"
                f"Current {platform.value} post:\n{existing_text}\n"
                f"Character limit: {char_limit}\n"
                f"Language requirement: return all text fields in {language_name}.\n"
                "Return valid SocialPost JSON with the exact platform."
            ),
            expected_output=(
                "SocialPost JSON with fields: platform, hook, body_content, call_to_action, hashtags."
            ),
            agent=agent,
            output_pydantic=SocialPost,
        )

    def _run_reanalyze_only(
        self,
        *,
        source_url: str,
        prompt: str,
        owner_user_id: str,
        target_language: TargetLanguage,
        selected_model: str | None,
        crew_settings: CrewSettings,
    ) -> ChatActionWorkflowOutput:
        self._log_stage(
            status="started",
            stage="reanalyze",
            owner_user_id=owner_user_id,
            action=ChatAction.REANALYZE_ONLY,
            language_used=target_language,
        )
        analyzer = create_analyzer_agent(
            model_override=selected_model,
            crew_settings=crew_settings,
        )
        analyze_task = create_analyze_task(analyzer, source_url, target_language)
        crew = Crew(
            agents=[analyzer],
            tasks=[analyze_task],
            process=Process.sequential,
            verbose=crew_settings.verbose,
        )
        crew.kickoff(inputs={"url": source_url, "additional_context": prompt})
        analysis = analyze_task.output.pydantic
        if not isinstance(analysis, DraftAnalysis):
            raise ValueError("Reanalyze output must be DraftAnalysis.")
        gateway = AgentContractGateway()
        validated_analysis, repair_applied = gateway.validate_analysis(
            analysis,
            target_language=target_language,
            stage="chat_reanalyze_output",
        )
        affected_sections = ["analysis"]
        analysis_summary = (
            f"Core message: {self._truncate_text(validated_analysis.core_message, 120)} | "
            f"Audience: {self._truncate_text(validated_analysis.target_audience, 90)}"
        )
        assistant_text = self._compose_action_assistant_reply(
            action=ChatAction.REANALYZE_ONLY,
            prompt=prompt,
            target_language=target_language,
            selected_model=selected_model,
            affected_sections=affected_sections,
            repair_applied=repair_applied,
            context_summary=analysis_summary,
        )
        self._log_stage(
            status="completed",
            stage="reanalyze",
            owner_user_id=owner_user_id,
            action=ChatAction.REANALYZE_ONLY,
            language_used=target_language,
            repair_applied=repair_applied,
        )
        return ChatActionWorkflowOutput(
            status=True,
            assistant_text=assistant_text,
            patch=SnapshotPatch(analysis=validated_analysis),
            affected_sections=affected_sections,
            metadata={
                "language_used": target_language,
                "repair_applied": repair_applied,
            },
            code=200,
        )

    def _run_rewrite_post_only(
        self,
        *,
        platform: Platform,
        prompt: str,
        owner_user_id: str,
        target_language: TargetLanguage,
        selected_model: str | None,
        snapshot: ContentPlanSnapshot,
        crew_settings: CrewSettings,
    ) -> ChatActionWorkflowOutput:
        action = (
            ChatAction.REWRITE_FACEBOOK_ONLY
            if platform == Platform.FACEBOOK
            else ChatAction.REWRITE_LINKEDIN_ONLY
        )
        self._log_stage(
            status="started",
            stage=f"rewrite_{platform.value}",
            owner_user_id=owner_user_id,
            action=action,
            language_used=target_language,
        )
        copywriter = create_copywriter_agent(
            model_override=selected_model,
            crew_settings=crew_settings,
        )
        existing = next(
            (post for post in snapshot.social_posts if post.platform == platform),
            None,
        )
        rewrite_task = self._build_single_post_task(
            agent=copywriter,
            platform=platform,
            prompt=prompt,
            target_language=target_language,
            snapshot=snapshot,
            existing_post=existing,
        )
        crew = Crew(
            agents=[copywriter],
            tasks=[rewrite_task],
            process=Process.sequential,
            verbose=crew_settings.verbose,
        )
        crew.kickoff(inputs={"prompt": prompt, "platform": platform.value})
        rewritten = rewrite_task.output.pydantic
        if not isinstance(rewritten, SocialPost):
            raise ValueError("Rewrite output must be SocialPost.")
        rewritten.platform = platform
        rewritten = self._inject_source_url_if_requested(
            prompt=prompt,
            source_url=snapshot.source_url,
            post=rewritten,
        )
        gateway = AgentContractGateway()
        validated_post, repair_applied = gateway.validate_social_post(
            rewritten,
            target_language=target_language,
            stage=f"chat_rewrite_{platform.value}_output",
            expected_platform=platform,
        )
        affected_sections = [f"social_posts.{platform.value}"]
        old_hook = existing.hook if existing is not None else ""
        change_summary = (
            f"Hook before: {self._truncate_text(old_hook, 100)} | "
            f"Hook after: {self._truncate_text(validated_post.hook, 100)} | "
            f"CTA after: {self._truncate_text(validated_post.call_to_action, 100)}"
        )
        assistant_text = self._compose_action_assistant_reply(
            action=action,
            prompt=prompt,
            target_language=target_language,
            selected_model=selected_model,
            affected_sections=affected_sections,
            platform=platform,
            repair_applied=repair_applied,
            context_summary=change_summary,
        )
        self._log_stage(
            status="completed",
            stage=f"rewrite_{platform.value}",
            owner_user_id=owner_user_id,
            action=action,
            language_used=target_language,
            repair_applied=repair_applied,
        )
        return ChatActionWorkflowOutput(
            status=True,
            assistant_text=assistant_text,
            patch=SnapshotPatch(social_post=validated_post),
            affected_sections=affected_sections,
            metadata={
                "language_used": target_language,
                "repair_applied": repair_applied,
            },
            code=200,
        )

    def _run_rewrite_strategy_only(
        self,
        *,
        prompt: str,
        owner_user_id: str,
        target_language: TargetLanguage,
        selected_model: str | None,
        snapshot: ContentPlanSnapshot,
        crew_settings: CrewSettings,
    ) -> ChatActionWorkflowOutput:
        language_name = "Vietnamese" if target_language == "vi" else "English"
        self._log_stage(
            status="started",
            stage="rewrite_strategy",
            owner_user_id=owner_user_id,
            action=ChatAction.REWRITE_STRATEGY_ONLY,
            language_used=target_language,
        )
        strategist = create_strategist_agent(
            model_override=selected_model,
            crew_settings=crew_settings,
        )
        task = Task(
            description=(
                "Create strategy direction only. Do not rewrite social posts.\n"
                f"User request: {prompt}\n"
                f"Core message: {snapshot.analysis.core_message}\n"
                f"Value proposition: {snapshot.analysis.value_proposition}\n"
                f"Reader intent: {snapshot.analysis.reader_intent.value}\n"
                f"Funnel stage: {snapshot.analysis.funnel_stage.value}\n"
                f"Audience: {snapshot.analysis.target_audience}\n"
                f"Pain points: {', '.join(snapshot.analysis.audience_pain_points)}\n"
                f"Desired outcomes: {', '.join(snapshot.analysis.audience_desired_outcomes)}\n"
                f"Primary CTA: {snapshot.analysis.primary_cta}\n"
                f"Risk flags: {', '.join(snapshot.analysis.risk_flags)}\n"
                f"Language requirement: strategy must be written in {language_name}.\n"
                "Return JSON with one field: strategy (short and actionable)."
            ),
            expected_output="JSON object with field strategy.",
            agent=strategist,
            output_pydantic=_StrategyOutput,
        )
        crew = Crew(
            agents=[strategist],
            tasks=[task],
            process=Process.sequential,
            verbose=crew_settings.verbose,
        )
        crew.kickoff(inputs={"prompt": prompt})
        strategy_output = task.output.pydantic
        if not isinstance(strategy_output, _StrategyOutput):
            raise ValueError("Strategy output is invalid.")
        strategy_text = strategy_output.strategy.strip()
        if not strategy_text:
            raise ValueError("Strategy output must not be blank.")
        if len(strategy_text.split()) < 8:
            raise ValueError("Strategy output is too short to be actionable.")
        if (
            LanguagePolicyService().detect_target_language(strategy_text)
            != target_language
        ):
            raise ValueError(f"Strategy language mismatch. expected={target_language}.")
        affected_sections = ["meta.strategy"]
        previous_strategy = (
            str(snapshot.meta.get("strategy", "")).strip() if snapshot.meta else ""
        )
        strategy_summary = (
            f"Strategy before: {self._truncate_text(previous_strategy, 100)} | "
            f"Strategy after: {self._truncate_text(strategy_text, 100)}"
        )
        assistant_text = self._compose_action_assistant_reply(
            action=ChatAction.REWRITE_STRATEGY_ONLY,
            prompt=prompt,
            target_language=target_language,
            selected_model=selected_model,
            affected_sections=affected_sections,
            repair_applied=False,
            context_summary=strategy_summary,
        )
        self._log_stage(
            status="completed",
            stage="rewrite_strategy",
            owner_user_id=owner_user_id,
            action=ChatAction.REWRITE_STRATEGY_ONLY,
            language_used=target_language,
            repair_applied=False,
        )
        return ChatActionWorkflowOutput(
            status=True,
            assistant_text=assistant_text,
            patch=SnapshotPatch(strategy=strategy_text),
            affected_sections=affected_sections,
            metadata={
                "language_used": target_language,
                "repair_applied": False,
            },
            code=200,
        )

    def _run_general_qa(
        self,
        *,
        prompt: str,
        owner_user_id: str,
        target_language: TargetLanguage,
        selected_model: str | None,
        snapshot: ContentPlanSnapshot | None,
        assistant_token_callback: Callable[[str], None] | None = None,
    ) -> ChatActionWorkflowOutput:
        language_name = "Vietnamese" if target_language == "vi" else "English"
        if self._is_small_talk_prompt(prompt):
            self._log_stage(
                status="completed",
                stage="general_qa",
                owner_user_id=owner_user_id,
                action=ChatAction.GENERAL_QA,
                language_used=target_language,
            )
            return ChatActionWorkflowOutput(
                status=True,
                assistant_text=self._compose_action_assistant_reply(
                    action=ChatAction.GENERAL_QA,
                    prompt=prompt,
                    target_language=target_language,
                    selected_model=selected_model,
                    affected_sections=[],
                    context_summary="No content update. Conversational greeting.",
                ),
                patch=SnapshotPatch(),
                affected_sections=[],
                metadata={"language_used": target_language},
                code=200,
            )
        self._log_stage(
            status="started",
            stage="general_qa",
            owner_user_id=owner_user_id,
            action=ChatAction.GENERAL_QA,
            language_used=target_language,
        )
        if assistant_token_callback is not None:
            snapshot_context = (
                f"Core: {snapshot.analysis.core_message}\n"
                f"Value proposition: {snapshot.analysis.value_proposition}\n"
                f"Reader intent: {snapshot.analysis.reader_intent.value}\n"
                f"Funnel stage: {snapshot.analysis.funnel_stage.value}\n"
                f"Audience: {snapshot.analysis.target_audience}\n"
                f"Primary CTA: {snapshot.analysis.primary_cta}\n"
                if snapshot is not None
                else "No snapshot available."
            )
            streamed_reply = stream_llm_text(
                model_override=selected_model,
                on_delta=assistant_token_callback,
                prompt="Reply naturally and keep snapshot unchanged.\n"
                f"Use exactly {language_name}.\n"
                "Answer the user's exact prompt directly in 1-3 sentences.\n"
                "Do not drift into unrelated topics.\n"
                "Do not dump raw fields like 'Core:' or 'Audience:' unless user explicitly asks.\n"
                "Use snapshot context only when it helps the current question.\n"
                f"User prompt: {prompt}\n"
                f"Snapshot context:\n{snapshot_context}\n"
                "Return only the final assistant reply text.",
            )
            reply_text = streamed_reply.strip()
            if not reply_text:
                raise ValueError("General QA streamed output is empty.")
            self._log_stage(
                status="completed",
                stage="general_qa",
                owner_user_id=owner_user_id,
                action=ChatAction.GENERAL_QA,
                language_used=target_language,
                streaming_used=True,
            )
            return ChatActionWorkflowOutput(
                status=True,
                assistant_text=reply_text,
                patch=SnapshotPatch(),
                affected_sections=[],
                metadata={
                    "language_used": target_language,
                    "streaming_used": True,
                },
                code=200,
            )

        llm = get_crewai_llm(model_override=selected_model)
        qa_agent = Agent(
            role="Campaign Assistant",
            goal="Answer naturally and concisely based on campaign context when available.",
            backstory=(
                "You are a helpful content refinement assistant. "
                "Do not mutate campaign snapshot unless explicitly requested by action."
            ),
            llm=llm,
            tools=[],
            allow_delegation=False,
            verbose=False,
            max_iter=1,
            max_retry_limit=0,
        )
        snapshot_context = (
            f"Core: {snapshot.analysis.core_message}\n"
            f"Value proposition: {snapshot.analysis.value_proposition}\n"
            f"Reader intent: {snapshot.analysis.reader_intent.value}\n"
            f"Funnel stage: {snapshot.analysis.funnel_stage.value}\n"
            f"Audience: {snapshot.analysis.target_audience}\n"
            f"Primary CTA: {snapshot.analysis.primary_cta}\n"
            if snapshot is not None
            else "No snapshot available."
        )
        task = Task(
            description=(
                "Reply naturally and keep snapshot unchanged.\n"
                f"Use exactly {language_name}.\n"
                "Answer the user's exact prompt directly in 1-3 sentences.\n"
                "Do not drift into unrelated topics.\n"
                "Do not dump raw fields like 'Core:' or 'Audience:' unless user explicitly asks.\n"
                "Use snapshot context only when it helps the current question.\n"
                f"User prompt: {prompt}\n"
                f"Snapshot context:\n{snapshot_context}\n"
                "Output JSON with only field 'reply'."
            ),
            expected_output="JSON object with field reply.",
            agent=qa_agent,
            output_pydantic=_ChatReplyOutput,
        )
        crew = Crew(
            agents=[qa_agent],
            tasks=[task],
            process=Process.sequential,
            verbose=False,
        )
        crew.kickoff(inputs={"prompt": prompt})
        reply_output = task.output.pydantic
        if not isinstance(reply_output, _ChatReplyOutput):
            raise ValueError("General QA output is invalid.")
        self._log_stage(
            status="completed",
            stage="general_qa",
            owner_user_id=owner_user_id,
            action=ChatAction.GENERAL_QA,
            language_used=target_language,
        )
        return ChatActionWorkflowOutput(
            status=True,
            assistant_text=reply_output.reply,
            patch=SnapshotPatch(),
            affected_sections=[],
            metadata={"language_used": target_language, "streaming_used": False},
            code=200,
        )

    def process(self, inputs: ChatActionWorkflowInput) -> ChatActionWorkflowOutput:
        target_language = LanguagePolicyService().detect_target_language(inputs.prompt)
        try:
            crew_settings = Settings().crew
            selected_model = (inputs.selected_model or "").strip() or None
            prompt = inputs.prompt.strip()

            if inputs.action == ChatAction.FULL_REGENERATE:
                if not inputs.source_url:
                    return ChatActionWorkflowOutput(
                        status=False,
                        assistant_text="",
                        error="Missing source URL for full regenerate.",
                        code=409,
                    )
                content_plan = ContentPlanningService().process(
                    ContentPlanningInput(
                        url=inputs.source_url,
                        additional_context=prompt,
                        selected_model=selected_model,
                        requester_user_id=inputs.owner_user_id,
                    )
                )
                if not content_plan.status:
                    return ChatActionWorkflowOutput(
                        status=False,
                        assistant_text="",
                        error=content_plan.error
                        or "Failed to regenerate full content plan.",
                        code=content_plan.code,
                    )
                if not isinstance(content_plan.data, ContentPlanOutput):
                    raise ValueError(
                        "Full regenerate output does not match expected schema."
                    )

                snapshot = ContentPlanSnapshot.from_content_plan(content_plan.data)
                gateway = AgentContractGateway()
                _, analysis_repair_applied = gateway.validate_analysis(
                    snapshot.analysis,
                    target_language=target_language,
                    stage="chat_full_regenerate_analysis",
                )
                posts_bundle, posts_repair_applied = (
                    gateway.validate_social_posts_bundle(
                        SocialPostsBundle(posts=snapshot.social_posts),
                        target_language=target_language,
                        stage="chat_full_regenerate_posts",
                    )
                )
                snapshot.social_posts = posts_bundle.posts
                repair_applied = analysis_repair_applied or posts_repair_applied
                affected_sections = ["analysis", "social_posts"]
                return ChatActionWorkflowOutput(
                    status=True,
                    assistant_text=self._compose_action_assistant_reply(
                        action=ChatAction.FULL_REGENERATE,
                        prompt=prompt,
                        target_language=target_language,
                        selected_model=selected_model,
                        affected_sections=affected_sections,
                        repair_applied=repair_applied,
                        context_summary=(
                            f"Regenerated full snapshot with {len(snapshot.social_posts)} social posts. "
                            f"Core message: {self._truncate_text(snapshot.analysis.core_message, 120)}"
                        ),
                    ),
                    patch=SnapshotPatch(full_snapshot=snapshot),
                    affected_sections=affected_sections,
                    metadata={
                        "language_used": target_language,
                        "repair_applied": repair_applied,
                    },
                    code=200,
                )

            if inputs.action == ChatAction.REANALYZE_ONLY:
                if not inputs.source_url:
                    return ChatActionWorkflowOutput(
                        status=False,
                        assistant_text="",
                        error="Missing source URL for reanalyze action.",
                        code=409,
                    )
                return self._run_reanalyze_only(
                    source_url=inputs.source_url,
                    prompt=prompt,
                    owner_user_id=inputs.owner_user_id,
                    target_language=target_language,
                    selected_model=selected_model,
                    crew_settings=crew_settings,
                )

            if inputs.action == ChatAction.REWRITE_FACEBOOK_ONLY:
                if inputs.snapshot is None:
                    return ChatActionWorkflowOutput(
                        status=False,
                        assistant_text="",
                        error="Snapshot is required for facebook rewrite.",
                        code=409,
                    )
                return self._run_rewrite_post_only(
                    platform=Platform.FACEBOOK,
                    prompt=prompt,
                    owner_user_id=inputs.owner_user_id,
                    target_language=target_language,
                    selected_model=selected_model,
                    snapshot=inputs.snapshot,
                    crew_settings=crew_settings,
                )

            if inputs.action == ChatAction.REWRITE_LINKEDIN_ONLY:
                if inputs.snapshot is None:
                    return ChatActionWorkflowOutput(
                        status=False,
                        assistant_text="",
                        error="Snapshot is required for linkedin rewrite.",
                        code=409,
                    )
                return self._run_rewrite_post_only(
                    platform=Platform.LINKEDIN,
                    prompt=prompt,
                    owner_user_id=inputs.owner_user_id,
                    target_language=target_language,
                    selected_model=selected_model,
                    snapshot=inputs.snapshot,
                    crew_settings=crew_settings,
                )

            if inputs.action == ChatAction.REWRITE_STRATEGY_ONLY:
                if inputs.snapshot is None:
                    return ChatActionWorkflowOutput(
                        status=False,
                        assistant_text="",
                        error="Snapshot is required for strategy rewrite.",
                        code=409,
                    )
                return self._run_rewrite_strategy_only(
                    prompt=prompt,
                    owner_user_id=inputs.owner_user_id,
                    target_language=target_language,
                    selected_model=selected_model,
                    snapshot=inputs.snapshot,
                    crew_settings=crew_settings,
                )

            return self._run_general_qa(
                prompt=prompt,
                owner_user_id=inputs.owner_user_id,
                target_language=target_language,
                selected_model=selected_model,
                snapshot=inputs.snapshot,
                assistant_token_callback=inputs.assistant_token_callback,
            )
        except WorkflowContractError as exc:
            self._log_stage(
                status="failed",
                stage=exc.stage,
                owner_user_id=inputs.owner_user_id,
                action=inputs.action,
                language_used=target_language,
                error_code=exc.code,
                error=redact_message(exc.detail),
            )
            return ChatActionWorkflowOutput(
                status=False,
                assistant_text="",
                error=f"{exc.code}: {redact_message(exc.detail)}",
                code=422,
                metadata={
                    "language_used": target_language,
                    "contract_error": {"code": exc.code, "stage": exc.stage},
                },
            )
        except UnsupportedModelError as exc:
            logger.warning(
                "chat_action_unsupported_model", error=redact_message(str(exc))
            )
            return ChatActionWorkflowOutput(
                status=False,
                assistant_text="",
                error=redact_message(str(exc)),
                code=400,
                metadata={"language_used": target_language},
            )
        except ScraperToolError as exc:
            logger.warning("chat_action_scraper_failed", error=redact_message(str(exc)))
            return ChatActionWorkflowOutput(
                status=False,
                assistant_text="",
                error=redact_message(str(exc)),
                code=502,
                metadata={"language_used": target_language},
            )
        except Exception as exc:
            self._log_stage(
                status="failed",
                stage="workflow_process",
                owner_user_id=inputs.owner_user_id,
                action=inputs.action,
                language_used=target_language,
                error=redact_message(str(exc)),
            )
            logger.exception(
                "chat_action_workflow_failed", error=redact_message(str(exc))
            )
            error_code = self._classify_runtime_error_code(exc)
            return ChatActionWorkflowOutput(
                status=False,
                assistant_text="",
                error=redact_message(str(exc)),
                code=error_code,
                metadata={"language_used": target_language},
            )
