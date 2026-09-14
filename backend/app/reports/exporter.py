"""
Days 64–66 — Export System

Supported formats:
  - Markdown   (.md)    — always available
  - HTML       (.html)  — always available
  - JSON       (.json)  — always available
  - CSV        (.csv)   — always available (structured metadata)
  - PDF        (.pdf)   — requires reportlab
  - DOCX       (.docx)  — requires python-docx
"""

import csv
import io
import json
import textwrap
from datetime import datetime, timezone
from typing import Any, Dict

import markdown as _md_lib

from app.database.models.report import ResearchReport
from app.reports.formatter import report_formatter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _utcnow_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Exporter
# ---------------------------------------------------------------------------

class ReportExporter:
    """Export a ResearchReport to multiple formats."""

    # ------------------------------------------------------------------ #
    # Markdown
    # ------------------------------------------------------------------ #

    def export_as_markdown(self, report: ResearchReport) -> str:
        """Return the full report as a Markdown string."""
        return report_formatter.format_full_markdown(report)

    # ------------------------------------------------------------------ #
    # HTML
    # ------------------------------------------------------------------ #

    def export_as_html_document(self, report: ResearchReport) -> str:
        """Return a self-contained HTML document."""
        body_html = report_formatter.format_html(report)
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>{report.title}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            line-height: 1.6;
            color: #1a202c;
            max-width: 900px;
            margin: 40px auto;
            padding: 0 20px;
        }}
        h1, h2, h3 {{ color: #2d3748; }}
        blockquote {{
            border-left: 4px solid #4299e1;
            padding-left: 1rem;
            color: #4a5568;
            margin: 1rem 0;
        }}
        code {{ background: #edf2f7; padding: 2px 6px; border-radius: 4px; }}
        table {{ width: 100%; border-collapse: collapse; margin: 1.5rem 0; }}
        th, td {{ border: 1px solid #e2e8f0; padding: 8px 12px; text-align: left; }}
        th {{ background-color: #f7fafc; }}
    </style>
</head>
<body>
    {body_html}
</body>
</html>"""

    # ------------------------------------------------------------------ #
    # JSON
    # ------------------------------------------------------------------ #

    def export_as_json(self, report: ResearchReport, indent: int = 2) -> str:
        """Return the full structured report as a JSON string."""
        data = report.to_dict()
        data["exported_at"] = _utcnow_iso()
        return json.dumps(data, indent=indent, ensure_ascii=False, default=str)

    # ------------------------------------------------------------------ #
    # CSV  (structured metadata — one row per section / finding)
    # ------------------------------------------------------------------ #

    def export_as_csv(self, report: ResearchReport) -> str:
        """
        Export structured research data as CSV.
        Produces one CSV file with multiple logical sections separated
        by blank rows (like Excel would show them).
        """
        buf = io.StringIO()
        writer = csv.writer(buf, quoting=csv.QUOTE_ALL)

        # Header metadata
        writer.writerow(["report_id", "research_id", "title", "quality_score",
                         "confidence", "created_at", "exported_at"])
        writer.writerow([
            report.id, report.research_id, report.title,
            report.quality_score, report.confidence,
            report.created_at.isoformat() if hasattr(report.created_at, "isoformat") else str(report.created_at),
            _utcnow_iso(),
        ])
        writer.writerow([])

        # Key findings
        if report.key_findings:
            writer.writerow(["#", "key_finding"])
            for i, kf in enumerate(report.key_findings, 1):
                writer.writerow([i, kf])
            writer.writerow([])

        # Citations / sources
        if report.citations:
            writer.writerow(["citation_index", "title", "url", "domain", "source_type"])
            for c in report.citations:
                writer.writerow([c.index, c.title, c.url, c.domain or "", c.source_type])
            writer.writerow([])

        # Recommendations
        if report.recommendations:
            writer.writerow(["#", "recommendation"])
            for i, r in enumerate(report.recommendations, 1):
                writer.writerow([i, r])
            writer.writerow([])

        # Risks
        if report.risks:
            writer.writerow(["#", "risk"])
            for i, r in enumerate(report.risks, 1):
                writer.writerow([i, r])

        return buf.getvalue()

    # ------------------------------------------------------------------ #
    # PDF  (requires reportlab)
    # ------------------------------------------------------------------ #

    def export_as_pdf(self, report: ResearchReport) -> bytes:
        """
        Export the report as a PDF binary (bytes).

        Requires:  pip install reportlab
        """
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import mm
            from reportlab.platypus import (
                Paragraph, Spacer, SimpleDocTemplate, Table, TableStyle,
                HRFlowable,
            )
        except ImportError:
            raise RuntimeError(
                "reportlab is required for PDF export. "
                "Install it: pip install reportlab"
            )

        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf, pagesize=A4,
            leftMargin=20 * mm, rightMargin=20 * mm,
            topMargin=20 * mm, bottomMargin=20 * mm,
        )

        styles = getSampleStyleSheet()
        style_h1 = ParagraphStyle(
            "H1", parent=styles["Heading1"], fontSize=18, spaceAfter=6,
            textColor=colors.HexColor("#2d3748"),
        )
        style_h2 = ParagraphStyle(
            "H2", parent=styles["Heading2"], fontSize=13, spaceAfter=4,
            textColor=colors.HexColor("#4a5568"),
        )
        style_body = ParagraphStyle(
            "Body", parent=styles["Normal"], fontSize=10, leading=14,
            spaceAfter=6,
        )
        style_bullet = ParagraphStyle(
            "Bullet", parent=style_body, leftIndent=12, bulletIndent=4,
        )
        style_small = ParagraphStyle(
            "Small", parent=style_body, fontSize=8, textColor=colors.grey,
        )

        story = []

        # Title
        story.append(Paragraph(report.title, style_h1))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#e2e8f0")))
        story.append(Spacer(1, 4 * mm))

        # Meta
        story.append(Paragraph(
            f"Quality score: {report.quality_score:.1f} | "
            f"Confidence: {report.confidence:.0%} | "
            f"Exported: {_utcnow_iso()[:10]}",
            style_small,
        ))
        story.append(Spacer(1, 4 * mm))

        # Executive summary
        story.append(Paragraph("Executive Summary", style_h2))
        story.append(Paragraph(_safe_para(report.executive_summary), style_body))
        story.append(Spacer(1, 4 * mm))

        # Key findings
        if report.key_findings:
            story.append(Paragraph("Key Findings", style_h2))
            for kf in report.key_findings:
                story.append(Paragraph(f"• {_safe_para(kf)}", style_bullet))
            story.append(Spacer(1, 4 * mm))

        # Sections
        for section in report.sections:
            story.append(Paragraph(_safe_para(section.title), style_h2))
            for para in section.content.split("\n\n"):
                if para.strip():
                    story.append(Paragraph(_safe_para(para.strip()), style_body))
            story.append(Spacer(1, 3 * mm))

        # Recommendations
        if report.recommendations:
            story.append(Paragraph("Recommendations", style_h2))
            for rec in report.recommendations:
                story.append(Paragraph(f"• {_safe_para(rec)}", style_bullet))
            story.append(Spacer(1, 4 * mm))

        # Citations table
        if report.citations:
            story.append(Paragraph("Sources", style_h2))
            table_data = [["#", "Title", "Domain"]]
            for c in report.citations[:30]:  # cap at 30 for readability
                table_data.append([
                    str(c.index),
                    textwrap.shorten(c.title, 60),
                    c.domain or "",
                ])
            tbl = Table(table_data, colWidths=[12 * mm, None, 40 * mm])
            tbl.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f7fafc")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#2d3748")),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7fafc")]),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#e2e8f0")),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ]))
            story.append(tbl)

        doc.build(story)
        return buf.getvalue()

    # ------------------------------------------------------------------ #
    # DOCX  (requires python-docx)
    # ------------------------------------------------------------------ #

    def export_as_docx(self, report: ResearchReport) -> bytes:
        """
        Export the report as a .docx binary (bytes).

        Requires:  pip install python-docx
        """
        try:
            from docx import Document
            from docx.shared import Pt, RGBColor, Inches
            from docx.enum.text import WD_ALIGN_PARAGRAPH
        except ImportError:
            raise RuntimeError(
                "python-docx is required for DOCX export. "
                "Install it: pip install python-docx"
            )

        doc = Document()

        # Styles
        title_para = doc.add_heading(report.title, level=0)
        title_para.runs[0].font.color.rgb = RGBColor(0x2d, 0x37, 0x48)

        doc.add_paragraph(
            f"Quality: {report.quality_score:.1f}  |  "
            f"Confidence: {report.confidence:.0%}  |  "
            f"Exported: {_utcnow_iso()[:10]}"
        ).runs[0].font.size = Pt(9)

        doc.add_heading("Executive Summary", level=1)
        doc.add_paragraph(report.executive_summary)

        if report.key_findings:
            doc.add_heading("Key Findings", level=1)
            for kf in report.key_findings:
                doc.add_paragraph(kf, style="List Bullet")

        for section in report.sections:
            doc.add_heading(section.title, level=2)
            for para in section.content.split("\n\n"):
                if para.strip():
                    doc.add_paragraph(para.strip())

        if report.recommendations:
            doc.add_heading("Recommendations", level=1)
            for rec in report.recommendations:
                doc.add_paragraph(rec, style="List Bullet")

        if report.risks:
            doc.add_heading("Risks", level=1)
            for risk in report.risks:
                doc.add_paragraph(risk, style="List Bullet")

        if report.citations:
            doc.add_heading("Sources", level=1)
            tbl = doc.add_table(rows=1, cols=3)
            tbl.style = "Table Grid"
            hdr = tbl.rows[0].cells
            hdr[0].text = "#"
            hdr[1].text = "Title"
            hdr[2].text = "URL"
            for c in report.citations:
                row = tbl.add_row().cells
                row[0].text = str(c.index)
                row[1].text = c.title
                row[2].text = c.url

        buf = io.BytesIO()
        doc.save(buf)
        return buf.getvalue()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_para(text: str) -> str:
    """Strip markdown syntax that confuses ReportLab XML parser."""
    import re
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"#{1,6}\s*", "", text)
    text = text.replace("<", "&lt;").replace(">", "&gt;").replace("&", "&amp;")
    return text.strip()


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

report_exporter = ReportExporter()
