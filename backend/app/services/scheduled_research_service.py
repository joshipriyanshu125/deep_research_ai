import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from fastapi import HTTPException

from app.database.models.scheduled_research import (
    ScheduledResearch,
    ScheduledResearchCreate,
    ScheduledResearchUpdate,
    ScheduledChangeReport,
    ScheduledResearchFrequency,
)
from app.database.models.research import ResearchJob, ResearchStatus
from app.database.models.notification import NotificationPayload, NotificationEventType
from app.database.repositories.scheduled_research_repo import scheduled_research_repo
from app.database.repositories.research_repo import research_repo
from app.database.repositories.report_repo import report_repo
from app.agents.scheduled_research_agent import scheduled_research_agent
from app.research.orchestrator import research_orchestrator
from app.services.notification_service import notification_service
from app.utils.logger import logger


class ScheduledResearchService:
    """
    Day 70–72 — Scheduled Research Service & Scheduler Loop
    Orchestrates periodic research execution, report comparison, change report generation,
    and notification dispatch.
    """

    def __init__(self):
        self.is_running = False
        self._scheduler_task: Optional[asyncio.Task] = None

    def calculate_next_run(
        self,
        frequency: str,
        schedule_day: str = "monday",
        from_time: Optional[datetime] = None,
    ) -> datetime:
        base = from_time or datetime.now(timezone.utc)
        freq = frequency.lower()
        if freq == ScheduledResearchFrequency.DAILY.value:
            return base + timedelta(days=1)
        elif freq == ScheduledResearchFrequency.MONTHLY.value:
            return base + timedelta(days=30)
        else:
            # Default to weekly on schedule_day
            days_map = {
                "monday": 0,
                "tuesday": 1,
                "wednesday": 2,
                "thursday": 3,
                "friday": 4,
                "saturday": 5,
                "sunday": 6,
            }
            target_weekday = days_map.get(schedule_day.lower(), 0)
            current_weekday = base.weekday()
            days_ahead = target_weekday - current_weekday
            if days_ahead <= 0:
                days_ahead += 7
            return base + timedelta(days=days_ahead)

    async def create_schedule(
        self, request: ScheduledResearchCreate, user_id: str = "anonymous"
    ) -> ScheduledResearch:
        title = request.title or f"Scheduled Tracker: {request.query}"
        next_run = self.calculate_next_run(request.frequency, request.schedule_day)
        scheduled = ScheduledResearch(
            user_id=user_id,
            query=request.query,
            title=title,
            frequency=request.frequency,
            schedule_day=request.schedule_day,
            cron_expression=request.cron_expression,
            depth=request.depth,
            breadth=request.breadth,
            categories=request.categories,
            next_run_at=next_run,
        )
        return await scheduled_research_repo.create(scheduled)

    async def get_schedule(self, id: str) -> ScheduledResearch:
        item = await scheduled_research_repo.get(id)
        if not item:
            raise HTTPException(status_code=404, detail="Scheduled research task not found")
        return item

    async def list_user_schedules(self, user_id: str, limit: int = 50) -> List[ScheduledResearch]:
        return await scheduled_research_repo.list_by_user(user_id=user_id, limit=limit)

    async def update_schedule(self, id: str, request: ScheduledResearchUpdate) -> ScheduledResearch:
        item = await self.get_schedule(id)
        if request.title is not None:
            item.title = request.title
        if request.frequency is not None:
            item.frequency = request.frequency
        if request.schedule_day is not None:
            item.schedule_day = request.schedule_day
        if request.cron_expression is not None:
            item.cron_expression = request.cron_expression
        if request.is_active is not None:
            item.is_active = request.is_active
        if request.depth is not None:
            item.depth = request.depth
        if request.breadth is not None:
            item.breadth = request.breadth

        item.next_run_at = self.calculate_next_run(item.frequency, item.schedule_day)
        return await scheduled_research_repo.update(item)

    async def delete_schedule(self, id: str) -> bool:
        await self.get_schedule(id)
        return await scheduled_research_repo.delete(id)

    async def execute_scheduled_task(self, scheduled_id: str) -> ScheduledChangeReport:
        schedule = await self.get_schedule(scheduled_id)
        logger.info(f"[ScheduledResearch] Executing scheduled research task {schedule.id} for query '{schedule.query}'")

        # 1. Create ResearchJob
        job = ResearchJob(
            user_id=schedule.user_id,
            query=schedule.query,
            depth=schedule.depth,
            breadth=schedule.breadth,
            categories=schedule.categories,
            status=ResearchStatus.PENDING,
        )
        await research_repo.create_job(job)

        # 2. Run research orchestrator
        async for _ in research_orchestrator.run_pipeline_stream(job):
            pass

        # 3. Retrieve current report
        current_report = await report_repo.get_by_research_id(job.id)
        if not current_report:
            raise RuntimeError(f"Failed to generate report for scheduled job {job.id}")

        # 4. Fetch previous report from history if available
        previous_report = None
        if schedule.history:
            last_run = schedule.history[-1]
            prev_report_id = last_run.get("report_id")
            if prev_report_id:
                previous_report = await report_repo.get_by_id(prev_report_id)

        # 5. Generate Change Report via Agent
        change_report = await scheduled_research_agent.compare_and_generate_change_report(
            schedule=schedule,
            current_report=current_report,
            previous_report=previous_report,
        )
        await scheduled_research_repo.create_change_report(change_report)

        # 6. Multi-channel Notification
        notification_payload = NotificationPayload(
            event_type=NotificationEventType.SCHEDULED_RESEARCH_COMPLETED.value,
            user_id=schedule.user_id,
            research_id=job.id,
            title=f"Scheduled Research Update: {schedule.title or schedule.query}",
            message=change_report.summary_of_changes[:300],
            data={
                "scheduled_id": schedule.id,
                "change_report_id": change_report.id,
                "new_findings": change_report.new_findings,
            },
        )
        await notification_service.dispatch(notification_payload)

        # 7. Update schedule state
        now = datetime.now(timezone.utc)
        schedule.last_run_at = now
        schedule.next_run_at = self.calculate_next_run(schedule.frequency, schedule.schedule_day, from_time=now)
        schedule.history.append({
            "job_id": job.id,
            "report_id": current_report.id,
            "change_report_id": change_report.id,
            "run_at": now.isoformat(),
            "status": "completed",
        })
        await scheduled_research_repo.update(schedule)

        logger.info(f"[ScheduledResearch] Completed task {schedule.id}. Change report {change_report.id} created.")
        return change_report

    async def check_and_run_due_schedules(self):
        due_items = await scheduled_research_repo.list_active_due()
        for schedule in due_items:
            try:
                await self.execute_scheduled_task(schedule.id)
            except Exception as e:
                logger.error(f"[ScheduledResearch] Error executing scheduled task {schedule.id}: {e}")

    async def start_scheduler_loop(self, poll_interval_seconds: int = 60):
        self.is_running = True
        logger.info("[ScheduledResearchService] Scheduler background loop started.")
        while self.is_running:
            try:
                await self.check_and_run_due_schedules()
                await asyncio.sleep(poll_interval_seconds)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[ScheduledResearchService] Loop encountered error: {e}")
                await asyncio.sleep(poll_interval_seconds)

    def stop_scheduler_loop(self):
        self.is_running = False
        if self._scheduler_task:
            self._scheduler_task.cancel()


scheduled_research_service = ScheduledResearchService()
