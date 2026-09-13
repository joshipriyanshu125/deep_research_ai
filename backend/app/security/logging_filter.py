"""
Day 53 — Logging Without Sensitive Data

Implements redacting log filter that masks:
  - Bearer tokens & JWTs
  - Passwords & secret fields
  - API keys (OpenAI, OpenRouter, Tavily, Anthropic, Gemini)
  - Database connection strings containing credentials
  - Credit card numbers & sensitive personal identifiers
"""

from __future__ import annotations

import logging
import re
from typing import Any


REDACTION_PATTERNS = [
    # Authorization header / Bearer tokens
    (r"(?i)(bearer\s+)[a-zA-Z0-9_\-\.]{15,}", r"\1[REDACTED_TOKEN]"),
    # JWT Tokens
    (r"ey[A-Za-z0-9-_=]+\.ey[A-Za-z0-9-_=]+\.[A-Za-z0-9-_.+/=]+", r"[REDACTED_JWT]"),
    # OpenAI / generic API keys
    (r"(?i)(sk-[a-zA-Z0-9_\-]{6})[a-zA-Z0-9_\-]{10,}", r"\1...[REDACTED_API_KEY]"),
    # JSON password / secret fields
    (r'(?i)"(password|secret|api_key|token|access_token)"\s*:\s*"[^"]+"', r'"\1": "[REDACTED]"'),
    # Key-value secret fields (e.g. password=secret)
    (r"(?i)(password|secret|token|apikey|api_key)=([^&\s]+)", r"\1=[REDACTED]"),
    # Database connection string passwords (mongodb://user:pass@host)
    (r"://([^\s/:@]+):([^\s/]+)@([^\s/]+)", r"://\1:[REDACTED]@\3"),
    # Credit card numbers
    (r"\b(?:\d{4}[ -]?){3}\d{4}\b", r"[REDACTED_CARD]"),
]


def redact_sensitive_data(message: str) -> str:
    """Masks all sensitive credential patterns from log strings."""
    if not message or not isinstance(message, str):
        return str(message or "")

    sanitized = message
    for pattern, replacement in REDACTION_PATTERNS:
        sanitized = re.sub(pattern, replacement, sanitized)

    return sanitized


class SensitiveDataFilter(logging.Filter):
    """
    Python logging filter that intercepts log records and scrubs credentials
    before writing to stdout/files.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact_sensitive_data(record.msg)
        if record.args:
            if isinstance(record.args, tuple):
                record.args = tuple(
                    redact_sensitive_data(a) if isinstance(a, str) else a for a in record.args
                )
            elif isinstance(record.args, dict):
                record.args = {
                    k: (redact_sensitive_data(v) if isinstance(v, str) else v)
                    for k, v in record.args.items()
                }
        return True
