from crewai import Agent, Task

from domain.models.models import DraftAnalysis


def create_analyze_task(agent: Agent, url: str) -> Task:
    return Task(
        description=(
            f"Thực hiện phân tích chuyên sâu nội dung từ URL sau: {url}\n\n"
            "Yêu cầu cụ thể:\n"
            "1. Sử dụng công cụ scraper để đọc toàn bộ nội dung bài viết từ URL.\n"
            "2. Xác định và tóm tắt thông điệp cốt lõi của bài viết trong 1 câu duy nhất.\n"
            "3. Trích xuất từ 3 đến 5 điểm chính (key takeaways) quan trọng nhất. "
            "Mỗi điểm phải là 1 câu hoàn chỉnh, cụ thể, có thể dùng độc lập.\n"
            "4. Phân tích và mô tả đối tượng mục tiêu mà bài viết hướng đến.\n"
            "5. Nhận diện giọng điệu chủ đạo của bài viết gốc "
            "(ví dụ: Học thuật, Hài hước, Trang trọng, Truyền cảm hứng...).\n\n"
            "QUAN TRỌNG: Chỉ sử dụng thông tin có trong bài viết. "
            "KHÔNG suy đoán hay thêm nội dung ngoài bài viết gốc."
        ),
        expected_output=(
            "Một JSON object có cấu trúc chính xác với các trường sau:\n"
            "- core_message: string — Thông điệp cốt lõi tóm tắt trong 1 câu duy nhất.\n"
            "- key_takeaways: list of strings — Danh sách 3 đến 5 điểm chính, mỗi điểm là 1 câu hoàn chỉnh.\n"
            "- target_audience: string — Mô tả ngắn gọn đối tượng độc giả mục tiêu.\n"
            "- tone_of_voice: string — Giọng điệu của bài viết gốc (ví dụ: 'Học thuật và phân tích')."
        ),
        agent=agent,
        output_pydantic=DraftAnalysis,
    )
