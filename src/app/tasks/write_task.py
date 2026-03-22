from crewai import Agent, Task

from domain.models.models import SocialPostsBundle


def create_write_task(agent: Agent) -> Task:
    return Task(
        description=(
            "Dựa trên chiến lược truyền thông và kết quả phân tích đã được cung cấp, "
            "sáng tạo bài đăng mạng xã hội hoàn chỉnh CHO TẤT CẢ các nền tảng được đề xuất.\n\n"
            "Yêu cầu cụ thể:\n"
            "1. Viết 2 bài đăng RIÊNG BIỆT cho 2 nền tảng:\n\n"
            "   📌 LINKEDIN (platform='linkedin', tối đa 3.000 ký tự):\n"
            "   - Giọng điệu chuyên nghiệp, thought leadership.\n"
            "   - Nội dung có chiều sâu, chia sẻ insight ngành.\n"
            "   - Hook mở đầu gây tò mò, tạo bối cảnh.\n\n"
            "   📌 FACEBOOK (platform='facebook', tối đa 2.000 ký tự):\n"
            "   - Giọng điệu gần gũi, thân thiện, dễ tiếp cận.\n"
            "   - Khuyến khích bình luận, thảo luận.\n"
            "   - Hook đơn giản, dễ hiểu với đại chúng.\n\n"
            "2. MỖI bài đăng phải có đầy đủ:\n"
            "   - Hook: Câu đầu tiên phải gây tò mò, bắt người dùng dừng lại scroll.\n"
            "   - Body content: Nội dung chính chia thành đoạn ngắn, dễ đọc, có giá trị thực.\n"
            "   - Call to action: Rõ ràng, tự nhiên, phù hợp với platform.\n"
            "   - Hashtags: 3-5 hashtag phù hợp và có lượng tìm kiếm tốt trên platform đó.\n\n"
            "3. TUYỆT ĐỐI KHÔNG:\n"
            "   - Dùng giọng văn máy móc, sáo rỗng ('In today's world...', 'It's important to...').\n"
            "   - Copy paste nội dung giữa 2 platform.\n"
            "   - Vượt quá giới hạn ký tự của từng platform."
        ),
        expected_output=(
            "Một JSON object với trường 'posts' là list chứa ĐÚNG 2 bài đăng:\n"
            "Mỗi bài đăng có cấu trúc:\n"
            "- platform: 'linkedin' hoặc 'facebook'\n"
            "- hook: string — Câu mở đầu thu hút (1-2 câu)\n"
            "- body_content: string — Nội dung chính (có thể có xuống dòng)\n"
            "- call_to_action: string — Lời kêu gọi hành động\n"
            "- hashtags: list of strings — 3-5 hashtags (không có dấu #)"
        ),
        agent=agent,
        output_pydantic=SocialPostsBundle,
    )
