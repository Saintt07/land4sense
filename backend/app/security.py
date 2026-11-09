import threading
import time
from collections import deque

from fastapi import HTTPException, Request

LIMIT = 10
WINDOW_S = 60.0

# shortcut: per-process memory, resets on restart, not shared across workers; switch to slowapi+Redis if >1 worker
_hits: dict[str, deque] = {}
_lock = threading.Lock()  # sync dependencies run in the threadpool


def rate_limit(request: Request) -> None:
    """Sliding-window limit per client IP. X-Forwarded-For is deliberately not trusted (spoofable); revisit behind a proxy (M9)."""
    ip = request.client.host if request.client else "unknown"
    now = time.monotonic()
    with _lock:
        for key in list(_hits):  # drop expired timestamps and empty entries so memory stays bounded
            q = _hits[key]
            while q and now - q[0] >= WINDOW_S:
                q.popleft()
            if not q:
                del _hits[key]
        q = _hits.setdefault(ip, deque())
        if len(q) >= LIMIT:
            raise HTTPException(429, f"Rate limit exceeded: {LIMIT} requests/minute")
        q.append(now)
