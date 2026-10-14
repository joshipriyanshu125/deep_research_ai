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
            if not doc:
                return None
            try:
                return ResearchReport(**doc)
            except Exception:
                # Written by the Node backend with a different schema.
                return None
        return self._reports.get(report_id)

    async def get_by_research_id(self, research_id: str) -> Optional[ResearchReport]:
        if db_manager.is_connected:
            doc = await db_manager.db.reports.find_one({"research_id": research_id})
            if not doc:
                return None
            try:
                return ResearchReport(**doc)
            except Exception:
                return None
        for r in self._reports.values():
            if r.research_id == research_id:
                return r
        return None

    async def delete(self, report_id: str) -> bool:
        if db_manager.is_connected:
            res = await db_manager.db.reports.delete_one({"id": report_id})
            return res.deleted_count > 0
        deleted = report_id in self._reports
        self._reports.pop(report_id, None)
        return deleted

    async def list_all(self, limit: int = 50) -> List[ResearchReport]:
        if db_manager.is_connected:
            cursor = db_manager.db.reports.find().sort("created_at", -1).limit(limit)
            reports: List[ResearchReport] = []
            async for doc in cursor:
                # The Node backend writes report documents into this same
                # collection with a different shape (no research_id, uses
                # markdown/content fields). Skip anything that cannot be
                # coerced so one foreign document never 500s the archive.
                try:
                    reports.append(ResearchReport(**doc))
                except Exception:
                    continue
            return reports
        reports = list(self._reports.values())
        reports.sort(key=lambda x: x.created_at, reverse=True)
        return reports[:limit]


report_repo = ReportRepository()
