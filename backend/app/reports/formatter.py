import markdown
from app.database.models.report import ResearchReport
from app.research.citation import citation_engine


class ReportFormatter:
    def format_full_markdown(self, report: ResearchReport) -> str:
        md = f"# {report.title}\n\n"
        md += f"> **Executive Summary**: {report.executive_summary}\n\n"
        
        if report.key_findings:
            md += "### Key Discoveries\n"
            for kf in report.key_findings:
                md += f"- {kf}\n"
            md += "\n"
            
        body = report.markdown_content or ""
        md += citation_engine.append_bibliography_if_missing(body, report.citations)
        return md

    def format_html(self, report: ResearchReport) -> str:
        md_text = self.format_full_markdown(report)
        return markdown.markdown(md_text, extensions=["tables", "fenced_code", "toc"])


report_formatter = ReportFormatter()

