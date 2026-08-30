import time
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_requests: int = 60, window_seconds: float = 60.0) -> None:
        super().__init__(app)
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._hits: list[float] = []

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        now = time.monotonic()
        cutoff = now - self._window_seconds
        hits = [t for t in self._hits if t > cutoff]
        self._hits = hits
        if len(hits) >= self._max_requests:
            return Response("Rate limit exceeded", status_code=429)
        self._hits.append(now)
        return await call_next(request)
