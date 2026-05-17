from crewai import Agent, Task


def create_strategize_task(agent: Agent, target_language: str) -> Task:
    language_name = "Vietnamese" if target_language == "vi" else "English"
    return Task(
        description=(
            "Using analyzer output, produce a strict SOP strategy brief for LinkedIn and "
            "Facebook that is directly executable by copywriting.\n\n"
            "Language policy:\n"
            f"- Strategy text must be {language_name}.\n"
            "- Do not switch language.\n\n"
            "Framework assignment rule (mandatory):\n"
            "- If intent indicates pain/risk/time-loss urgency, assign PAS.\n"
            "- If intent indicates growth/opportunity/competitive-advantage, assign AIDA.\n"
            "- You must explicitly assign one framework per platform and explain why.\n\n"
            "You must explicitly use these analysis fields:\n"
            "- core_message\n"
            "- value_proposition\n"
            "- reader_intent\n"
            "- funnel_stage\n"
            "- target_audience\n"
            "- audience_pain_points\n"
            "- audience_desired_outcomes\n"
            "- tone_of_voice\n"
            "- primary_cta\n"
            "- cta_reasoning\n"
            "- risk_flags\n\n"
            "Quality gates and acceptance criteria:\n"
            "1. Platform differentiation is mandatory:\n"
            "   - LinkedIn: professional thought leadership, insight-heavy.\n"
            "   - Facebook: community-friendly, conversation-driven.\n"
            "2. Keep one shared strategic message but adapt angle and CTA style per channel.\n"
            "3. Include engagement ideas aligned to reader_intent and funnel_stage.\n"
            "4. Include concrete risk mitigation from risk_flags.\n"
            "5. Keep recommendations implementable with no follow-up clarifications.\n"
            "6. Keep the brief concise, structured, and decision-ready.\n"
            "7. Ensure framework guidance is directly reusable by the copywriter task."
        ),
        expected_output=(
            "A practical strategy brief in plain text with EXACTLY two sections:\n"
            "1) LinkedIn Strategy\n"
            "2) Facebook Strategy\n"
            "Each section must include these labeled lines:\n"
            "- Framework: PAS or AIDA\n"
            "- Framework rationale:\n"
            "- Angle:\n"
            "- Tone:\n"
            "- Core message:\n"
            "- CTA direction:\n"
            "- Engagement tips:\n"
            "- Risk mitigation:\n"
            "- Character limit:\n"
            f"All section content must be {language_name}."
        ),
        agent=agent,
    )
