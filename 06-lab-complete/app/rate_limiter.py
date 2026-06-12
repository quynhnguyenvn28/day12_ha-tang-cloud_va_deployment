"""
Rate Limiter — Sliding Window Algorithm (Day 12 Lab)

Limits requests per user per minute.
Uses in-memory storage (deque) for simplicity;
in a real multi-instance deployment, use Redis.
"""
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

from app.config import settings

# ─────────────────────────────────────────────────────────
# In-memory sliding window store
# key  → deque of timestamps (unix seconds)
# ─────────────────────────────────────────────────────────
_windows: dict[str, deque] = defaultdict(deque)

WINDOW_SECONDS = 60


def check_rate_limit(key: str) -> None:
    """
    Sliding window rate limiter.

    Args:
        key: Unique identifier for the caller (e.g. truncated API key).

    Raises:
        HTTPException 429 if the caller has exceeded
        settings.rate_limit_per_minute requests in the last 60 seconds.
    """
    now = time.time()
    window = _windows[key]

    # Evict timestamps outside the window
    while window and window[0] < now - WINDOW_SECONDS:
        window.popleft()

    if len(window) >= settings.rate_limit_per_minute:
        retry_after = int(WINDOW_SECONDS - (now - window[0]))
        raise HTTPException(
            status_code=429,
            detail=(
                f"Rate limit exceeded: {settings.rate_limit_per_minute} "
                f"req/{WINDOW_SECONDS}s. Retry after {retry_after}s."
            ),
            headers={"Retry-After": str(retry_after)},
        )

    window.append(now)


def rate_limit_dependency(request: Request, x_api_key: str = None) -> None:
    """
    FastAPI dependency wrapper for check_rate_limit.
    Extracts a bucket key from the request (first 8 chars of API key or IP).
    """
    api_key = request.headers.get("X-API-Key", "")
    bucket = api_key[:8] if api_key else str(request.client.host if request.client else "unknown")
    check_rate_limit(bucket)
