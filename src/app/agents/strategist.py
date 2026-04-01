from __future__ import annotations

from crewai import Agent

from infra.tools.tools import get_crewai_llm
from shared.settings import Settings
from shared.settings.models import CrewSettings


def create_strategist_agent(
    model_override: str | None = None,
    *,
    crew_settings: CrewSettings | None = None,
) -> Agent:
    c = crew_settings or Settings().crew
    return Agent(
        role="Giám đốc Chiến lược Truyền thông",
        goal=(
            "Dựa trên kết quả phân tích bài viết gốc, xây dựng chiến lược nội dung "
            "đa nền tảng (LinkedIn, Facebook) với góc tiếp cận phù hợp cho "
            "từng kênh truyền thông, đảm bảo tối ưu hóa tương tác và tiếp cận đúng đối tượng."
        ),
        backstory=(
            "Bạn là một Giám đốc Chiến lược Truyền thông với bề dày kinh nghiệm "
            "trong việc xây dựng chiến lược nội dung cho các thương hiệu lớn. "
            "Bạn hiểu rõ đặc thù của từng nền tảng mạng xã hội — từ giọng điệu chuyên nghiệp "
            "trên LinkedIn đến tính lan truyền và kết nối cộng đồng trên Facebook. "
            "Bạn luôn đưa ra chiến lược rõ ràng, có tính ứng dụng cao, phù hợp xu hướng thị trường, "
            "và đủ cụ thể để Copywriter có thể thực thi ngay mà không cần hỏi thêm."
        ),
        llm=get_crewai_llm(model_override=model_override),
        tools=[],
        allow_delegation=False,
        verbose=c.verbose,
        max_iter=c.max_iter_llm_only,
        max_retry_limit=c.max_retry_limit,
    )
