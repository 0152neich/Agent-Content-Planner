from __future__ import annotations

from typing import Any, Optional, Union

from crewai import Crew, Process

from app.agents import (
    create_analyzer_agent,
    create_strategist_agent,
    create_copywriter_agent,
    create_editor_agent,
)
from app.tasks import (
    create_analyze_task,
    create_strategize_task,
    create_write_task,
    create_review_task,
)
from domain.models.models import ContentPlanOutput, DraftAnalysis, SocialPostsBundle
from shared.base import BaseModel, BaseService
from shared.logging import get_logger

logger = get_logger(__name__)


class ContentPlanningInput(BaseModel):
    url: str
    additional_context: Optional[str] = None


class ContentPlanningOutput(BaseModel):
    status: bool
    data: Optional[Union[ContentPlanOutput, Any]] = None
    error: Optional[str] = None


class ContentPlanningService(BaseService):
    @property
    def _analyzer_agent(self):
        return create_analyzer_agent()

    @property
    def _strategist_agent(self):
        return create_strategist_agent()

    @property
    def _copywriter_agent(self):
        return create_copywriter_agent()

    @property
    def _editor_agent(self):
        return create_editor_agent()

    def process(self, inputs: ContentPlanningInput) -> ContentPlanningOutput:
        try:
            # Instantiate agents
            analyzer_agent = self._analyzer_agent
            strategist_agent = self._strategist_agent
            copywriter_agent = self._copywriter_agent
            editor_agent = self._editor_agent

            # Create tasks
            analyze_task = create_analyze_task(analyzer_agent, inputs.url)
            strategize_task = create_strategize_task(strategist_agent)
            write_task = create_write_task(copywriter_agent)
            review_task = create_review_task(editor_agent)

            # Explicitly wire context chain
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

            crew_inputs = {
                "url": inputs.url,
                "additional_context": inputs.additional_context or "",
            }
            crew.kickoff(inputs=crew_inputs)

            # Assemble final structured output from individual task outputs
            analysis: DraftAnalysis = analyze_task.output.pydantic
            reviewed_posts: SocialPostsBundle = review_task.output.pydantic

            final_output = ContentPlanOutput(
                source_url=inputs.url,
                analysis=analysis,
                social_posts=reviewed_posts.posts,
            )

            return ContentPlanningOutput(status=True, data=final_output, error=None)

        except Exception as e:
            logger.exception("Content planning pipeline failed")
            return ContentPlanningOutput(status=False, data=None, error=str(e))
