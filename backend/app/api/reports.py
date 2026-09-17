from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Response, Depends
from app.database.models.report import ResearchReport, Citation, CitationTrace
from app.services.report_service import report_service
from app.database.models.feedback import ReportFeedback, ReportFeedbackCreate
from app.database.repositories.feedback_repo import feedback_repo
from app.database.models.user import UserInDB
from app.middleware.auth import get_current_user

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("/{report_id}", response_model=ResearchReport)
async def get_report(report_id: str):
    return await report_service.get_report_by_id(report_id)

@router.post("/{report_id}/feedback", response_model=ReportFeedback)
async def submit_report_feedback(
    report_id: str,
    request: ReportFeedbackCreate,
    user: Optional[UserInDB] = Depends(get_current_user),
):
    await report_service.get_report_by_id(report_id)
    return await feedback_repo.create(ReportFeedback(
        report_id=report_id, user_id=user.id if user else "anonymous", **request.model_dump(),
    ))

@router.get("/{report_id}/feedback", response_model=List[ReportFeedback])
async def list_report_feedback(report_id: str):
    await report_service.get_report_by_id(report_id)
    return await feedback_repo.list_by_report(report_id)


@router.get("/by-research/{research_id}", response_model=ResearchReport)
async def get_report_by_research(research_id: str):
    return await report_service.get_report_by_research(research_id)


@router.get("/{report_id}/citations", response_model=List[Citation])
async def get_report_citations(report_id: str):
    report = await report_service.get_report_by_id(report_id)
    return report.citations


@router.get("/{report_id}/traceability", response_model=List[CitationTrace])
async def get_report_traceability(report_id: str):
    report = await report_service.get_report_by_id(report_id)
    return report.traceability_matrix


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

