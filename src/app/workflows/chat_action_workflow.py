from __future__ import annotations

from crewai import Agent, Crew, Process, Task
from pydantic import Field

from app.agents import (
    create_analyzer_agent,
    create_copywriter_agent,
    create_strategist_agent,
)
from app.services.chat_contracts import ChatAction
from app.workflows.chat_snapshot import ContentPlanSnapshot, SnapshotPatch
from app.workflows.content_pipeline import ContentPlanningInput, ContentPlanningService
from app.tasks import create_analyze_task
from domain.models.models import ContentPlanOutput, DraftAnalysis, Platform, SocialPost
from infra.tools.tools import get_crewai_llm
from shared.base import BaseModel
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


class ChatActionWorkflowOutput(BaseModel):
    status: bool
    assistant_text: str
    patch: SnapshotPatch = Field(default_factory=SnapshotPatch)
    affected_sections: list[str] = Field(default_factory=list)
    error: str | None = None
    code: int = 200


class _StrategyOutput(BaseModel):
    strategy: str


class _ChatReplyOutput(BaseModel):
    reply: str


class ChatActionWorkflowService(BaseModel):
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

    def _build_single_post_task(
        self,
        *,
        agent: Agent,
        platform: Platform,
        prompt: str,
        snapshot: ContentPlanSnapshot,
        existing_post: SocialPost | None,
    ) -> Task:
        char_limit = 2000 if platform == Platform.FACEBOOK else 3000
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
                f"- Audience: {snapshot.analysis.target_audience}\n"
                f"- Tone: {snapshot.analysis.tone_of_voice}\n"
                f"Current {platform.value} post:\n{existing_text}\n"
                f"Character limit: {char_limit}\n"
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
        selected_model: str | None,
        crew_settings: CrewSettings,
    ) -> ChatActionWorkflowOutput:
        analyzer = create_analyzer_agent(
            model_override=selected_model,
            crew_settings=crew_settings,
        )
        analyze_task = create_analyze_task(analyzer, source_url)
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
        return ChatActionWorkflowOutput(
            status=True,
            assistant_text="Done. I re-analyzed the source URL and updated Analysis.",
            patch=SnapshotPatch(analysis=analysis),
            affected_sections=["analysis"],
            code=200,
        )

    def _run_rewrite_post_only(
        self,
        *,
        platform: Platform,
        prompt: str,
        selected_model: str | None,
        snapshot: ContentPlanSnapshot,
        crew_settings: CrewSettings,
    ) -> ChatActionWorkflowOutput:
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
        return ChatActionWorkflowOutput(
            status=True,
            assistant_text=f"Done. I updated the {platform.value} post.",
            patch=SnapshotPatch(social_post=rewritten),
            affected_sections=[f"social_posts.{platform.value}"],
            code=200,
        )

    def _run_rewrite_strategy_only(
        self,
        *,
        prompt: str,
        selected_model: str | None,
        snapshot: ContentPlanSnapshot,
        crew_settings: CrewSettings,
    ) -> ChatActionWorkflowOutput:
        strategist = create_strategist_agent(
            model_override=selected_model,
            crew_settings=crew_settings,
        )
        task = Task(
            description=(
                "Create strategy direction only. Do not rewrite social posts.\n"
                f"User request: {prompt}\n"
                f"Core message: {snapshot.analysis.core_message}\n"
                f"Audience: {snapshot.analysis.target_audience}\n"
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
        return ChatActionWorkflowOutput(
            status=True,
            assistant_text="Done. I updated the strategy in metadata.",
            patch=SnapshotPatch(strategy=strategy_output.strategy),
            affected_sections=["meta.strategy"],
            code=200,
        )

    def _run_general_qa(
        self,
        *,
        prompt: str,
        selected_model: str | None,
        snapshot: ContentPlanSnapshot | None,
    ) -> ChatActionWorkflowOutput:
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
            f"Audience: {snapshot.analysis.target_audience}\n"
            if snapshot is not None
            else "No snapshot available."
        )
        task = Task(
            description=(
                "Reply naturally as a friendly chatbot and keep snapshot unchanged.\n"
                "Use the same language as the user (Vietnamese or English).\n"
                "Keep answer concise (2-4 sentences) unless user asks for more detail.\n"
                "Do not dump raw fields like 'Core:' or 'Audience:' unless user explicitly asks.\n"
                "If useful, integrate snapshot context smoothly into a normal sentence.\n"
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
        return ChatActionWorkflowOutput(
            status=True,
            assistant_text=reply_output.reply,
            patch=SnapshotPatch(),
            affected_sections=[],
            code=200,
        )

    def process(self, inputs: ChatActionWorkflowInput) -> ChatActionWorkflowOutput:
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
                return ChatActionWorkflowOutput(
                    status=True,
                    assistant_text="Done. I regenerated analysis and social posts.",
                    patch=SnapshotPatch(full_snapshot=snapshot),
                    affected_sections=["analysis", "social_posts"],
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
                    selected_model=selected_model,
                    snapshot=inputs.snapshot,
                    crew_settings=crew_settings,
                )

            return self._run_general_qa(
                prompt=prompt,
                selected_model=selected_model,
                snapshot=inputs.snapshot,
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
            )
        except ScraperToolError as exc:
            logger.warning("chat_action_scraper_failed", error=redact_message(str(exc)))
            return ChatActionWorkflowOutput(
                status=False,
                assistant_text="",
                error=redact_message(str(exc)),
                code=502,
            )
        except Exception as exc:
            logger.exception(
                "chat_action_workflow_failed", error=redact_message(str(exc))
            )
            error_code = self._classify_runtime_error_code(exc)
            return ChatActionWorkflowOutput(
                status=False,
                assistant_text="",
                error=redact_message(str(exc)),
                code=error_code,
            )
