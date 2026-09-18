"""
Module 12: In-memory sliding-window rate limiter.
Structured so the storage backend (currently a dict) can be swapped for Redis later.
"""
import time
import logging
from collections import deque
from threading import Lock
from typing import Deque, Dict, Tuple

from fastapi import HTTPException, Request, status

from app.core.config import settings

logger = logging.getLogger(__name__)

# Storage: key -> deque of timestamps (epoch floats)
_store: Dict[str, Deque[float]] = {}
_lock = Lock()


def _is_allowed(key: str, max_requests: int, window_seconds: int) -> Tuple[bool, int]:
    """
    Sliding-window check.
    Returns (allowed, remaining_requests).
    Thread-safe via a module-level lock.
    """
    now = time.monotonic()
    cutoff = now - window_seconds

    with _lock:
        if key not in _store:
            _store[key] = deque()
        dq = _store[key]

        # Evict timestamps outside the window
        while dq and dq[0] < cutoff:
            dq.popleft()

        count = len(dq)
        if count >= max_requests:
            return False, 0

        dq.append(now)
        return True, max_requests - count - 1


def check_rate_limit(key: str, max_requests: int, window_seconds: int) -> None:
    """
    Raises HTTP 429 if the key has exceeded max_requests within window_seconds.
    No-op when RATE_LIMIT_ENABLED is False.
    """
    if not settings.RATE_LIMIT_ENABLED:
        return

    allowed, remaining = _is_allowed(key, max_requests, window_seconds)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Please wait before sending more requests.",
            headers={"Retry-After": str(window_seconds)},
        )


def check_authenticated_limit(user_id: str) -> None:
    """Standard per-user API rate limit."""
    check_rate_limit(
        f"user:{user_id}",
        settings.RATE_LIMIT_REQUESTS,
        settings.RATE_LIMIT_WINDOW_SECONDS,
    )


def check_ai_limit(user_id: str) -> None:
    """Per-user AI request rate limit (stricter, longer window)."""
    check_rate_limit(
        f"ai:{user_id}",
        settings.RATE_LIMIT_AI_REQUESTS,
        settings.RATE_LIMIT_AI_WINDOW_SECONDS,
    )


def check_public_chatbot_limit(session_id: str) -> None:
    """Per-visitor-session public chatbot rate limit."""
    check_rate_limit(
        f"pub:{session_id}",
        settings.RATE_LIMIT_PUBLIC_REQUESTS,
        settings.RATE_LIMIT_PUBLIC_WINDOW_SECONDS,
    )


def reset_for_testing(key: str) -> None:
    """Test helper: clear rate-limit state for a specific key."""
    with _lock:
        _store.pop(key, None)
