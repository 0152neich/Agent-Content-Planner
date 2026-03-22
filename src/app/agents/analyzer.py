from crewai import Agent

from infra.tools.tools import get_crewai_llm
from infra.tools.tools import get_scraper_tool


def create_analyzer_agent(model_override: str | None = None) -> Agent:
    return Agent(
        role="Chuyên viên Phân tích Dữ liệu",
        goal=(
            "Đọc và phân tích chuyên sâu nội dung từ một URL được cung cấp, "
            "sau đó trích xuất thông điệp cốt lõi, các điểm chính, "
            "đối tượng mục tiêu và giọng điệu của bài viết gốc."
        ),
        backstory=(
            "Bạn là một chuyên viên phân tích dữ liệu kỳ cựu với hơn 10 năm kinh nghiệm "
            "trong lĩnh vực nghiên cứu nội dung số. Bạn có khả năng đọc hiểu sâu, "
            "tổng hợp thông tin nhanh chóng và xác định chính xác thông điệp trọng tâm "
            "cùng đối tượng mục tiêu của bất kỳ bài viết nào. "
            "Kết quả phân tích của bạn luôn rõ ràng, có cấu trúc và đáng tin cậy."
        ),
        llm=get_crewai_llm(model_override=model_override),
        tools=[get_scraper_tool()],
        allow_delegation=False,
        verbose=True,
    )
