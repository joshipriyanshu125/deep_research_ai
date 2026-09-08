from fastapi import APIRouter, HTTPException, Response
from app.database.models.report import ResearchReport
from app.services.report_service import report_service

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("/{report_id}", response_model=ResearchReport)
async def get_report(report_id: str):
    return await report_service.get_report_by_id(report_id)


@router.get("/by-research/{research_id}", response_model=ResearchReport)
async def get_report_by_research(research_id: str):
    return await report_service.get_report_by_research(research_id)


@router.get("/{report_id}/export/markdown")
async def export_report_markdown(report_id: str):
    report = await report_service.get_report_by_id(report_id)
    md_content = report_service.export_markdown(report)
    return Response(
        content=md_content,
        media_type="text/markdown",
        headers={"Content-Disposition": f"attachment; filename=report_{report_id}.md"}
    )


@router.get("/{report_id}/export/html")
async def export_report_html(report_id: str):
    report = await report_service.get_report_by_id(report_id)
    html_content = report_service.export_html(report)
    return Response(
        content=html_content,
        media_type="text/html",
        headers={"Content-Disposition": f"attachment; filename=report_{report_id}.html"}
    )
