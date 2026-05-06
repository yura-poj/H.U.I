from __future__ import annotations

import time
from collections import defaultdict, deque
from threading import Lock

from flask import current_app, jsonify, request


class FixedWindowRateLimiter:
    def __init__(self, max_requests: int, window_seconds: int, now=time.monotonic):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._now = now
        self._requests = defaultdict(deque)
        self._lock = Lock()

    def allow(self, key: str) -> tuple[bool, int]:
        if self.max_requests <= 0 or self.window_seconds <= 0:
            return True, 0

        now = self._now()
        cutoff = now - self.window_seconds

        with self._lock:
            timestamps = self._requests[key]
            while timestamps and timestamps[0] <= cutoff:
                timestamps.popleft()

            if len(timestamps) >= self.max_requests:
                retry_after = max(1, int(timestamps[0] + self.window_seconds - now))
                return False, retry_after

            timestamps.append(now)
            return True, 0


def get_client_ip() -> str:
    if current_app.config.get("TRUST_PROXY_HEADERS"):
        forwarded_for = request.headers.get("X-Forwarded-For", "")
        forwarded_ip = forwarded_for.split(",", 1)[0].strip()
        if forwarded_ip:
            return forwarded_ip

    return request.remote_addr or "unknown"


def configure_rate_limiting(app):
    limiter = FixedWindowRateLimiter(
        app.config.get("RATE_LIMIT_MAX_REQUESTS", 120),
        app.config.get("RATE_LIMIT_WINDOW_SECONDS", 60),
    )

    @app.before_request
    def enforce_rate_limit():
        if not app.config.get("RATE_LIMIT_ENABLED", True):
            return None

        if not request.path.startswith("/api/"):
            return None

        allowed, retry_after = limiter.allow(get_client_ip())
        if allowed:
            return None

        response = jsonify(
            {
                "error": "rate_limit_exceeded",
                "retry_after_seconds": retry_after,
            }
        )
        response.headers["Retry-After"] = str(retry_after)
        return response, 429

    return limiter
