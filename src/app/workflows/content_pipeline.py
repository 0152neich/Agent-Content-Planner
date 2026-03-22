from __future__ import annotations

from typing import Any, Optional, Union

from crewai import Crew, Process

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
from infra.tools.tools import UnsupportedModelError
from shared.base import BaseModel, BaseService
from shared.logging import get_logger
from shared.logging import redact_message

logger = get_logger(__name__)


class ContentPlanningInput(BaseModel):
    url: str
    additional_context: Optional[str] = None
    selected_model: Optional[str] = None


class ContentPlanningOutput(BaseModel):
    status: bool
    data: Optional[Union[ContentPlanOutput, Any]] = None
    error: Optional[str] = None
    code: int = 200


class ContentPlanningService(BaseService):
    def process(self, inputs: ContentPlanningInput) -> ContentPlanningOutput:
        try:
            selected_model = (inputs.selected_model or "").strip() or None

            analyzer_agent = create_analyzer_agent(model_override=selected_model)
            strategist_agent = create_strategist_agent(model_override=selected_model)
            copywriter_agent = create_copywriter_agent(model_override=selected_model)
            editor_agent = create_editor_agent(model_override=selected_model)

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
                verbose=True,
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
            return ContentPlanningOutput(
                status=True, data=final_output, error=None, code=200
            )
        except UnsupportedModelError as exc:
            logger.warning(
                "Unsupported model selected for content planning.", error=str(exc)
            )
            return ContentPlanningOutput(
                status=False,
                data=None,
                error=str(exc),
                code=400,
            )
        except Exception as exc:
            logger.exception("Content planning pipeline failed")
            return ContentPlanningOutput(
                status=False,
                data=None,
                error=redact_message(str(exc)),
                code=500,
            )
