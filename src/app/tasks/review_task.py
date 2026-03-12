from crewai import Agent, Task

from domain.models.models import SocialPostsBundle


def create_review_task(agent: Agent) -> Task:
    return Task(
        description=(
            "Rà soát và kiểm duyệt chất lượng toàn bộ bài đăng mạng xã hội "
            "đã được Copywriter soạn thảo.\n\n"
            "Tiêu chí đánh giá BẮT BUỘC:\n"
            "1. ✅ Chính tả & Ngữ pháp: Không chấp nhận bất kỳ lỗi nào.\n"
            "2. ✅ Độ dài phù hợp từng nền tảng:\n"
            "   - LinkedIn: Tối đa 3.000 ký tự.\n"
            "   - Facebook: Tối đa 2.000 ký tự để đảm bảo hiển thị tối ưu.\n"
            "3. ✅ Phát hiện & Loại bỏ 'AI Tone' — các dấu hiệu bao gồm:\n"
            "   - Cụm từ sáo rỗng: 'In today\\'s world', 'It\\'s important to', 'As an AI...'.\n"
            "   - Cấu trúc câu rập khuôn, thiếu cá tính và cảm xúc tự nhiên.\n"
            "   - Giọng văn quá hoàn hảo, thiếu lỗi nhỏ bình thường của con người.\n"
            "4. ✅ Tính nhất quán: Nội dung phải phù hợp với phân tích và chiến lược ban đầu.\n"
            "5. ✅ Platform differentiation: 2 bài LinkedIn và Facebook phải khác nhau rõ rệt "
            "về giọng điệu và cách tiếp cận.\n\n"
            "QUY TRÌNH:\n"
            "- Nếu bài đăng ĐẠT chuẩn: Trả về nguyên bài đăng đã được chỉnh sửa nhỏ (nếu có).\n"
            "- Nếu bài đăng CHƯA đạt: Tự sửa trực tiếp và trả về bản đã hoàn chỉnh. "
            "KHÔNG yêu cầu viết lại từ đầu."
        ),
        expected_output=(
            "Một JSON object với trường 'posts' là list chứa ĐÚNG 2 bài đăng đã qua kiểm duyệt:\n"
            "Mỗi bài đăng có cấu trúc:\n"
            "- platform: 'linkedin' hoặc 'facebook'\n"
            "- hook: string — Câu mở đầu thu hút đã kiểm duyệt\n"
            "- body_content: string — Nội dung chính đã kiểm duyệt\n"
            "- call_to_action: string — Lời kêu gọi hành động đã kiểm duyệt\n"
            "- hashtags: list of strings — 3-5 hashtags đã kiểm duyệt"
        ),
        agent=agent,
        output_pydantic=SocialPostsBundle,
    )
