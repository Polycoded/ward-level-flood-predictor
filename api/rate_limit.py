"""Small in-memory sliding-window rate limiter for public endpoints.

Process-local by design: it protects a single API instance from accidental
request storms. A shared store (Redis) is the production upgrade path.
"""

from __future__ import annotations

import threading
import time
from collections import deque

from api.settings import settings


class RateLimiter:
    def __init__(self, limit: int, window_seconds: float = 60.0) -> None:
        self.limit = max(1, int(limit))
        self.window = float(window_seconds)
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        cutoff = now - self.window
        with self._lock:
            bucket = self._hits.setdefault(key, deque())
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            if len(bucket) >= self.limit:
                return False
            bucket.append(now)
            # Bound memory if many distinct clients appear.
            if len(self._hits) > 10_000:
                for stale in [k for k, v in self._hits.items() if not v or v[-1] < cutoff]:
                    self._hits.pop(stale, None)
            return True

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


subscription_limiter = RateLimiter(settings.subscription_rate_limit_per_minute)
webhook_limiter = RateLimiter(settings.webhook_rate_limit_per_minute)


def client_key(request) -> str:
    """Best-effort client identity without trusting spoofable headers."""
    if request.client and request.client.host:
        return request.client.host
    return "unknown"
