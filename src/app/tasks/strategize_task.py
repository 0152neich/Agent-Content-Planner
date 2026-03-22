from crewai import Agent, Task


def create_strategize_task(agent: Agent) -> Task:
    return Task(
        description=(
            "Dựa trên kết quả phân tích bài viết gốc từ bước trước, "
            "xây dựng chiến lược nội dung đa nền tảng chi tiết.\n\n"
            "Yêu cầu cụ thể:\n"
            "1. Đề xuất góc tiếp cận (angle) riêng biệt và phù hợp cho từng nền tảng:\n"
            "   - LinkedIn: Góc nhìn chuyên nghiệp, chia sẻ insight ngành, thought leadership. "
            "Độc giả là professionals, nhà quản lý, người đi làm. Giới hạn 3.000 ký tự.\n"
            "   - Facebook: Gần gũi, dễ tiếp cận, khuyến khích thảo luận cộng đồng. "
            "Độc giả đa dạng hơn. Giới hạn 2.000 ký tự để hiển thị tối ưu.\n"
            "2. Xác định thông điệp chủ đạo xuyên suốt tất cả các nền tảng.\n"
            "3. Đề xuất giọng điệu và phong cách viết phù hợp cho từng kênh.\n"
            "4. Gợi ý các yếu tố tăng tương tác (câu hỏi mở, số liệu gây tò mò, CTA phù hợp).\n\n"
            "LƯU Ý: Chiến lược này sẽ được dùng làm nền tảng cho bước viết nội dung tiếp theo. "
            "Hãy đảm bảo đủ cụ thể để Copywriter có thể thực thi ngay."
        ),
        expected_output=(
            "Một bản chiến lược truyền thông rõ ràng CHO 2 nền tảng (LinkedIn và Facebook), "
            "mỗi nền tảng bao gồm:\n"
            "- angle: Góc tiếp cận riêng biệt cho platform đó\n"
            "- tone: Giọng điệu và phong cách viết\n"
            "- core_message: Thông điệp chính cần truyền tải\n"
            "- engagement_tips: Gợi ý tăng tương tác (câu hỏi, CTA, số liệu gây tò mò)\n"
            "- char_limit: Giới hạn ký tự tối đa cho platform"
        ),
        agent=agent,
    )
