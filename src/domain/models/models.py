from enum import Enum
from typing import List, Optional

from pydantic import Field

from shared.base import BaseModel


class Platform(str, Enum):
    LINKEDIN = "linkedin"
    FACEBOOK = "facebook"


# 1. Input
class ContentInput(BaseModel):
    url: str = Field(
        ..., description="The URL of the original article/blog to be analyzed"
    )
    additional_context: Optional[str] = Field(
        None, description="Additional context from the user (if any)"
    )


# 2. Output of Analyzer Agent
class DraftAnalysis(BaseModel):
    core_message: str = Field(
        ..., description="The core message of the article (1 sentence)"
    )
    key_takeaways: List[str] = Field(..., description="List of 3-5 key takeaways")
    target_audience: str = Field(..., description="Description of the target audience")
    tone_of_voice: str = Field(
        ...,
        description="Tone of voice of the original article (e.g. Academic, Humorous, Formal...)",
    )


# 3. Output of Copywriter Agent for a specific post
class SocialPost(BaseModel):
    platform: Platform = Field(..., description="The social media platform to target")
    hook: str = Field(..., description="The hook of the post (e.g. 'Did you know?')")
    body_content: str = Field(
        ..., description="The main content of the post, segmented into paragraphs"
    )
    call_to_action: str = Field(
        ...,
        description="The call to action of the post (e.g. 'Click here to learn more')",
    )
    hashtags: List[str] = Field(
        ..., description="List of 3-5 hashtags suitable for the post"
    )


# 4. Bundle — output of write_task and review_task (all platforms in one pass)
class SocialPostsBundle(BaseModel):
    posts: List[SocialPost] = Field(
        ...,
        description="List of social media posts, one per platform (linkedin, facebook)",
    )


# 5. Final Deliverable
class ContentPlanOutput(BaseModel):
    source_url: str = Field(
        ..., description="The URL of the original article/blog that has been analyzed"
    )
    analysis: DraftAnalysis = Field(
        ..., description="The detailed analysis of the original article/blog"
    )
    social_posts: List[SocialPost] = Field(
        ..., description="List of posts optimized for each social media platform"
    )
