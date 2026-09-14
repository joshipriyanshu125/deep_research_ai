"""
Day 56 — Structured Request Logging Middleware

Emits a structured JSON log on every request:
    {
      "event": "api_request",
      "method": "GET",
      "path": "/api/v1/research",
      "status": 200,
      "latency_ms": 42.3,
      "request_id": "..."
    }

Also calls app.monitoring.metrics.record_api_request() (Day 57) so latency
histograms are updated automatically.
"""

import time
import uuid
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from app.utils.logger import logger


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
        start_time = time.perf_counter()

        response = await call_next(request)

        latency_ms = (time.perf_counter() - start_time) * 1000

        logger.info(
            f"{request.method} {request.url.path} {response.status_code} {latency_ms:.2f}ms",
            extra={
                "event": "api_request",
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "latency_ms": round(latency_ms, 2),
                "request_id": request_id,
            },
        )

        # Day 57 — update metrics (graceful: skip if monitoring not yet imported)
        try:
            from app.monitoring.metrics import metrics_collector
            metrics_collector.record_api_request(
                method=request.method,
                path=request.url.path,
                status=response.status_code,
                latency_ms=latency_ms,
            )
        except Exception:
            pass

        response.headers["x-request-id"] = request_id
        return response
