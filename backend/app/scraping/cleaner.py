"""
Day 14 & 15 — HTML Cleaner & Content Normalizer
Cleans raw HTML into well-structured Markdown, stripping navigation, advertisements,
cookie notices, menus, footers, and comments, while preserving headings, tables, and lists.
Applies Unicode, HTML entities, and whitespace normalization.
"""
import re
from typing import Optional, List
from bs4 import BeautifulSoup, Tag
from app.scraping.text_normalizer import text_normalizer


class HTMLCleaner:
    """
    Transforms raw HTML into clean, readable Markdown text:
      - Strips navigation, ads, cookie notices, menus, footers, and comments.
      - Isolates main article body when available.
      - Preserves structural elements: headings (#), tables (|), and lists (- / 1.).
      - Normalizes whitespace, entities, encoding, and duplicate boilerplate.
    """

    # Tag names to strip completely
    _STRIP_TAGS = [
        "script", "style", "nav", "footer", "aside", "header",
        "form", "noscript", "svg", "iframe", "button", "dialog",
        "input", "textarea", "select", "template", "menu", "canvas",
        "audio", "video", "source", "track", "applet", "object", "embed",
    ]

    # CSS selector patterns for ads, cookie notices, comments, and boilerplate widgets
    _NOISE_SELECTORS = [
        # Cookie & Consent banners
        '[class*="cookie"]', '[id*="cookie"]',
        '[class*="consent"]', '[id*="consent"]',
        '[class*="gdpr"]', '[id*="gdpr"]',
        '#onetrust-banner-sdk', '.cc-window',
        # Advertisements & Sponsored Content
        '[class*="advert"]', '[id*="advert"]',
        '[class*="sponsored"]', '[class*="adsbygoogle"]',
        'ins.adsbygoogle', '.ad-banner', '.adbox',
        # Comments & discussions
        '#comments', '.comments', '.comment-list',
        '.comment-section', '#disqus_thread', '.disqus',
        # Navigation & menus
        '[role="navigation"]', '.navbar', '.nav-menu',
        '.header-nav', '.breadcrumbs',
        # Social sharing & newsletters
        '.social-share', '.share-buttons', '.newsletter-signup',
        '.subscribe-box', '.sidebar',
    ]

    # Candidate selectors for the main article content container
    _ARTICLE_SELECTORS = [
        "article", "main", '[role="main"]',
        ".post-content", ".article-body", ".entry-content",
        ".story-body", ".article__content", ".content-article",
    ]

    def clean(self, raw_html: str) -> str:
        """
        Convert raw HTML into normalized markdown text.
        """
        if not raw_html or not isinstance(raw_html, str):
            return ""

        soup = BeautifulSoup(raw_html, "html.parser")

        # 1. Strip unwanted tags by name
        for tag_name in self._STRIP_TAGS:
            for element in soup.find_all(tag_name):
                element.decompose()

        # 2. Strip noise elements by class/id selectors (cookies, ads, comments, nav)
        for selector in self._NOISE_SELECTORS:
            try:
                for noise in soup.select(selector):
                    noise.decompose()
            except Exception:
                continue

        # 3. Try to locate the main article root container
        content_root = self._locate_main_article_root(soup)

        # 4. Transform tables to markdown tables in-place
        for table in content_root.find_all("table"):
            self._convert_table_to_markdown(table)

        # 5. Transform headings to markdown headings in-place
        for level in range(1, 7):
            for h in content_root.find_all(f"h{level}"):
                prefix = "#" * level
                h_text = h.get_text().strip()
                if h_text:
                    h.string = f"\n\n{prefix} {h_text}\n\n"

        # 6. Transform lists to markdown lists in-place
        for ul in content_root.find_all("ul"):
            self._convert_list_to_markdown(ul, ordered=False)

        for ol in content_root.find_all("ol"):
            self._convert_list_to_markdown(ol, ordered=True)

        # 7. Extract raw text with newline separation
        raw_extracted_text = content_root.get_text(separator="\n")

        # 8. Run through comprehensive TextNormalizer (entities, encoding, whitespace, dedup)
        normalized_text = text_normalizer.normalize(raw_extracted_text)

        return normalized_text

    def _locate_main_article_root(self, soup: BeautifulSoup) -> Tag:
        """
        Search for <article>, <main>, or article content classes.
        If a container holds substantial text (>= 100 chars), return it as the extraction root.
        Otherwise fallback to the entire <body> or soup.
        """
        for selector in self._ARTICLE_SELECTORS:
            try:
                candidate = soup.select_one(selector)
                if candidate:
                    cand_text = candidate.get_text(strip=True)
                    if len(cand_text) >= 100:
                        return candidate
            except Exception:
                continue

        return soup.body if soup.body else soup

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

            if is_first_row:
                sep_str = "| " + " | ".join(["---"] * len(row_vals)) + " |"
                table_md_lines.append(sep_str)
                is_first_row = False

        if table_md_lines:
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
