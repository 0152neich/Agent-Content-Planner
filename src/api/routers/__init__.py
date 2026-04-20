from __future__ import annotations

from api.routers.auth import auth_router
from api.routers.conversation import conversation_router
from api.routers.content import content_plan_router
from api.routers.health import health_router
from api.routers.history import history_router
from api.routers.project import project_router
from api.routers.social_publish import social_publish_router
from api.routers.user import user_router

__all__ = [
    "auth_router",
    "project_router",
    "conversation_router",
    "history_router",
    "health_router",
    "content_plan_router",
    "social_publish_router",
    "user_router",
]
