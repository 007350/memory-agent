from collections.abc import Awaitable, Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware


class InMemoryMetrics:
    def __init__(self) -> None:
        self.requests = 0
        self.errors = 0
        self.lightrag_unavailable = 0

    def inc_request(self) -> None:
        self.requests += 1

    def inc_error(self) -> None:
        self.errors += 1

    def inc_unavailable(self) -> None:
        self.lightrag_unavailable += 1

    def record_health(self, status: str) -> None:
        self.last_lightrag_status = status

    def snapshot(self) -> dict[str, int | str]:
        return {
            "requests": self.requests,
            "errors": self.errors,
            "lightrag_unavailable": self.lightrag_unavailable,
            "last_lightrag_status": getattr(self, "last_lightrag_status", "unknown"),
        }


metrics = InMemoryMetrics()


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable]) -> object:
        metrics.inc_request()
        response = await call_next(request)
        if getattr(response, "status_code", 200) >= 500:
            metrics.inc_error()
        return response
