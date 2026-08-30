import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable]) -> object:
        request.state.request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        start = time.monotonic()
        response = None
        try:
            response = await call_next(request)
            return response
        finally:
            latency = time.monotonic() - start
            print(
                f"request_id={request.state.request_id} method={request.method} path={request.url.path} "
                f"status={getattr(response, 'status_code', 'err')} latency_ms={latency * 1000:.1f}"
            )
