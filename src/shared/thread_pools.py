"""Thread pools for asyncio.run_in_executor.

Long-running CrewAI / LLM work must not share the same pool as short DB/auth handlers:
the default executor is small; a few stuck LLM retries can starve every other API call.
"""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor

import asyncio

_io_pool: ThreadPoolExecutor | None = None
_crew_pool: ThreadPoolExecutor | None = None


def install_default_executors(loop: asyncio.AbstractEventLoop) -> None:
    """Larger default pool for I/O-bound sync services; separate pool for CrewAI."""
    global _io_pool, _crew_pool
    if _io_pool is not None:
        return

    io_workers = max(8, int(os.getenv("API_IO_THREAD_POOL_SIZE", "32")))
    crew_workers = max(1, int(os.getenv("CREW_THREAD_POOL_SIZE", "3")))

    _io_pool = ThreadPoolExecutor(max_workers=io_workers, thread_name_prefix="api_io")
    _crew_pool = ThreadPoolExecutor(
        max_workers=crew_workers, thread_name_prefix="crewai"
    )
    loop.set_default_executor(_io_pool)


def get_crew_executor() -> ThreadPoolExecutor:
    """Executor for content pipeline only — isolated from auth/projects/conversation routes."""
    if _crew_pool is None:
        raise RuntimeError(
            "Crew thread pool not initialized. Ensure FastAPI lifespan calls "
            "install_default_executors()."
        )
    return _crew_pool


def shutdown_executors() -> None:
    global _io_pool, _crew_pool
    if _crew_pool is not None:
        _crew_pool.shutdown(wait=True)
        _crew_pool = None
    if _io_pool is not None:
        _io_pool.shutdown(wait=True)
        _io_pool = None
