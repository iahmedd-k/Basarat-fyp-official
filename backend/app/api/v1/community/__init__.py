from app.api.v1.community.posts import router as posts_router
from app.api.v1.community.comments import router as comments_router
from app.api.v1.community.follows import router as follows_router
from app.api.v1.community.profile import router as profile_router
from app.api.v1.community.notifications import router as notifications_router

__all__ = [
    "posts_router",
    "comments_router",
    "follows_router",
    "profile_router",
    "notifications_router",
]