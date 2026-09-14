"""
Days 61–63 — Admin Service Layer

Provides all data-retrieval logic for the admin API endpoints.
Queries MongoDB when available; falls back to in-memory stores
(metrics collector, worker queue) when DB is offline.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.database.mongodb import get_database
from app.utils.logger import logger


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _utcnow_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


async def _find_many(
    collection: str,
    query: dict,
    limit: int = 100,
    sort_field: str = "created_at",
    sort_dir: int = -1,
) -> List[Dict[str, Any]]:
    """Generic helper: query a MongoDB collection and return a list of dicts."""
    db = get_database()
    if db is None:
        return []
    cursor = db[collection].find(query, {"_id": 0}).sort(sort_field, sort_dir).limit(limit)
    return await cursor.to_list(length=limit)


async def _count(collection: str, query: dict) -> int:
    db = get_database()
    if db is None:
        return 0
    return await db[collection].count_documents(query)


# ---------------------------------------------------------------------------
# Admin Service
# ---------------------------------------------------------------------------

class AdminService:
    """
    All read-only admin queries.  All methods are async-safe and return
    plain dicts/lists — no Pydantic models — so the router can directly
    return them as JSON.
    """

    # ------------------------------------------------------------------ #
    # Users
    # ------------------------------------------------------------------ #

    async def get_users(
        self,
        limit: int = 100,
        skip: int = 0,
        role: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Return paginated user list."""
        db = get_database()
        query: dict = {}
        if role:
            query["role"] = role

        if db is None:
            return {"users": [], "total": 0, "limit": limit, "skip": skip}

        total = await _count("users", query)
        cursor = db["users"].find(
            query,
            {"_id": 0, "hashed_password": 0},  # never expose password hash
        ).skip(skip).limit(limit).sort("created_at", -1)
        users = await cursor.to_list(length=limit)
        return {"users": users, "total": total, "limit": limit, "skip": skip}

    # ------------------------------------------------------------------ #
    # Research jobs
    # ------------------------------------------------------------------ #

    async def get_research_jobs(
        self,
        limit: int = 50,
        status: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Return recent research jobs, optionally filtered by status."""
        query: dict = {}
        if status:
            query["status"] = status
        jobs = await _find_many("research_jobs", query, limit=limit)
        total = await _count("research_jobs", query)
        return {"jobs": jobs, "total": total, "limit": limit}

    async def get_failed_jobs(self, limit: int = 50) -> Dict[str, Any]:
        """Return all failed research jobs with their error messages."""
        jobs = await _find_many("research_jobs", {"status": "failed"}, limit=limit)
        return {
            "failed_jobs": jobs,
            "total": len(jobs),
            "retrieved_at": _utcnow_iso(),
        }

    # ------------------------------------------------------------------ #
    # LLM Usage & Costs
    # ------------------------------------------------------------------ #

    async def get_llm_usage(self) -> Dict[str, Any]:
        """
        Return aggregated LLM usage stats from the metrics collector
        and any usage records stored in the DB.
        """
        from app.monitoring.metrics import metrics_collector
        snap = metrics_collector.get_snapshot()

        # Pull DB-level usage records if the collection exists
        db_records = await _find_many("llm_usage", {}, limit=1000, sort_field="timestamp")

        total_calls = snap["llm_calls_total"]["total"]
        total_errors = snap["llm_errors_total"]["total"]
        latency = snap["llm_latency_ms"]

        # Aggregate cost from DB records
        total_cost_usd = sum(r.get("cost_usd", 0.0) for r in db_records)
        total_tokens = sum(r.get("total_tokens", 0) for r in db_records)

        return {
            "total_calls": total_calls,
            "total_errors": total_errors,
            "error_rate": round(total_errors / total_calls, 4) if total_calls else 0.0,
            "latency_ms": latency,
            "total_cost_usd": round(total_cost_usd, 4),
            "total_tokens": total_tokens,
            "by_model": snap["llm_calls_total"].get("by_labels", {}),
            "retrieved_at": _utcnow_iso(),
        }

    async def get_costs(self) -> Dict[str, Any]:
        """Return cost breakdown by model and time window."""
        db_records = await _find_many("llm_usage", {}, limit=5000, sort_field="timestamp")

        by_model: Dict[str, float] = {}
        for r in db_records:
            model = r.get("model", "unknown")
            by_model[model] = round(by_model.get(model, 0.0) + r.get("cost_usd", 0.0), 6)

        return {
            "total_cost_usd": round(sum(by_model.values()), 4),
            "by_model": by_model,
            "record_count": len(db_records),
            "retrieved_at": _utcnow_iso(),
        }

    # ------------------------------------------------------------------ #
    # Sources & Reports
    # ------------------------------------------------------------------ #

    async def get_sources(
        self,
        limit: int = 100,
        research_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Return research sources with optional research_id filter."""
        query: dict = {}
        if research_id:
            query["research_id"] = research_id
        sources = await _find_many("research_sources", query, limit=limit)
        total = await _count("research_sources", query)
        return {"sources": sources, "total": total, "limit": limit}

    async def get_reports(
        self,
        limit: int = 50,
        research_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Return research reports."""
        query: dict = {}
        if research_id:
            query["research_id"] = research_id
        reports = await _find_many("research_reports", query, limit=limit)
        total = await _count("research_reports", query)
        return {"reports": reports, "total": total, "limit": limit}

    # ------------------------------------------------------------------ #
    # System Errors
    # ------------------------------------------------------------------ #

    async def get_system_errors(self, limit: int = 100) -> Dict[str, Any]:
        """
        Return recent system errors from DB error log collection.
        Also surfaces current metric error counters.
        """
        from app.monitoring.metrics import metrics_collector
        snap = metrics_collector.get_snapshot()

        db_errors = await _find_many("system_errors", {}, limit=limit, sort_field="timestamp")

        return {
            "db_errors": db_errors,
            "metric_counters": {
                "llm_errors_total": snap["llm_errors_total"]["total"],
                "search_errors_total": snap["search_errors_total"]["total"],
                "scraping_errors_total": snap["scraping_errors_total"]["total"],
                "worker_failures_total": snap["worker_failures_total"]["total"],
            },
            "total": len(db_errors),
            "retrieved_at": _utcnow_iso(),
        }

    # ------------------------------------------------------------------ #
    # Metrics (Day 57 integration)
    # ------------------------------------------------------------------ #

    async def get_metrics(self) -> Dict[str, Any]:
        """Return the full metrics snapshot from the in-memory collector."""
        from app.monitoring.metrics import metrics_collector
        snap = metrics_collector.get_snapshot()
        snap["retrieved_at"] = _utcnow_iso()
        return snap

    # ------------------------------------------------------------------ #
    # Queue Status
    # ------------------------------------------------------------------ #

    async def get_queue_status(self) -> Dict[str, Any]:
        """Return the current worker queue depth and processing status."""
        from app.workers.research_worker import research_worker
        from app.monitoring.metrics import metrics_collector

        qsize = research_worker.queue.qsize()
        metrics_collector.set_queue_size(qsize)

        pending = await _count("research_jobs", {"status": "pending"})
        in_progress = await _count("research_jobs", {"status": {"$in": [
            "planning", "searching", "extracting", "analyzing", "synthesizing"
        ]}})

        return {
            "queue_size": qsize,
            "worker_running": research_worker.is_running,
            "db_pending_jobs": pending,
            "db_in_progress_jobs": in_progress,
            "retrieved_at": _utcnow_iso(),
        }

    # ------------------------------------------------------------------ #
    # System Overview
    # ------------------------------------------------------------------ #

    async def get_system_status(self) -> Dict[str, Any]:
        """One-stop status endpoint combining DB, worker, and metrics state."""
        from app.config.settings import settings
        from app.database.mongodb import db_manager
        from app.monitoring.metrics import metrics_collector

        snap = metrics_collector.get_snapshot()
        queue_status = await self.get_queue_status()

        return {
            "project_name": settings.PROJECT_NAME,
            "version": settings.VERSION,
            "environment": settings.ENVIRONMENT,
            "debug": settings.DEBUG,
            "llm_provider": settings.LLM_PROVIDER,
            "default_model": settings.DEFAULT_MODEL,
            "db_connected": db_manager.is_connected,
            "uptime_seconds": snap["uptime_seconds"],
            "queue": queue_status,
            "retrieved_at": _utcnow_iso(),
        }


admin_service = AdminService()
