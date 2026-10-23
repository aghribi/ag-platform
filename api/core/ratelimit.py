"""
Lightweight in-memory IP-based rate limiter.

Uses a sliding-window counter per (IP, endpoint) key. Counters are per process:
with WEB_CONCURRENCY workers the effective limit is that many times higher.
"""
import time
from collections import defaultdict
from fastapi import HTTPException, Request, status


# key → list of request timestamps (pruned to window)
_counters: dict[str, list[float]] = defaultdict(list)


def _check(key: str, limit: int, window_seconds: int) -> None:
    now = time.monotonic()
    cutoff = now - window_seconds
    bucket = _counters[key]
    # Prune timestamps outside the window
    while bucket and bucket[0] < cutoff:
        bucket.pop(0)
    if len(bucket) >= limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many requests. Max {limit} per {window_seconds}s.",
            headers={"Retry-After": str(window_seconds)},
        )
    bucket.append(now)


def rate_limit(limit: int, window_seconds: int = 60, endpoint: str = ""):
    """
    FastAPI dependency factory. Raises HTTP 429 when IP exceeds *limit*
    requests within *window_seconds*.

    Usage::
        @router.post("/login", dependencies=[Depends(rate_limit(5, 60, "login"))])
    """
    async def _dependency(request: Request) -> None:
        ip = request.client.host if request.client else "unknown"
        key = f"{ip}:{endpoint or request.url.path}"
        _check(key, limit, window_seconds)

    return _dependency
