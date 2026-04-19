from crewai import Agent, Task

from domain.models.models import SocialPostsBundle


def create_review_task(agent: Agent, target_language: str) -> Task:
    language_name = "Vietnamese" if target_language == "vi" else "English"
    return Task(
        description=(
            "Review and finalize copywriter outputs under strict QA SOP.\n\n"
            "Language policy:\n"
            f"- Finalized content must remain in {language_name}.\n"
            "- Do not switch language.\n\n"
            "Hard quality gates (must pass all):\n"
            "1. Language correctness:\n"
            "   - No spelling or grammar errors.\n"
            "2. Platform character limits:\n"
            "   - LinkedIn <= 3000 characters.\n"
            "   - Facebook <= 2000 characters.\n"
            "3. Anti-generic writing quality:\n"
            "   - Remove templated AI-like phrasing and empty filler.\n"
            "   - Keep wording natural, specific, and audience-relevant.\n"
            "4. Strategy and analysis alignment:\n"
            "   - Message, tone, and CTA must stay aligned with approved strategy.\n"
            "5. Platform differentiation:\n"
            "   - LinkedIn and Facebook versions must be clearly distinct in angle and voice.\n\n"
            "Execution rule:\n"
            "- If any gate fails, you must fix inline and return the final corrected output.\n"
            "- Do not request a full rewrite loop.\n"
            "- Return only the final publish-ready JSON bundle."
        ),
        expected_output=(
            "Return EXACTLY one JSON object:\n"
            "- posts: list containing EXACTLY 2 reviewed posts.\n"
            "Each post must contain:\n"
            "- platform: 'linkedin' or 'facebook'\n"
            "- hook: string\n"
            "- body_content: string\n"
            "- call_to_action: string\n"
            "- hashtags: list[str] with 3-5 items\n"
            f"Language requirement: hook/body_content/call_to_action must be {language_name}."
        ),
        agent=agent,
        output_pydantic=SocialPostsBundle,
    )
