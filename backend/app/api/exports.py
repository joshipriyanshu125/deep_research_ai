"""
Days 64–66 — Export API Router

Endpoints
---------
GET /export/formats                  — list available formats
GET /export/{research_id}/markdown   — download .md
GET /export/{research_id}/html       — download .html
GET /export/{research_id}/json       — download .json
GET /export/{research_id}/csv        — download .csv
GET /export/{research_id}/pdf        — download .pdf
GET /export/{research_id}/docx       — download .docx
"""

import re
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from app.middleware.auth import require_auth
from app.database.models.user import UserInDB
from app.reports.exporter import report_exporter
from app.database.mongodb import get_database

router = APIRouter(prefix="/export", tags=["Export"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _slug(title: str) -> str:
    """Convert a report title to a safe filename slug."""
    return re.sub(r"[^\w\-]", "_", title.lower())[:60]


async def _get_report(research_id: str):
    """Fetch report from DB or raise 404."""
    from app.database.models.report import ResearchReport
    db = get_database()
    if db is not None:
        doc = await db["research_reports"].find_one(
            {"research_id": research_id}, {"_id": 0}
        )
        if doc:
            return ResearchReport(**doc)

    raise HTTPException(
        status_code=404,
        detail=f"No report found for research_id={research_id!r}. "
               "Ensure the research has completed successfully.",
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/formats", summary="List available export formats")
async def list_formats():
    """Return metadata about all supported export formats."""
    return {
        "formats": [
            {"format": "markdown", "extension": ".md",   "mime": "text/markdown",    "binary": False},
            {"format": "html",     "extension": ".html", "mime": "text/html",         "binary": False},
            {"format": "json",     "extension": ".json", "mime": "application/json",  "binary": False},
            {"format": "csv",      "extension": ".csv",  "mime": "text/csv",          "binary": False},
            {"format": "pdf",      "extension": ".pdf",  "mime": "application/pdf",   "binary": True},
            {"format": "docx",     "extension": ".docx",
             "mime": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
             "binary": True},
        ]
    }


@router.get("/{research_id}/markdown", summary="Download report as Markdown")
async def export_markdown(
    research_id: str,
    _: UserInDB = Depends(require_auth),
):
    report = await _get_report(research_id)
    content = report_exporter.export_as_markdown(report)
    return Response(
        content=content.encode("utf-8"),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{_slug(report.title)}.md"'},
    )


@router.get("/{research_id}/html", summary="Download report as HTML")
async def export_html(
    research_id: str,
    _: UserInDB = Depends(require_auth),
):
    report = await _get_report(research_id)
    content = report_exporter.export_as_html_document(report)
    return Response(
        content=content.encode("utf-8"),
        media_type="text/html; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{_slug(report.title)}.html"'},
    )


@router.get("/{research_id}/json", summary="Download report as JSON")
async def export_json(
    research_id: str,
    _: UserInDB = Depends(require_auth),
):
    report = await _get_report(research_id)
    content = report_exporter.export_as_json(report)
    return Response(
        content=content.encode("utf-8"),
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{_slug(report.title)}.json"'},
    )


@router.get("/{research_id}/csv", summary="Download structured research data as CSV")
async def export_csv(
    research_id: str,
    _: UserInDB = Depends(require_auth),
):
    report = await _get_report(research_id)
    content = report_exporter.export_as_csv(report)
    return Response(
        content=content.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{_slug(report.title)}.csv"'},
    )


@router.get("/{research_id}/pdf", summary="Download report as PDF")
async def export_pdf(
    research_id: str,
    _: UserInDB = Depends(require_auth),
):
    report = await _get_report(research_id)
    try:
        content = report_exporter.export_as_pdf(report)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{_slug(report.title)}.pdf"'},
    )


@router.get("/{research_id}/docx", summary="Download report as DOCX")
async def export_docx(
    research_id: str,
    _: UserInDB = Depends(require_auth),
):
    report = await _get_report(research_id)
    try:
        content = report_exporter.export_as_docx(report)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{_slug(report.title)}.docx"'},
    )
