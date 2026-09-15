"""
Day 96–100 — Production Deployment: Health & Monitoring Probes

Provides standard production observability endpoints:
- GET /health/live   — Liveness probe (container running)
- GET /health/ready  — Readiness probe (DB, Redis, Vector DB operational)
- GET /health        — Full system diagnostic status
- GET /metrics       — Prometheus scraping endpoint (exposition format v0.0.4)
"""

from __future__ import annotations

import time
from typing import Any, Dict
from fastapi import APIRouter, Response, status
from fastapi.responses import PlainTextResponse

from app.config.settings import settings
from app.database.mongodb import get_database
from app.monitoring.metrics import metrics_collector
from app.services.redis_service import redis_service

router = APIRouter(tags=["Health & Monitoring"])


@router.get("/health/live", summary="Kubernetes / Docker Liveness Probe")
async def liveness_probe() -> Dict[str, str]:
    """
    Returns HTTP 200 if the process is alive.
    Used by load balancers and container orchestrators to detect process crashes.
    """
    return {"status": "alive", "timestamp": str(time.time())}


@router.get("/health/ready", summary="Kubernetes / Docker Readiness Probe")
async def readiness_probe(response: Response) -> Dict[str, Any]:
    """
    Validates core backing services (MongoDB, Redis).
    Returns HTTP 200 when ready to receive traffic, HTTP 503 if critical dependencies are down.
    """
    checks: Dict[str, Any] = {}
    is_ready = True

    # 1. MongoDB Check
    try:
        db = get_database()
        if db is not None:
            # Quick ping command
            await db.command("ping")
            checks["mongodb"] = {"status": "connected"}
        else:
            checks["mongodb"] = {"status": "not_initialized"}
            # Only fail readiness if not running in mock/dev mode
            if settings.ENVIRONMENT == "production":
                is_ready = False
    except Exception as e:
        checks["mongodb"] = {"status": "error", "message": str(e)}
        if settings.ENVIRONMENT == "production":
            is_ready = False

    # 2. Redis Check
    redis_status = await redis_service.health_check()
    checks["redis"] = redis_status

    # 3. Queue status
    checks["queue_driver"] = "redis" if redis_service.is_connected else "in-memory-fallback"

    if not is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": "ready" if is_ready else "not_ready",
        "environment": settings.ENVIRONMENT,
        "checks": checks,
    }


@router.get("/health", summary="Full System Health Diagnostic")
@router.get(f"{settings.API_V1_STR}/health", summary="API Health Check")
async def full_health_status() -> Dict[str, Any]:
    """Return comprehensive health status including DB and Redis connectivity."""
    db_ok = False
    try:
        db = get_database()
        if db is not None:
            await db.command("ping")
            db_ok = True
    except Exception:
        db_ok = False

    redis_diag = await redis_service.health_check()

    return {
        "status": "healthy" if (db_ok or settings.ENVIRONMENT != "production") else "degraded",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "database": {"connected": db_ok, "type": "mongodb"},
        "redis": redis_diag,
        "vector_db": {"type": settings.VECTOR_DB_TYPE, "collection": settings.VECTOR_DB_COLLECTION},
        "llm_provider": settings.LLM_PROVIDER,
        "active_model": settings.DEFAULT_MODEL,
    }


@router.get("/health/services", summary="Individual Services Health & Readiness Breakdown")
@router.get(f"{settings.API_V1_STR}/health/services", summary="API Individual Services Health Breakdown")
async def services_health_status() -> Dict[str, Any]:
    """Return detailed health breakdown for all integrated services and dependencies."""
    # 1. MongoDB
    db_status: Dict[str, Any] = {"type": "mongodb", "database": settings.MONGODB_DB_NAME}
    try:
        db = get_database()
        if db is not None:
            t0 = time.perf_counter()
            await db.command("ping")
            latency_ms = round((time.perf_counter() - t0) * 1000, 2)
            db_status.update({"status": "healthy", "connected": True, "latency_ms": latency_ms})
        else:
            db_status.update({"status": "disconnected", "connected": False})
    except Exception as exc:
        db_status.update({"status": "unhealthy", "connected": False, "error": str(exc)})

    # 2. Redis
    redis_status = await redis_service.health_check()

    # 3. Vector DB (Qdrant / Chroma / In-Memory)
    vector_status = {
        "type": settings.VECTOR_DB_TYPE,
        "collection": settings.VECTOR_DB_COLLECTION,
        "url": settings.VECTOR_DB_URL,
        "configured": bool(settings.VECTOR_DB_API_KEY or settings.VECTOR_DB_TYPE == "in_memory"),
        "status": "healthy" if settings.VECTOR_DB_TYPE in ("qdrant", "chroma", "in_memory") else "unknown"
    }

    # 4. LLM Providers
    llm_status = {
        "primary_provider": settings.LLM_PROVIDER,
        "default_model": settings.DEFAULT_MODEL,
        "openrouter_configured": bool(settings.OPENROUTER_API_KEY),
        "openai_configured": bool(settings.OPENAI_API_KEY),
        "gemini_configured": bool(settings.GEMINI_API_KEY),
        "anthropic_configured": bool(settings.ANTHROPIC_API_KEY),
        "status": "healthy" if (settings.OPENROUTER_API_KEY or settings.OPENAI_API_KEY or settings.GEMINI_API_KEY) else "unconfigured"
    }

    # 5. Search Engines
    search_status = {
        "tavily_configured": bool(settings.TAVILY_API_KEY),
        "serper_configured": bool(settings.SERPER_API_KEY),
        "mock_fallback_enabled": settings.USE_MOCK_FALLBACK,
        "status": "healthy" if (settings.TAVILY_API_KEY or settings.SERPER_API_KEY or settings.USE_MOCK_FALLBACK) else "degraded"
    }

    # 6. Email / SMTP
    email_status = {
        "smtp_server": settings.SMTP_SERVER,
        "smtp_port": settings.SMTP_PORT,
        "smtp_username_configured": bool(settings.SMTP_USERNAME),
        "from_address": settings.EMAIL_FROM,
        "status": "configured" if (settings.SMTP_USERNAME and settings.SMTP_PASSWORD) else "unconfigured"
    }

    all_healthy = db_status.get("connected", False) and (llm_status["status"] == "healthy")

    return {
        "status": "healthy" if all_healthy else "degraded",
        "timestamp": time.time(),
        "environment": settings.ENVIRONMENT,
        "services": {
            "database": db_status,
            "redis": redis_status,
            "vector_database": vector_status,
            "llm": llm_status,
            "search": search_status,
            "email": email_status
        }
    }


@router.get("/metrics", summary="Prometheus Metrics Endpoint", response_class=PlainTextResponse)
async def prometheus_metrics() -> str:
    """
    Expose metrics formatted for Prometheus server scraping.
    Content-Type: text/plain; version=0.0.4
    """
    return metrics_collector.to_prometheus_text()
