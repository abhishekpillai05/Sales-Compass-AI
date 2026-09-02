"""
app/middleware/request_logging.py

FastAPI middleware for HTTP request/response logging with correlation IDs.

For every request this middleware:
  1. Generates or reuses an X-Request-ID header.
  2. Logs: method, path, status code, duration, request_id.
  3. Adds X-Request-ID to the response headers.
  4. Does NOT log passwords, tokens, cookies, Authorization headers,
     or any sensitive request/response body content.
"""

import time
import uuid
import logging

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)

# Headers that must never be echoed into logs
_SENSITIVE_HEADERS = frozenset(
    {
        "authorization",
        "cookie",
        "set-cookie",
        "x-api-key",
        "proxy-authorization",
    }
)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Log every HTTP request with timing and a correlation/request ID.

    Sensitive headers (Authorization, Cookie, Set-Cookie, X-Api-Key) are
    never included in log output.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next) -> Response:
        # ── Correlation / Request ID ─────────────────────────────────────────
        request_id: str = (
            request.headers.get("x-request-id") or str(uuid.uuid4())
        )

        start_time: float = time.perf_counter()

        # Process the request
        response: Response = await call_next(request)

        duration_ms: float = (time.perf_counter() - start_time) * 1000

        # Attach request_id to response so callers can correlate
        response.headers["X-Request-ID"] = request_id

        logger.info(
            "request_id=%s method=%s path=%s status=%d duration=%.1fms",
            request_id,
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )

        return response
