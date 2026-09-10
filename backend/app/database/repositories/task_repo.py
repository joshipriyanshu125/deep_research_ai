from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from app.database.mongodb import db_manager
from app.database.models.task import ResearchTaskRecord, TaskStatus
from app.utils.logger import logger


class TaskRepository:
    """
    Dual-mode repository for ResearchTaskRecord.
    Uses MongoDB collection `research_tasks` when connected,
    falls back to in-memory dict when offline.
    """

    def __init__(self):
        self._tasks: Dict[str, ResearchTaskRecord] = {}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _from_doc(self, doc: Dict[str, Any]) -> ResearchTaskRecord:
        """Convert a MongoDB document (with _id) to ResearchTaskRecord."""
        doc["_id"] = str(doc.get("_id", doc.get("id", "")))
        return ResearchTaskRecord(**doc)

    def _to_doc(self, task: ResearchTaskRecord) -> Dict[str, Any]:
        """Serialize task to a MongoDB-friendly dict keyed by _id."""
        d = task.model_dump(by_alias=True)
        # Ensure both 'id' and '_id' are present for query compatibility
        d["id"] = task.id
        return d

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    async def create_task(self, task: ResearchTaskRecord) -> ResearchTaskRecord:
        if db_manager.is_connected:
            await db_manager.db.research_tasks.insert_one(self._to_doc(task))
        else:
            self._tasks[task.id] = task
        return task

    async def get_task(self, task_id: str) -> Optional[ResearchTaskRecord]:
        if db_manager.is_connected:
            doc = await db_manager.db.research_tasks.find_one({"id": task_id})
            return self._from_doc(doc) if doc else None
        return self._tasks.get(task_id)

    async def update_task(self, task: ResearchTaskRecord) -> ResearchTaskRecord:
        task.touch()
        if db_manager.is_connected:
            await db_manager.db.research_tasks.replace_one(
                {"id": task.id}, self._to_doc(task)
            )
        else:
            self._tasks[task.id] = task
        return task

    async def delete_task(self, task_id: str) -> bool:
        if db_manager.is_connected:
            result = await db_manager.db.research_tasks.delete_one({"id": task_id})
            return result.deleted_count > 0
        if task_id in self._tasks:
            del self._tasks[task_id]
            return True
        return False

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    async def list_tasks_by_research(
        self,
        research_id: str,
        status_filter: Optional[str] = None,
    ) -> List[ResearchTaskRecord]:
        if db_manager.is_connected:
            query: Dict[str, Any] = {"research_id": research_id}
            if status_filter:
                query["status"] = status_filter
            cursor = (
                db_manager.db.research_tasks
                .find(query)
                .sort([("priority", 1), ("created_at", 1)])
            )
            return [self._from_doc(doc) async for doc in cursor]

        tasks = [t for t in self._tasks.values() if t.research_id == research_id]
        if status_filter:
            tasks = [t for t in tasks if t.status == status_filter]
        tasks.sort(key=lambda t: (t.priority, t.created_at))
        return tasks

    async def get_tasks_by_status(
        self, status: str, limit: int = 50
    ) -> List[ResearchTaskRecord]:
        if db_manager.is_connected:
            cursor = (
                db_manager.db.research_tasks
                .find({"status": status})
                .sort([("priority", 1), ("created_at", 1)])
                .limit(limit)
            )
            return [self._from_doc(doc) async for doc in cursor]

        tasks = [t for t in self._tasks.values() if t.status == status]
        tasks.sort(key=lambda t: (t.priority, t.created_at))
        return tasks[:limit]

    # ------------------------------------------------------------------
    # Atomic Updates
    # ------------------------------------------------------------------

    async def update_task_status(
        self,
        task_id: str,
        new_status: str,
        *,
        error_message: Optional[str] = None,
        result_summary: Optional[str] = None,
    ) -> Optional[ResearchTaskRecord]:
        task = await self.get_task(task_id)
        if not task:
            return None

        task.status = new_status
        task.touch()

        now = self._now()
        if new_status == TaskStatus.RUNNING:
            task.started_at = now
        elif new_status in {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED}:
            task.completed_at = now

        if error_message is not None:
            task.error_message = error_message
        if result_summary is not None:
            task.result_summary = result_summary

        return await self.update_task(task)

    async def increment_attempts(self, task_id: str) -> Optional[ResearchTaskRecord]:
        task = await self.get_task(task_id)
        if not task:
            return None
        task.attempts += 1
        task.touch()
        return await self.update_task(task)

    async def cancel_pending_tasks(self, research_id: str) -> int:
        """Bulk-cancel all pending/running tasks for a research job. Returns count."""
        cancellable = await self.list_tasks_by_research(research_id)
        count = 0
        for task in cancellable:
            if task.status in {TaskStatus.PENDING, TaskStatus.RUNNING, TaskStatus.RETRYING}:
                await self.update_task_status(task.id, TaskStatus.CANCELLED)
                count += 1
        logger.info(f"Cancelled {count} tasks for research_id={research_id}")
        return count

    # ------------------------------------------------------------------
    # Aggregation
    # ------------------------------------------------------------------

    async def get_task_counts(self, research_id: str) -> Dict[str, int]:
        """Return a dict of {status: count} for all tasks in a research job."""
        tasks = await self.list_tasks_by_research(research_id)
        counts: Dict[str, int] = {s: 0 for s in TaskStatus.ALL}
        for t in tasks:
            counts[t.status] = counts.get(t.status, 0) + 1
        return counts


task_repo = TaskRepository()
