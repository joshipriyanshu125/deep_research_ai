from typing import Optional, List, Dict, Any
from fastapi import HTTPException
from app.database.models.task import (
    ResearchTaskRecord,
    TaskStatus,
    TaskType,
    TaskCreateRequest,
    TaskStatsResponse,
)
from app.database.repositories.task_repo import task_repo
from app.utils.logger import logger

_HTTP_422 = 422  # Unprocessable Content — avoids deprecated Starlette constant names
_HTTP_404 = 404


class TaskService:
    """
    Business-logic layer for research task management.
    Enforces status transition rules and handles retry/cancel semantics.
    """

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    async def create_task(self, req: TaskCreateRequest) -> ResearchTaskRecord:
        """Create and persist a single ResearchTaskRecord."""
        if req.type not in TaskType.ALL:
            raise HTTPException(
                status_code=_HTTP_422,
                detail=f"Invalid task type '{req.type}'. Must be one of {sorted(TaskType.ALL)}.",
            )

        task = ResearchTaskRecord(
            research_id=req.research_id,
            question=req.question,
            type=req.type,
            priority=req.priority,
            assigned_agent=req.assigned_agent,
            max_attempts=req.max_attempts,
            metadata=req.metadata,
        )
        await task_repo.create_task(task)
        logger.info(f"Created task {task.id} for research_id={req.research_id} [{req.type}]")
        return task

    async def create_tasks_bulk(
        self, research_id: str, tasks_data: List[TaskCreateRequest]
    ) -> List[ResearchTaskRecord]:
        """Bulk-create tasks for a research job (e.g. from planner output)."""
        created = []
        for req in tasks_data:
            req.research_id = research_id  # enforce consistent research_id
            task = await self.create_task(req)
            created.append(task)
        logger.info(f"Bulk-created {len(created)} tasks for research_id={research_id}")
        return created

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def get_task(self, task_id: str) -> ResearchTaskRecord:
        task = await task_repo.get_task(task_id)
        if not task:
            raise HTTPException(
                status_code=_HTTP_404,
                detail=f"Task '{task_id}' not found.",
            )
        return task

    async def list_tasks(
        self,
        research_id: str,
        status_filter: Optional[str] = None,
    ) -> List[ResearchTaskRecord]:
        if status_filter and status_filter not in TaskStatus.ALL:
            raise HTTPException(
                status_code=_HTTP_422,
                detail=f"Invalid status filter '{status_filter}'.",
            )
        return await task_repo.list_tasks_by_research(research_id, status_filter)

    # ------------------------------------------------------------------
    # Status Transitions
    # ------------------------------------------------------------------

    async def transition_status(
        self,
        task_id: str,
        new_status: str,
        *,
        error_message: Optional[str] = None,
        result_summary: Optional[str] = None,
    ) -> ResearchTaskRecord:
        """
        Transition a task to a new status, enforcing allowed transitions.
        Raises 422 for illegal transitions, 404 if task not found.
        """
        task = await self.get_task(task_id)

        if new_status not in TaskStatus.ALL:
            raise HTTPException(
                status_code=_HTTP_422,
                detail=f"Unknown status '{new_status}'.",
            )

        if not task.can_transition_to(new_status):
            raise HTTPException(
                status_code=_HTTP_422,
                detail=(
                    f"Cannot transition task from '{task.status}' to '{new_status}'. "
                    f"Allowed next states: {sorted(TaskStatus.TRANSITIONS.get(task.status, set()))}."
                ),
            )

        updated = await task_repo.update_task_status(
            task_id,
            new_status,
            error_message=error_message,
            result_summary=result_summary,
        )
        logger.info(f"Task {task_id}: {task.status} → {new_status}")
        return updated

    # ------------------------------------------------------------------
    # Cancel
    # ------------------------------------------------------------------

    async def cancel_task(self, task_id: str) -> ResearchTaskRecord:
        """Cancel a task. Only allowed if not already in a terminal state."""
        task = await self.get_task(task_id)
        if task.is_terminal():
            raise HTTPException(
                status_code=_HTTP_422,
                detail=f"Task is already in terminal state '{task.status}' and cannot be cancelled.",
            )
        return await self.transition_status(task_id, TaskStatus.CANCELLED)

    async def cancel_all_for_research(self, research_id: str) -> Dict[str, Any]:
        """Cancel all non-terminal tasks for a given research job."""
        count = await task_repo.cancel_pending_tasks(research_id)
        return {"research_id": research_id, "cancelled_count": count}

    # ------------------------------------------------------------------
    # Retry
    # ------------------------------------------------------------------

    async def retry_task(self, task_id: str) -> ResearchTaskRecord:
        """
        Retry a failed task.
        - Task must be in FAILED status.
        - Must not have exceeded max_attempts.
        - Increments attempt counter, sets status to RETRYING.
        """
        task = await self.get_task(task_id)

        if task.status != TaskStatus.FAILED:
            raise HTTPException(
                status_code=_HTTP_422,
                detail=f"Only FAILED tasks can be retried. Current status: '{task.status}'.",
            )
        if not task.is_retryable():
            raise HTTPException(
                status_code=_HTTP_422,
                detail=(
                    f"Task has exhausted all {task.max_attempts} attempts and cannot be retried."
                ),
            )

        await task_repo.increment_attempts(task_id)
        updated = await self.transition_status(
            task_id, TaskStatus.RETRYING, error_message=None
        )
        logger.info(f"Task {task_id} queued for retry (attempt {updated.attempts}/{updated.max_attempts})")
        return updated

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    async def get_task_stats(self, research_id: str) -> TaskStatsResponse:
        """Return task counts per status for a research job."""
        counts = await task_repo.get_task_counts(research_id)
        total = sum(counts.values())
        completed = counts.get(TaskStatus.COMPLETED, 0)
        rate = round((completed / total * 100), 1) if total > 0 else 0.0

        return TaskStatsResponse(
            research_id=research_id,
            total=total,
            pending=counts.get(TaskStatus.PENDING, 0),
            running=counts.get(TaskStatus.RUNNING, 0),
            completed=completed,
            failed=counts.get(TaskStatus.FAILED, 0),
            retrying=counts.get(TaskStatus.RETRYING, 0),
            cancelled=counts.get(TaskStatus.CANCELLED, 0),
            completion_rate=rate,
        )


task_service = TaskService()
