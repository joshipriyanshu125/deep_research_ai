from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, List, Optional

RESEARCH_STARTED = "RESEARCH_STARTED"
PLAN_CREATED = "PLAN_CREATED"
TASK_STARTED = "TASK_STARTED"
SEARCH_COMPLETED = "SEARCH_COMPLETED"
SOURCE_FOUND = "SOURCE_FOUND"
SOURCE_PROCESSED = "SOURCE_PROCESSED"
EVIDENCE_FOUND = "EVIDENCE_FOUND"
TASK_COMPLETED = "TASK_COMPLETED"
FACT_CHECK_STARTED = "FACT_CHECK_STARTED"
REPORT_STARTED = "REPORT_STARTED"
REPORT_COMPLETED = "REPORT_COMPLETED"
RESEARCH_FAILED = "RESEARCH_FAILED"

RESEARCH_EVENT_TYPES = [
    RESEARCH_STARTED,
    PLAN_CREATED,
    TASK_STARTED,
    SEARCH_COMPLETED,
    SOURCE_FOUND,
    SOURCE_PROCESSED,
    EVIDENCE_FOUND,
    TASK_COMPLETED,
    FACT_CHECK_STARTED,
    REPORT_STARTED,
    REPORT_COMPLETED,
    RESEARCH_FAILED,
]


class ResearchEventBus:
    """Simple in-memory event bus for real-time research events."""

    def __init__(self):
        self._job_queues: Dict[str, List[asyncio.Queue]] = {}
        self._history: Dict[str, List[Dict[str, Any]]] = {}

    def emit(
        self,
        event_name: str,
        job_id: Optional[str] = None,
        message: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        **extra: Any,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "event": event_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "message": message or event_name.replace("_", " ").title(),
            "data": data or {},
        }
        if job_id:
            payload["job_id"] = job_id
        payload.update(extra)

        if job_id:
            self._history.setdefault(job_id, []).append(payload)
            for queue in list(self._job_queues.get(job_id, [])):
                queue.put_nowait(payload)
        return payload

    async def subscribe(self, job_id: str) -> AsyncGenerator[Dict[str, Any], None]:
        queue: asyncio.Queue = asyncio.Queue()
        self._job_queues.setdefault(job_id, []).append(queue)
        try:
            while True:
                event = await queue.get()
                yield event
        finally:
            queues = self._job_queues.get(job_id, [])
            if queue in queues:
                queues.remove(queue)
            if not queues:
                self._job_queues.pop(job_id, None)

    def get_history(self, job_id: str) -> List[Dict[str, Any]]:
        return list(self._history.get(job_id, []))


research_event_bus = ResearchEventBus()

__all__ = [
    "RESEARCH_STARTED",
    "PLAN_CREATED",
    "TASK_STARTED",
    "SEARCH_COMPLETED",
    "SOURCE_FOUND",
    "SOURCE_PROCESSED",
    "EVIDENCE_FOUND",
    "TASK_COMPLETED",
    "FACT_CHECK_STARTED",
    "REPORT_STARTED",
    "REPORT_COMPLETED",
    "RESEARCH_FAILED",
    "RESEARCH_EVENT_TYPES",
    "ResearchEventBus",
    "research_event_bus",
]
