import io
from app.database.models.report import ResearchReport
from app.reports.formatter import report_formatter


class ReportExporter:
    def export_as_markdown(self, report: ResearchReport) -> str:
        return report_formatter.format_full_markdown(report)

    def export_as_html_document(self, report: ResearchReport) -> str:
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


report_exporter = ReportExporter()
