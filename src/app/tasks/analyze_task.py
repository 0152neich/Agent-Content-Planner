from crewai import Agent, Task

from domain.models.models import DraftAnalysis


def create_analyze_task(agent: Agent, url: str, target_language: str) -> Task:
    language_name = "Vietnamese" if target_language == "vi" else "English"
    return Task(
        description=(
            f"Analyze the blog content from URL: {url}\n\n"
            "Additional context from current chat session:\n"
            "{additional_context}\n\n"
            "Business objective:\n"
            "- Produce Marketing Ops analysis that is decision-ready for social campaigns.\n"
            "- Follow evidence-only mode: each strong claim must be backed by explicit source evidence.\n\n"
            "Language policy:\n"
            f"- Output language for all textual fields is {language_name}.\n"
            "- Do not switch to another language.\n"
            "- Keep enum-like fields unchanged: reader_intent, funnel_stage.\n\n"
            "Mandatory SOP workflow:\n"
            "1. Use scraper tool to read the source article content.\n"
            "2. Build a complete analysis object for content strategy and social conversion.\n"
            "3. For each supporting_claim, provide:\n"
            "   - claim\n"
            "   - evidence_excerpt (quoted or near-quoted from source)\n"
            "   - evidence_reason\n"
            "4. If evidence is insufficient, do not infer unsupported facts.\n"
            "   Put unknowns into missing_information.\n"
            "5. Keep list sizes strict for readability:\n"
            "   - key_takeaways: 3-5\n"
            "   - audience_pain_points: 3-5\n"
            "   - audience_desired_outcomes: 3-5\n"
            "   - supporting_claims: 3-5\n"
            "   - voice_guidelines: 3-5\n"
            "   - risk_flags: 2-4\n\n"
            "Quality gates and acceptance criteria:\n"
            "- Do not add unsupported market stats.\n"
            "- No evidence means no conclusion: move it to missing_information.\n"
            "- Prioritize conversion-oriented insights: audience intent, value proposition, CTA, risk.\n"
            "- confidence_score must be in range [0, 1]."
        ),
        expected_output=(
            "Return EXACTLY one JSON object matching this schema:\n"
            "- core_message: string\n"
            "- value_proposition: string\n"
            "- reader_intent: one of ['learn', 'evaluate', 'act']\n"
            "- funnel_stage: one of ['awareness', 'consideration', 'decision']\n"
            "- target_audience: string\n"
            "- audience_pain_points: list[str] (3-5)\n"
            "- audience_desired_outcomes: list[str] (3-5)\n"
            "- key_takeaways: list[str] (3-5)\n"
            "- supporting_claims: list[object] (3-5), each object contains:\n"
            "  - claim: string\n"
            "  - evidence_excerpt: string\n"
            "  - evidence_reason: string\n"
            "- tone_of_voice: string\n"
            "- voice_guidelines: list[str] (3-5)\n"
            "- primary_cta: string\n"
            "- cta_reasoning: string\n"
            "- risk_flags: list[str] (2-4)\n"
            "- confidence_score: float in [0, 1]\n"
            "- missing_information: list[str]\n"
            f"Language requirement: all textual values above must be {language_name} "
            "(except enum values and technical keys)."
        ),
        agent=agent,
        output_pydantic=DraftAnalysis,
    )
