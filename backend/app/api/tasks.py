from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query
from app.database.models.task import (
    ResearchTaskRecord,
    TaskCreateRequest,
    TaskStatusTransitionRequest,
    TaskBulkCreateRequest,
    TaskStatsResponse,
)
from app.services.task_service import task_service

router = APIRouter(prefix="/tasks", tags=["Tasks"])


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------

@router.post("/", response_model=ResearchTaskRecord, status_code=201)
async def create_task(req: TaskCreateRequest):
    """Create a single research task."""
    return await task_service.create_task(req)


@router.post("/bulk", response_model=List[ResearchTaskRecord], status_code=201)
async def create_tasks_bulk(req: TaskBulkCreateRequest):
    """
    Bulk-create multiple tasks for a research job in one call.
    All tasks inherit the top-level `research_id`.
    """
    return await task_service.create_tasks_bulk(req.research_id, req.tasks)


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

@router.get("/{task_id}", response_model=ResearchTaskRecord)
async def get_task(task_id: str):
    """Retrieve a single task by its ID."""
    return await task_service.get_task(task_id)


@router.get("/research/{research_id}", response_model=List[ResearchTaskRecord])
async def list_tasks_for_research(
    research_id: str,
    status: Optional[str] = Query(
        default=None,
        description="Filter by status: pending | running | completed | failed | retrying | cancelled",
    ),
):
    """List all tasks for a research job, optionally filtered by status."""
    return await task_service.list_tasks(research_id, status_filter=status)


@router.get("/research/{research_id}/stats", response_model=TaskStatsResponse)
async def get_task_stats(research_id: str):
    """Get task counts by status for a research job."""
    return await task_service.get_task_stats(research_id)


# ---------------------------------------------------------------------------
# Status Transitions
# ---------------------------------------------------------------------------

@router.patch("/{task_id}/status", response_model=ResearchTaskRecord)
async def update_task_status(task_id: str, body: TaskStatusTransitionRequest):
    """
    Transition a task to a new status.

    Allowed transitions:
    - `pending`   → `running`, `cancelled`
    - `running`   → `completed`, `failed`, `cancelled`
    - `failed`    → `retrying`, `cancelled`
    - `retrying`  → `running`, `cancelled`
    - `completed` → *(terminal)*
    - `cancelled` → *(terminal)*
    """
    return await task_service.transition_status(
        task_id,
        body.status,
        error_message=body.error_message,
        result_summary=body.result_summary,
    )


# ---------------------------------------------------------------------------
# Cancel & Retry
# ---------------------------------------------------------------------------

@router.post("/{task_id}/cancel", response_model=ResearchTaskRecord)
async def cancel_task(task_id: str):
    """Cancel a task. Not allowed if already completed or cancelled."""
    return await task_service.cancel_task(task_id)


@router.post("/{task_id}/retry", response_model=ResearchTaskRecord)
async def retry_task(task_id: str):
    """
    Retry a failed task.
    Task must be in `failed` status and have remaining attempts.
    """
    return await task_service.retry_task(task_id)


@router.post("/research/{research_id}/cancel-all")
async def cancel_all_tasks(research_id: str):
    """Cancel all pending/running/retrying tasks for a research job."""
    return await task_service.cancel_all_for_research(research_id)
