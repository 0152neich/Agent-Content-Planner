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
    def _build_small_talk_reply(target_language: TargetLanguage) -> str:
        if target_language == "vi":
            return "Chào bạn, mình ở đây. Bạn muốn mình chỉnh nội dung nào tiếp theo?"
        return "Hi there, I am here. What would you like me to refine next?"

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
    def _stable_variant(seed: str, size: int) -> int:
        if size <= 1:
            return 0
        return sum(ord(ch) for ch in seed) % size

    @staticmethod
    def _build_action_assistant_text(
        *,
        action: ChatAction,
        target_language: TargetLanguage,
        affected_sections: list[str],
        platform: Platform | None = None,
        repair_applied: bool = False,
        prompt: str | None = None,
    ) -> str:
        sections = ", ".join(affected_sections) if affected_sections else "snapshot"
        seed = (
            f"{action.value}|{platform.value if platform else ''}|{sections}|"
            f"{prompt or ''}|{int(repair_applied)}"
        )
        repair_text_vi = (
            "Mình đã tinh chỉnh nhẹ lần cuối để câu chữ và định dạng nhất quán hơn."
            if repair_applied
            else "Kết quả đã hợp lệ ngay từ lần chạy đầu tiên."
        )
        repair_text_en = (
            "I applied one lightweight normalization pass to keep the output contract-safe."
            if repair_applied
            else "The output passed contract validation on the first pass."
        )

        if target_language == "vi":
            if action == ChatAction.FULL_REGENERATE:
                openings = [
                    "Mình đã làm mới toàn bộ nội dung theo yêu cầu mới của bạn.",
                    "Mình vừa tái tạo lại full pipeline để đồng bộ toàn bộ nội dung.",
                    "Đã regenerate toàn bộ output để bám sát prompt mới của bạn.",
                ]
                opening = openings[
                    ChatActionWorkflowService._stable_variant(seed, len(openings))
                ]
                return f"{opening} Phần cập nhật: {sections}. {repair_text_vi}"
            if action == ChatAction.REANALYZE_ONLY:
                openings = [
                    "Mình đã phân tích lại theo đúng yêu cầu của bạn.",
                    "Mình vừa chạy lại bước phân tích với prompt mới.",
                    "Đã re-analyze xong phần phân tích theo hướng bạn muốn.",
                ]
                opening = openings[
                    ChatActionWorkflowService._stable_variant(seed, len(openings))
                ]
                return (
                    f"{opening} Mình chỉ cập nhật phần analysis, các social post đang giữ nguyên. "
                    f"Phần thay đổi: {sections}. {repair_text_vi}"
                )
            if action == ChatAction.REWRITE_STRATEGY_ONLY:
                openings = [
                    "Mình đã cập nhật lại định hướng chiến lược.",
                    "Mình vừa chỉnh lại phần strategy theo yêu cầu mới.",
                    "Đã rewrite phần strategy để khớp mục tiêu bạn đưa ra.",
                ]
                opening = openings[
                    ChatActionWorkflowService._stable_variant(seed, len(openings))
                ]
                return (
                    f"{opening} Các bài social hiện tại vẫn được giữ nguyên. "
                    f"Phần thay đổi: {sections}. {repair_text_vi}"
                )
            platform_name = platform.value if platform is not None else "social"
            openings = [
                f"Mình đã viết lại bài {platform_name} theo đúng ý bạn.",
                f"Đã chỉnh lại bài {platform_name} theo prompt mới của bạn.",
                f"Mình vừa rewrite bài {platform_name} theo hướng bạn yêu cầu.",
            ]
            opening = openings[
                ChatActionWorkflowService._stable_variant(seed, len(openings))
            ]
            return (
                f"{opening} Mình chỉ cập nhật đúng bài bạn chọn, các phần còn lại giữ nguyên. "
                f"Phần thay đổi: {sections}. {repair_text_vi}"
            )

        if action == ChatAction.FULL_REGENERATE:
            openings = [
                "I regenerated the full pipeline based on your latest prompt.",
                "I refreshed the entire content output end-to-end.",
                "I reran full generation to align all sections with your new direction.",
            ]
            opening = openings[
                ChatActionWorkflowService._stable_variant(seed, len(openings))
            ]
            return f"{opening} Updated sections: {sections}. {repair_text_en}"
        if action == ChatAction.REANALYZE_ONLY:
            openings = [
                "I re-analyzed the source content using your latest prompt.",
                "I reran analysis based on your updated instruction.",
                "I refreshed the analysis section according to your request.",
            ]
            opening = openings[
                ChatActionWorkflowService._stable_variant(seed, len(openings))
            ]
            return (
                f"{opening} Only analysis was updated; existing social posts remain unchanged. "
                f"Updated section: {sections}. {repair_text_en}"
            )
        if action == ChatAction.REWRITE_STRATEGY_ONLY:
            openings = [
                "I updated the strategy direction based on your latest instruction.",
                "I refined the strategy layer while keeping your current posts intact.",
                "I rewrote the strategy section to match your requested angle.",
            ]
            opening = openings[
                ChatActionWorkflowService._stable_variant(seed, len(openings))
            ]
            return (
                f"{opening} Existing social posts were intentionally left unchanged. "
                f"Updated section: {sections}. {repair_text_en}"
            )
        platform_name = platform.value if platform is not None else "social"
        openings = [
            f"I rewrote the {platform_name} post based on your latest prompt.",
            f"I updated the {platform_name} post to match your instruction.",
            f"I refined the {platform_name} draft according to your new direction.",
        ]
        opening = openings[
            ChatActionWorkflowService._stable_variant(seed, len(openings))
        ]
        return (
            f"{opening} Only the targeted post was changed; the rest of the snapshot stays untouched. "
            f"Updated section: {sections}. {repair_text_en}"
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
        assistant_text = self._build_action_assistant_text(
            action=ChatAction.REANALYZE_ONLY,
            target_language=target_language,
            affected_sections=affected_sections,
            repair_applied=repair_applied,
            prompt=prompt,
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
        gateway = AgentContractGateway()
        validated_post, repair_applied = gateway.validate_social_post(
            rewritten,
            target_language=target_language,
            stage=f"chat_rewrite_{platform.value}_output",
            expected_platform=platform,
        )
        affected_sections = [f"social_posts.{platform.value}"]
        assistant_text = self._build_action_assistant_text(
            action=action,
            target_language=target_language,
            affected_sections=affected_sections,
            platform=platform,
            repair_applied=repair_applied,
            prompt=prompt,
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
        assistant_text = self._build_action_assistant_text(
            action=ChatAction.REWRITE_STRATEGY_ONLY,
            target_language=target_language,
            affected_sections=affected_sections,
            repair_applied=False,
            prompt=prompt,
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
                assistant_text=self._build_small_talk_reply(target_language),
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
                    assistant_text=self._build_action_assistant_text(
                        action=ChatAction.FULL_REGENERATE,
                        target_language=target_language,
                        affected_sections=affected_sections,
                        repair_applied=repair_applied,
                        prompt=prompt,
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
