"""
Day 14 — HTML Cleaner & Structure Preserver
Cleans raw HTML into well-structured Markdown, preserving headings (H1-H6),
tables (markdown table syntax), and lists (bullet and numbered lists).
"""
import re
from typing import Optional
from bs4 import BeautifulSoup, Tag, NavigableString


class HTMLCleaner:
    """
    Cleans raw HTML into readable Markdown text while preserving
    structural elements: headings, tables, and lists.
    """

    # Unwanted elements to strip completely
    _STRIP_TAGS = {
        "script", "style", "nav", "footer", "aside", "header",
        "form", "noscript", "svg", "iframe", "button", "dialog",
        "input", "textarea", "select", "template", "menu",
    }

    def clean(self, raw_html: str) -> str:
        """
        Convert raw HTML to clean markdown text preserving headings, tables, and lists.
        """
        if not raw_html or not isinstance(raw_html, str):
            return ""

        soup = BeautifulSoup(raw_html, "html.parser")

        # 1. Remove unwanted tags
        for element in soup.find_all(list(self._STRIP_TAGS)):
            element.decompose()

        # 2. Transform tables to markdown tables in-place
        for table in soup.find_all("table"):
            self._convert_table_to_markdown(table)

        # 3. Transform headings to markdown headings in-place
        for level in range(1, 7):
            for h in soup.find_all(f"h{level}"):
                prefix = "#" * level
                h_text = h.get_text().strip()
                if h_text:
                    h.string = f"\n\n{prefix} {h_text}\n\n"

        # 4. Transform lists to markdown lists in-place
        for ul in soup.find_all("ul"):
            self._convert_list_to_markdown(ul, ordered=False)

        for ol in soup.find_all("ol"):
            self._convert_list_to_markdown(ol, ordered=True)

        # 5. Extract text
        text = soup.get_text(separator="\n")

        # 6. Normalize whitespace
        lines = [line.strip() for line in text.splitlines()]
        cleaned = "\n".join(lines)
        # Collapse multiple empty lines
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        return cleaned.strip()

    def _convert_table_to_markdown(self, table: Tag) -> None:
        """Convert a BeautifulSoup <table> tag to formatted markdown text."""
        rows = table.find_all("tr")
        if not rows:
            table.decompose()
            return

        table_md_lines = []
        is_first_row = True
        col_count = 0

        for r in rows:
            # Check headers or data cells
            headers = r.find_all("th")
            cells = r.find_all("td")

            if headers:
                row_vals = [h.get_text().strip().replace("|", "\\|") for h in headers]
            elif cells:
                row_vals = [c.get_text().strip().replace("|", "\\|") for c in cells]
            else:
                continue

            if not row_vals or not any(row_vals):
                continue

            col_count = max(col_count, len(row_vals))
            row_str = "| " + " | ".join(row_vals) + " |"
            table_md_lines.append(row_str)

            # Insert separator after header row
            if is_first_row:
                sep_str = "| " + " | ".join(["---"] * len(row_vals)) + " |"
                table_md_lines.append(sep_str)
                is_first_row = False

        if table_md_lines:
            # If no header was present, make sure first row gets a separator
            if is_first_row and col_count > 0:
                sep_str = "| " + " | ".join(["---"] * col_count) + " |"
                table_md_lines.insert(1, sep_str)

            md_content = "\n\n" + "\n".join(table_md_lines) + "\n\n"
            table.string = md_content
        else:
            table.decompose()

    def _convert_list_to_markdown(self, list_tag: Tag, ordered: bool = False) -> None:
        """Convert <ul> or <ol> into markdown bulleted/numbered items."""
        items = list_tag.find_all("li", recursive=False)
        if not items:
            return

        md_items = []
        for idx, li in enumerate(items, 1):
            li_text = li.get_text().strip()
            if not li_text:
                continue
            if ordered:
                md_items.append(f"{idx}. {li_text}")
            else:
                md_items.append(f"- {li_text}")

        if md_items:
            list_tag.string = "\n\n" + "\n".join(md_items) + "\n\n"


html_cleaner = HTMLCleaner()
