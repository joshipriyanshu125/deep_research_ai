from typing import Optional, List
from fastapi import HTTPException
from app.database.models.report import ResearchReport
from app.database.repositories.report_repo import report_repo
from app.reports.exporter import report_exporter


class ReportService:
    async def get_report_by_id(self, report_id: str) -> ResearchReport:
        report = await report_repo.get_by_id(report_id)
        if not report:
            raise HTTPException(status_code=404, detail="Report not found")
        return report

    async def get_report_by_research(self, research_id: str) -> ResearchReport:
        report = await report_repo.get_by_research_id(research_id)
        if not report:
            raise HTTPException(status_code=404, detail="Report not found for this research")
        return report

    async def list_reports(self, limit: int = 50) -> List[ResearchReport]:
        return await report_repo.list_all(limit=limit)

    def export_markdown(self, report: ResearchReport) -> str:
        return report_exporter.export_as_markdown(report)

    def export_html(self, report: ResearchReport) -> str:
        return report_exporter.export_as_html_document(report)


report_service = ReportService()
