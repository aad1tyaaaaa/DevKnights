"""Access control for deployments beyond a trusted local machine.

Scans are not yet owned by users, so this is a single shared access key, not per-user isolation:
it keeps an exposed backend from being read or used by anyone who finds it. Run without a key only
on a trusted machine or network.
"""

from __future__ import annotations

import hmac
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse

from app.core.config import settings

API_KEY_HEADER = "X-Provenyx-Key"
# Browsers navigate to these directly (no custom headers); they are protected by the OAuth state cookie.
KEY_EXEMPT_PATHS = {"/health", "/api/github/auth/login", "/api/github/auth/callback"}


def api_key_rejection(request: Request) -> JSONResponse | None:
    """401 response when an access key is configured and the request lacks it; None to let it through."""
    if settings.api_key is None or request.method == "OPTIONS" or request.url.path in KEY_EXEMPT_PATHS:
        return None
    supplied = request.headers.get(API_KEY_HEADER, "").encode()
    if hmac.compare_digest(supplied, settings.api_key.get_secret_value().encode()):
        return None
    return JSONResponse({"detail": f"A valid {API_KEY_HEADER} header is required"}, status_code=status.HTTP_401_UNAUTHORIZED)


class RateLimiter:
    """Sliding-window limit per client address for expensive submissions (scans, gate runs)."""

    # ponytail: in-process memory, so limits are per worker; use a shared store if the API runs replicated.
    def __init__(self, *, limit: int, window_seconds: float = 60.0) -> None:
        self.limit = limit
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, client: str) -> None:
        if self.limit <= 0:
            return
        now = time.monotonic()
        hits = self._hits[client]
        while hits and hits[0] <= now - self.window:
            hits.popleft()
        if len(hits) >= self.limit:
            retry_after = int(hits[0] + self.window - now) + 1
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                f"Too many submissions; try again in {retry_after} seconds",
                headers={"Retry-After": str(retry_after)},
            )
        hits.append(now)

    def reset(self) -> None:
        self._hits.clear()


submission_limiter = RateLimiter(limit=settings.submission_rate_limit_per_minute)


def limit_submissions(request: Request) -> None:
    submission_limiter.check(request.client.host if request.client else "unknown")
