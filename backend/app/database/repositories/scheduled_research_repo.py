from datetime import datetime, timezone
from typing import Optional, List, Dict
from app.database.mongodb import db_manager
from app.database.models.scheduled_research import ScheduledResearch, ScheduledChangeReport
from app.utils.logger import logger


class ScheduledResearchRepository:
    def __init__(self):
        self._schedules: Dict[str, ScheduledResearch] = {}
        self._change_reports: Dict[str, ScheduledChangeReport] = {}

    async def create(self, scheduled: ScheduledResearch) -> ScheduledResearch:
        if db_manager.is_connected:
            try:
                await db_manager.db["scheduled_research"].insert_one(scheduled.model_dump(mode="json"))
            except Exception as exc:
                logger.warning(f"[ScheduledResearchRepo] DB insert failed, using memory: {exc}")
                self._schedules[scheduled.id] = scheduled
        else:
            self._schedules[scheduled.id] = scheduled
        return scheduled

    async def get(self, id: str) -> Optional[ScheduledResearch]:
        if db_manager.is_connected:
            try:
                doc = await db_manager.db["scheduled_research"].find_one({"id": id})
                if doc:
                    doc.pop("_id", None)
                    return ScheduledResearch(**doc)
            except Exception as exc:
                logger.warning(f"[ScheduledResearchRepo] DB get failed: {exc}")
        return self._schedules.get(id)

    async def list_by_user(self, user_id: str, limit: int = 50) -> List[ScheduledResearch]:
        if db_manager.is_connected:
            try:
                cursor = db_manager.db["scheduled_research"].find({"user_id": user_id}).sort("created_at", -1).limit(limit)
                docs = await cursor.to_list(length=limit)
                results = []
                for d in docs:
                    d.pop("_id", None)
                    results.append(ScheduledResearch(**d))
                return results
            except Exception as exc:
                logger.warning(f"[ScheduledResearchRepo] DB list failed: {exc}")
        
        items = [s for s in self._schedules.values() if s.user_id == user_id]
        items.sort(key=lambda x: x.created_at, reverse=True)
        return items[:limit]

    async def list_active_due(self, now: Optional[datetime] = None) -> List[ScheduledResearch]:
        check_time = now or datetime.now(timezone.utc)
        all_schedules = []
        if db_manager.is_connected:
            try:
                cursor = db_manager.db["scheduled_research"].find({"is_active": True})
                docs = await cursor.to_list(length=100)
                for d in docs:
                    d.pop("_id", None)
                    all_schedules.append(ScheduledResearch(**d))
            except Exception as exc:
                logger.warning(f"[ScheduledResearchRepo] DB list active failed: {exc}")
                all_schedules = list(self._schedules.values())
        else:
            all_schedules = list(self._schedules.values())

        due = []
        for s in all_schedules:
            if not s.is_active:
                continue
            if s.next_run_at is None or s.next_run_at <= check_time:
                due.append(s)
        return due

    async def update(self, scheduled: ScheduledResearch) -> ScheduledResearch:
        scheduled.updated_at = datetime.now(timezone.utc)
        if db_manager.is_connected:
            try:
                await db_manager.db["scheduled_research"].replace_one(
                    {"id": scheduled.id}, scheduled.model_dump(mode="json")
                )
            except Exception as exc:
                logger.warning(f"[ScheduledResearchRepo] DB update failed: {exc}")
                self._schedules[scheduled.id] = scheduled
        else:
            self._schedules[scheduled.id] = scheduled
        return scheduled

    async def delete(self, id: str) -> bool:
        deleted = False
        if db_manager.is_connected:
            try:
                res = await db_manager.db["scheduled_research"].delete_one({"id": id})
                if res.deleted_count > 0:
                    deleted = True
            except Exception as exc:
                logger.warning(f"[ScheduledResearchRepo] DB delete failed: {exc}")

        if id in self._schedules:
            del self._schedules[id]
            deleted = True
        return deleted

    async def create_change_report(self, report: ScheduledChangeReport) -> ScheduledChangeReport:
        if db_manager.is_connected:
            try:
                await db_manager.db["scheduled_change_reports"].insert_one(report.model_dump(mode="json"))
            except Exception as exc:
                logger.warning(f"[ScheduledResearchRepo] DB insert report failed: {exc}")
                self._change_reports[report.id] = report
        else:
            self._change_reports[report.id] = report
        return report

    async def get_change_report(self, report_id: str) -> Optional[ScheduledChangeReport]:
        if db_manager.is_connected:
            try:
                doc = await db_manager.db["scheduled_change_reports"].find_one({"id": report_id})
                if doc:
                    doc.pop("_id", None)
                    return ScheduledChangeReport(**doc)
            except Exception as exc:
                logger.warning(f"[ScheduledResearchRepo] DB get report failed: {exc}")
        return self._change_reports.get(report_id)

    async def list_change_reports(self, scheduled_id: str, limit: int = 50) -> List[ScheduledChangeReport]:
        if db_manager.is_connected:
            try:
                cursor = db_manager.db["scheduled_change_reports"].find({"scheduled_id": scheduled_id}).sort("created_at", -1).limit(limit)
                docs = await cursor.to_list(length=limit)
                results = []
                for d in docs:
                    d.pop("_id", None)
                    results.append(ScheduledChangeReport(**d))
                return results
            except Exception as exc:
                logger.warning(f"[ScheduledResearchRepo] DB list reports failed: {exc}")

        reports = [r for r in self._change_reports.values() if r.scheduled_id == scheduled_id]
        reports.sort(key=lambda x: x.created_at, reverse=True)
        return reports[:limit]


scheduled_research_repo = ScheduledResearchRepository()
