from typing import Optional, List, Dict
from app.database.mongodb import db_manager
from app.database.models.report import ResearchReport


class ReportRepository:
    def __init__(self):
        self._reports: Dict[str, ResearchReport] = {}

    async def create(self, report: ResearchReport) -> ResearchReport:
        if db_manager.is_connected:
            await db_manager.db.reports.insert_one(report.model_dump())
        else:
            self._reports[report.id] = report
        return report

    async def get_by_id(self, report_id: str) -> Optional[ResearchReport]:
        if db_manager.is_connected:
            doc = await db_manager.db.reports.find_one({"id": report_id})
            return ResearchReport(**doc) if doc else None
        return self._reports.get(report_id)

    async def get_by_research_id(self, research_id: str) -> Optional[ResearchReport]:
        if db_manager.is_connected:
            doc = await db_manager.db.reports.find_one({"research_id": research_id})
            return ResearchReport(**doc) if doc else None
        for r in self._reports.values():
            if r.research_id == research_id:
                return r
        return None

    async def list_all(self, limit: int = 50) -> List[ResearchReport]:
        if db_manager.is_connected:
            cursor = db_manager.db.reports.find().sort("created_at", -1).limit(limit)
            return [ResearchReport(**doc) async for doc in cursor]
        reports = list(self._reports.values())
        reports.sort(key=lambda x: x.created_at, reverse=True)
        return reports[:limit]


report_repo = ReportRepository()
