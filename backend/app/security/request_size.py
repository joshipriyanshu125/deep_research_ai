"""
Day 53 — Request Size Limits Middleware

Protects the FastAPI application from buffer overflows, memory exhaustion,
and Denial-of-Service attacks by enforcing maximum body size limits.
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from fastapi import Request, Response, status
from fastapi.responses import JSONResponse


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """
    Rejects incoming requests whose Content-Length exceeds the configured threshold.
    Default limit: 10 MB (10,485,760 bytes).
    """

    def __init__(self, app: ASGIApp, max_size_bytes: int = 10 * 1024 * 1024):
        super().__init__(app)
        self.max_size_bytes = max_size_bytes

    async def dispatch(self, request: Request, call_next) -> Response:
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                length = int(content_length)
                if length > self.max_size_bytes:
                    return JSONResponse(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        content={
                            "detail": f"Payload too large. Maximum allowed size is {self.max_size_bytes // (1024 * 1024)}MB."
                        },
                    )
            except ValueError:
                pass

        return await call_next(request)
