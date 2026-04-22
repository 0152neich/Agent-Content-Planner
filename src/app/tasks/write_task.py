from crewai import Agent, Task

from domain.models.models import SocialPostsBundle


def create_write_task(agent: Agent, target_language: str) -> Task:
    language_name = "Vietnamese" if target_language == "vi" else "English"
    return Task(
        description=(
            "Write social posts based on the approved analysis and strategy.\n\n"
            "Business objective:\n"
            "- Deliver conversion-oriented, channel-native content for BOTH platforms as micro-funnels.\n"
            "- Keep strategy alignment while adapting voice, structure, and framework per platform.\n\n"
            "Language policy:\n"
            f"- Output language is {language_name}.\n"
            "- Do not switch language.\n\n"
            "Framework rule (mandatory):\n"
            "- Follow the framework assigned by strategy for each platform.\n"
            "- If strategy signals pain/risk/time-loss intent, use PAS.\n"
            "- If strategy signals growth/opportunity/competitive-edge intent, use AIDA.\n\n"
            "Mandatory requirements:\n"
            "1. You must return EXACTLY 2 posts:\n"
            "   - One for platform='linkedin' (max 3000 characters).\n"
            "   - One for platform='facebook' (max 2000 characters).\n"
            "2. Each post must include:\n"
            "   - hook (thumb-stopping opener, max 2 lines, no generic greetings)\n"
            "   - body_content (must follow funnel logic in order: Agitation/Interest -> Solution/Value -> Proof)\n"
            "   - call_to_action (one single action only, specific and natural)\n"
            "   - hashtags (3-5 items, no '#' symbol in values)\n"
            "3. Funnel and proof quality:\n"
            "   - AGITATION/INTEREST must show cost of inaction.\n"
            "   - SOLUTION/VALUE must be practical and easy to scan (use bullets when useful).\n"
            "   - PROOF is mandatory: include at least one evidence point from analysis "
            "(supporting_claims/evidence_excerpt).\n"
            "4. Platform differentiation is mandatory:\n"
            "   - LinkedIn: professional, insight-led, short lines, limited emoji.\n"
            "   - Facebook: approachable, community-oriented, can use emoji as visual bullets.\n"
            "5. Must not violate quality gates:\n"
            "   - Do not copy-paste between platforms.\n"
            "   - Do not exceed character limits.\n"
            "   - Avoid AI cliches and generic filler.\n"
            "   - Never use cliches such as: 'In today's digital landscape', 'unlock', 'revolutionize', "
            "'trong boi canh so hien nay', 'dot pha toan dien'.\n"
            "6. Acceptance criteria:\n"
            "   - Output must be publish-ready and aligned to analysis + strategy context.\n"
            "   - Keep paragraphs under 3 sentences for scannability."
        ),
        expected_output=(
            "Return EXACTLY one JSON object:\n"
            "- posts: list containing EXACTLY 2 items.\n"
            "Each item must contain:\n"
            "- platform: 'linkedin' or 'facebook'\n"
            "- hook: string\n"
            "- body_content: string (must include Agitation/Interest, Solution/Value, and Proof)\n"
            "- call_to_action: string\n"
            "- hashtags: list[str] with 3-5 items (without '#')\n"
            "Additional constraints:\n"
            "- Hook must be <= 2 lines.\n"
            "- Exactly one CTA per post.\n"
            "- Proof is mandatory in each post.\n"
            f"Language requirement: hook/body_content/call_to_action must be {language_name}."
        ),
        agent=agent,
        output_pydantic=SocialPostsBundle,
    )
