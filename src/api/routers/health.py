from __future__ import annotations

from fastapi import APIRouter

health_router = APIRouter(tags=["Health"])


@health_router.get("/health", summary="Health check")
async def health_check() -> dict:
    """Lightweight liveness probe for Docker / load-balancers."""
    return {"status": "ok", "message": "Server is running"}
