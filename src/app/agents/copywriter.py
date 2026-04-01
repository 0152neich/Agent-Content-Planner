from __future__ import annotations

from crewai import Agent

from infra.tools.tools import get_crewai_llm
from shared.settings import Settings
from shared.settings.models import CrewSettings


def create_copywriter_agent(
    model_override: str | None = None,
    *,
    crew_settings: CrewSettings | None = None,
) -> Agent:
    c = crew_settings or Settings().crew
    return Agent(
        role="Chuyên gia Viết bài (Senior Copywriter)",
        goal=(
            "Sáng tạo nội dung bài đăng mạng xã hội hấp dẫn, chuyên nghiệp dựa trên "
            "chiến lược truyền thông và kết quả phân tích đã cung cấp. "
            "Bài viết phải có hook thu hút, nội dung giá trị và lời kêu gọi hành động rõ ràng."
        ),
        backstory=(
            "Bạn là một Senior Copywriter với khả năng viết nội dung xuất sắc cho mọi nền tảng "
            "mạng xã hội. Bạn thành thạo nghệ thuật storytelling, biết cách tạo hook gây tò mò, "
            "truyền tải thông điệp súc tích và thúc đẩy hành động từ người đọc. "
            "Phong cách viết của bạn luôn tự nhiên, có chiều sâu và tránh hoàn toàn giọng văn "
            "máy móc hay rập khuôn của AI."
        ),
        llm=get_crewai_llm(model_override=model_override),
        tools=[],
        allow_delegation=False,
        verbose=c.verbose,
        max_iter=c.max_iter_llm_only,
        max_retry_limit=c.max_retry_limit,
    )
