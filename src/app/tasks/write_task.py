from crewai import Agent, Task

from domain.models.models import SocialPostsBundle


def create_write_task(agent: Agent, target_language: str) -> Task:
    language_name = "Vietnamese" if target_language == "vi" else "English"
    return Task(
        description=(
            "Write social posts based on the approved analysis and strategy.\n\n"
            "Business objective:\n"
            "- Deliver conversion-oriented, channel-native content for BOTH platforms.\n"
            "- Keep strategy alignment while adapting voice and structure per platform.\n\n"
            "Language policy:\n"
            f"- Output language is {language_name}.\n"
            "- Do not switch language.\n\n"
            "Mandatory requirements:\n"
            "1. You must return EXACTLY 2 posts:\n"
            "   - One for platform='linkedin' (max 3000 characters).\n"
            "   - One for platform='facebook' (max 2000 characters).\n"
            "2. Each post must include:\n"
            "   - hook (1-2 sentences, thumb-stopping opener)\n"
            "   - body_content (clear paragraphs, practical value, easy to scan)\n"
            "   - call_to_action (specific and natural)\n"
            "   - hashtags (3-5 items, no '#' symbol in values)\n"
            "3. Platform differentiation is mandatory:\n"
            "   - LinkedIn: professional, insight-led, thought leadership style.\n"
            "   - Facebook: approachable, community-oriented, discussion-friendly style.\n"
            "4. Must not violate quality gates:\n"
            "   - Do not copy-paste between platforms.\n"
            "   - Do not exceed character limits.\n"
            "   - Do not use templated AI phrasing or generic filler.\n"
            "5. Acceptance criteria:\n"
            "   - Output must be publish-ready and aligned to analysis + strategy context."
        ),
        expected_output=(
            "Return EXACTLY one JSON object:\n"
            "- posts: list containing EXACTLY 2 items.\n"
            "Each item must contain:\n"
            "- platform: 'linkedin' or 'facebook'\n"
            "- hook: string\n"
            "- body_content: string\n"
            "- call_to_action: string\n"
            "- hashtags: list[str] with 3-5 items (without '#')\n"
            f"Language requirement: hook/body_content/call_to_action must be {language_name}."
        ),
        agent=agent,
        output_pydantic=SocialPostsBundle,
    )
