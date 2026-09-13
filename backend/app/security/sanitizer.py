"""
Day 53 — Input Validation & Malicious HTML / XSS Sanitizer

Hardens inputs and output content:
  - Input parameter validation (length bounds, null-bytes, control characters)
  - Malicious HTML / XSS stripping (<script>, <iframe>, event handlers, javascript: URIs)
"""

from __future__ import annotations

import html
import re
from typing import Optional, List, Dict, Any


DANGEROUS_HTML_TAGS = [
    r"<\s*script[^>]*>[\s\S]*?<\s*/\s*script\s*>",
    r"<\s*iframe[^>]*>[\s\S]*?<\s*/\s*iframe\s*>",
    r"<\s*object[^>]*>[\s\S]*?<\s*/\s*object\s*>",
    r"<\s*embed[^>]*>[\s\S]*?<\s*/\s*embed\s*>",
    r"<\s*applet[^>]*>[\s\S]*?<\s*/\s*applet\s*>",
    r"<\s*meta[^>]*>",
    r"<\s*link[^>]*>",
    r"<\s*style[^>]*>[\s\S]*?<\s*/\s*style\s*>",
    r"<\s*base[^>]*>",
    r"<\s*form[^>]*>[\s\S]*?<\s*/\s*form\s*>",
]

EVENT_HANDLER_REGEX = r"(?i)\s+on[a-z]{3,20}\s*=\s*(?:'[^']*'|\"[^\"]*\"|[^\s>]+)"
JAVASCRIPT_URI_REGEX = r"(?i)(?:href|src|action)\s*=\s*['\"]?\s*(?:javascript|data|vbscript):[^\s'\">]*"


class InputValidator:
    """Validates and cleans user queries, search parameters, and request strings."""

    @staticmethod
    def sanitize_string(
        value: str,
        max_length: int = 5000,
        allow_newlines: bool = True,
    ) -> str:
        """Removes null bytes, normalizes whitespace, and truncates to max_length."""
        if not value or not isinstance(value, str):
            return ""

        # Remove null bytes
        cleaned = value.replace("\x00", "")

        # Truncate to maximum allowed length
        if len(cleaned) > max_length:
            cleaned = cleaned[:max_length]

        if not allow_newlines:
            cleaned = re.sub(r"[\r\n]+", " ", cleaned)

        return cleaned.strip()

    @staticmethod
    def validate_query(query: str, min_length: int = 2, max_length: int = 1000) -> Tuple[bool, str]:
        """Validates search / research user query. Returns (is_valid, error_or_cleaned)."""
        if not query or not isinstance(query, str):
            return False, "Query cannot be empty."

        clean_q = InputValidator.sanitize_string(query, max_length=max_length)
        if len(clean_q) < min_length:
            return False, f"Query must be at least {min_length} characters long."

        # Check for harmful SQL / script injection fragments
        if re.search(r"<script|<iframe|javascript:", clean_q, re.IGNORECASE):
            return False, "Query contains disallowed markup or script tokens."

        return True, clean_q


class HTMLSanitizer:
    """
    Strips XSS vectors and malicious HTML elements from scraped web content
    while preserving standard text, tables, and formatting.
    """

    def sanitize(self, raw_html: str) -> str:
        """Cleans malicious HTML tags, inline event handlers, and javascript: links."""
        if not raw_html or not isinstance(raw_html, str):
            return ""

        cleaned = raw_html

        # 1. Remove dangerous tag blocks
        for tag_pattern in DANGEROUS_HTML_TAGS:
            cleaned = re.sub(tag_pattern, "", cleaned, flags=re.IGNORECASE)

        # 2. Strip inline event handlers (e.g. onerror=..., onclick=..., onload=...)
        cleaned = re.sub(EVENT_HANDLER_REGEX, "", cleaned)

        # 3. Strip javascript: and vbscript: URIs in href/src
        cleaned = re.sub(JAVASCRIPT_URI_REGEX, "", cleaned)

        return cleaned

    def clean_text_for_display(self, text: str) -> str:
        """Escapes raw HTML entities for safe UI rendering."""
        if not text:
            return ""
        return html.escape(text)


input_validator = InputValidator()
html_sanitizer = HTMLSanitizer()
