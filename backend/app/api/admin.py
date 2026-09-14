"""
Days 61–63 — Admin Backend API

All endpoints require an authenticated user with role == "admin".

Endpoints
---------
GET /admin/status      — system health overview
GET /admin/users       — paginated user list
GET /admin/research    — recent research jobs
GET /admin/jobs        — alias for /research with status filter
GET /admin/failures    — failed jobs only
GET /admin/usage       — LLM call stats
GET /admin/costs       — cost breakdown by model
GET /admin/sources     — research sources
GET /admin/reports     — generated reports
GET /admin/errors      — system errors
GET /admin/metrics     — full metrics snapshot
GET /admin/queue       — worker queue depth
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional

from app.database.models.user import UserInDB, UserRole
from app.middleware.auth import require_auth
from app.services.admin_service import admin_service

router = APIRouter(prefix="/admin", tags=["Admin"])


# ---------------------------------------------------------------------------
# Dependency
# ---------------------------------------------------------------------------

async def require_admin(current_user: UserInDB = Depends(require_auth)) -> UserInDB:
    """Rejects non-admin callers with HTTP 403."""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return current_user


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/status", summary="System health overview")
async def get_system_status(_: UserInDB = Depends(require_admin)):
    """Return system health: DB, worker, LLM config, uptime, queue depth."""
    return await admin_service.get_system_status()


@router.get("/users", summary="List all users")
async def get_users(
    limit: int = Query(100, ge=1, le=500),
    skip: int = Query(0, ge=0),
    role: Optional[str] = Query(None, description="Filter by role (user / admin)"),
    _: UserInDB = Depends(require_admin),
):
    """Return paginated list of registered users (password hashes excluded)."""
    return await admin_service.get_users(limit=limit, skip=skip, role=role)


@router.get("/research", summary="List research jobs")
async def get_research_jobs(
    limit: int = Query(50, ge=1, le=200),
    status: Optional[str] = Query(None, description="Filter by status"),
    _: UserInDB = Depends(require_admin),
):
    """Return recent research jobs sorted by creation date."""
    return await admin_service.get_research_jobs(limit=limit, status=status)


@router.get("/jobs", summary="List research jobs (alias)")
async def get_jobs(
    limit: int = Query(50, ge=1, le=200),
    status: Optional[str] = Query(None),
    _: UserInDB = Depends(require_admin),
):
    """Alias for /admin/research, matches the requested endpoint naming."""
    return await admin_service.get_research_jobs(limit=limit, status=status)


@router.get("/failures", summary="List failed jobs")
async def get_failed_jobs(
    limit: int = Query(50, ge=1, le=200),
    _: UserInDB = Depends(require_admin),
):
    """Return all failed research jobs with their error messages."""
    return await admin_service.get_failed_jobs(limit=limit)


@router.get("/usage", summary="LLM usage statistics")
async def get_llm_usage(_: UserInDB = Depends(require_admin)):
    """
    Return aggregated LLM metrics: total calls, error rate, latency
    percentiles, token counts, and cost estimates.
    """
    return await admin_service.get_llm_usage()


@router.get("/costs", summary="Cost breakdown by model")
async def get_costs(_: UserInDB = Depends(require_admin)):
    """Return total and per-model cost breakdown in USD."""
    return await admin_service.get_costs()


@router.get("/sources", summary="Research sources")
async def get_sources(
    limit: int = Query(100, ge=1, le=500),
    research_id: Optional[str] = Query(None),
    _: UserInDB = Depends(require_admin),
):
    """Return scraped/retrieved research sources."""
    return await admin_service.get_sources(limit=limit, research_id=research_id)


@router.get("/reports", summary="Generated research reports")
async def get_reports(
    limit: int = Query(50, ge=1, le=200),
    research_id: Optional[str] = Query(None),
    _: UserInDB = Depends(require_admin),
):
    """Return generated research reports."""
    return await admin_service.get_reports(limit=limit, research_id=research_id)


@router.get("/errors", summary="System errors")
async def get_system_errors(
    limit: int = Query(100, ge=1, le=500),
    _: UserInDB = Depends(require_admin),
):
    """Return recent system errors and current error metric counters."""
    return await admin_service.get_system_errors(limit=limit)


@router.get("/metrics", summary="Full metrics snapshot")
async def get_metrics(_: UserInDB = Depends(require_admin)):
    """Return the complete real-time metrics snapshot from Day 57."""
    return await admin_service.get_metrics()


@router.get("/queue", summary="Worker queue status")
async def get_queue_status(_: UserInDB = Depends(require_admin)):
    """Return current worker queue depth and job counts by status."""
    return await admin_service.get_queue_status()
