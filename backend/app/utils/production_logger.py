"""
Day 96–100 — Production Deployment: Structured JSON Logging

Production-ready structured logger that formats log entries as JSON for
centralized ingestion (ELK, Datadog, CloudWatch, Loki, Promtail).
Includes sensitive token redaction and contextual request tracing.
"""

from __future__ import annotations

import datetime
import json
import logging
import re
import sys
import traceback
from typing import Any, Dict

SENSITIVE_PATTERNS = [
    re.compile(r"(api[_-]?key[\"'\s:=]+)([\w\-]{8,})", re.IGNORECASE),
    re.compile(r"(secret[\"'\s:=]+)([\w\-]{8,})", re.IGNORECASE),
    re.compile(r"(password[\"'\s:=]+)([\w\-]{6,})", re.IGNORECASE),
    re.compile(r"(bearer\s+)([\w\-\.]{12,})", re.IGNORECASE),
    re.compile(r"(authorization[\"'\s:=]+)([\w\-\.]{12,})", re.IGNORECASE),
]


def redact_sensitive_data(message: str) -> str:
    """Mask credentials and sensitive tokens in log text."""
    if not isinstance(message, str):
        return message
    result = message
    for pattern in SENSITIVE_PATTERNS:
        result = pattern.sub(r"\1***REDACTED***", result)
    return result


class JSONLogFormatter(logging.Formatter):
    """
    Formats standard Python log records into JSON strings.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_obj: Dict[str, Any] = {
            "timestamp": datetime.datetime.fromtimestamp(
                record.created, tz=datetime.timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": redact_sensitive_data(record.getMessage()),
            "module": record.module,
            "line": record.lineno,
            "process": record.process,
            "thread": record.threadName,
        }

        # Include custom request ID / user ID if present on record
        if hasattr(record, "request_id"):
            log_obj["request_id"] = getattr(record, "request_id")
        if hasattr(record, "user_id"):
            log_obj["user_id"] = getattr(record, "user_id")

        # Include exception tracebacks
        if record.exc_info:
            log_obj["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else "Exception",
                "message": str(record.exc_info[1]),
                "traceback": traceback.format_exception(*record.exc_info),
            }

        return json.dumps(log_obj, default=str)


def setup_production_logging(log_level: str = "INFO", use_json: bool = True) -> logging.Logger:
    """Configure root logger with stdout JSON handler."""
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Remove existing handlers to avoid duplicates
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    if use_json:
        handler.setFormatter(JSONLogFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] [%(name)s] %(message)s")
        )

    root_logger.addHandler(handler)
    return root_logger
