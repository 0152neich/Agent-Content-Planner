"""Shared pytest fixtures for Agent-Content-Planner tests."""

from __future__ import annotations

import pytest

from app.workflows.content_pipeline import ContentPlanningInput
from domain.models.models import (
    DraftAnalysis,
    FunnelStage,
    Platform,
    ReaderIntent,
    SocialPost,
    SocialPostsBundle,
    SupportingClaim,
)


@pytest.fixture
def sample_url() -> str:
    return "https://example.com/sample-article"


@pytest.fixture
def content_planning_input(sample_url: str) -> ContentPlanningInput:
    return ContentPlanningInput(url=sample_url, additional_context=None)


@pytest.fixture
def content_planning_input_with_context(sample_url: str) -> ContentPlanningInput:
    return ContentPlanningInput(
        url=sample_url,
        additional_context="Focus on B2B audience.",
    )


@pytest.fixture
def fake_draft_analysis() -> DraftAnalysis:
    return DraftAnalysis(
        core_message="Bài viết giải thích các thực hành tốt nhất cho lập kế hoạch nội dung.",
        value_proposition="Giúp đội ngũ biến quy trình lập kế hoạch phức tạp thành thực thi lặp lại.",
        reader_intent=ReaderIntent.LEARN,
        funnel_stage=FunnelStage.AWARENESS,
        target_audience="Đội marketing và quản lý nội dung",
        audience_pain_points=[
            "Ưu tiên giữa các kênh chưa rõ ràng.",
            "Chất lượng thông điệp chưa nhất quán.",
            "Thiếu thời gian cho lập kế hoạch chiến lược.",
        ],
        audience_desired_outcomes=[
            "Xây dựng thông điệp nhất quán đa kênh.",
            "Tăng tốc triển khai mà vẫn đảm bảo chất lượng.",
            "Đo lường kế hoạch chiến dịch rõ ràng hơn.",
        ],
        key_takeaways=[
            "Xác định mục tiêu rõ ràng trước khi tạo nội dung.",
            "Giữ giọng điệu nhất quán trên các nền tảng.",
            "Rà soát và tối ưu theo dữ liệu đo lường.",
        ],
        supporting_claims=[
            SupportingClaim(
                claim="Làm rõ mục tiêu giúp nâng chất lượng triển khai phía sau.",
                evidence_excerpt="Xác định mục tiêu rõ ràng trước khi tạo nội dung.",
                evidence_reason="Nguồn nhấn mạnh mối liên hệ trực tiếp giữa mục tiêu và chất lượng triển khai.",
            ),
            SupportingClaim(
                claim="Tính nhất quán đa nền tảng ảnh hưởng đến niềm tin thương hiệu.",
                evidence_excerpt="Giữ giọng điệu nhất quán trên các nền tảng.",
                evidence_reason="Nội dung liên kết rõ việc nhất quán thông điệp với hiệu quả đa kênh.",
            ),
            SupportingClaim(
                claim="Tối ưu dựa trên dữ liệu là điều kiện để cải thiện liên tục.",
                evidence_excerpt="Rà soát và tối ưu theo dữ liệu đo lường.",
                evidence_reason="Trích đoạn nêu rõ việc lặp cải tiến dựa trên đo lường.",
            ),
        ],
        tone_of_voice="Chuyên nghiệp và định hướng hành động",
        voice_guidelines=[
            "Dùng ngôn ngữ ngắn gọn, hướng hành động.",
            "Ưu tiên rõ ràng hơn thuật ngữ khó hiểu.",
            "Gắn khuyến nghị với kết quả có thể quan sát.",
        ],
        primary_cta="Bắt đầu bằng việc ghép một mục tiêu chiến dịch với một KPI đo được.",
        cta_reasoning="Bước khởi đầu cụ thể giúp đội ngũ áp dụng dễ hơn.",
        risk_flags=[
            "Có thể đơn giản hóa quá mức các ràng buộc theo từng kênh.",
            "Cần số liệu nền chiến dịch để định lượng mức cải thiện.",
        ],
        confidence_score=0.84,
        missing_information=["Bài viết chưa cung cấp benchmark cụ thể theo từng kênh."],
    )


@pytest.fixture
def fake_social_posts_bundle() -> SocialPostsBundle:
    return SocialPostsBundle(
        posts=[
            SocialPost(
                platform=Platform.LINKEDIN,
                hook="Bạn đã thử chuẩn hóa quy trình nội dung chưa?",
                body_content="Bài đăng ngắn gọn, chuyên nghiệp cho LinkedIn với trọng tâm vào tính nhất quán.",
                call_to_action="Đọc bài đầy đủ để áp dụng ngay.",
                hashtags=["contentstrategy", "marketing", "linkedin"],
            ),
            SocialPost(
                platform=Platform.FACEBOOK,
                hook="Mẹo nhanh cho đội nội dung của bạn:",
                body_content="Bài đăng thân thiện cho Facebook, khuyến khích thảo luận trong cộng đồng.",
                call_to_action="Chia sẻ nếu bạn thấy hữu ích.",
                hashtags=["contentplanning", "socialmedia", "tips"],
            ),
        ]
    )
