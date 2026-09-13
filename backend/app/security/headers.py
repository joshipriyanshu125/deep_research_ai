"""
Day 53 — Secure HTTP Headers Middleware

Injects security headers into every API and static response:
  - Content-Security-Policy (CSP)
  - X-Content-Type-Options: nosniff
  - X-Frame-Options: DENY
  - X-XSS-Protection: 1; mode=block
  - Strict-Transport-Security (HSTS)
  - Referrer-Policy: strict-origin-when-cross-origin
  - Permissions-Policy
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from fastapi import Request, Response


DEFAULT_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=()",
    "Content-Security-Policy": (
        "default-src 'self'; "
        "img-src 'self' data: https: blob:; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.jsdelivr.net; "
        "font-src 'self' https://fonts.gstatic.com data:; "
        "connect-src 'self' https: ws: wss:;"
    ),
}


class SecureHeadersMiddleware(BaseHTTPMiddleware):
    """
    Day 53 — Security Middleware that appends industry-standard security headers
    to prevent MIME-confusion attacks, clickjacking, XSS, and transport downgrade attacks.
    """

    def __init__(self, app: ASGIApp, custom_headers: dict = None):
        super().__init__(app)
        self.headers = DEFAULT_SECURITY_HEADERS.copy()
        if custom_headers:
            self.headers.update(custom_headers)

    async def dispatch(self, request: Request, call_next) -> Response:
        response: Response = await call_next(request)
        for key, value in self.headers.items():
            if key not in response.headers:
                response.headers[key] = value
        return response
