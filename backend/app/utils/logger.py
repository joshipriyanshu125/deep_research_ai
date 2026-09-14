"""
Day 56 — Structured Logging

Upgrades the logger to emit structured JSON records so every log line can be
parsed by log-aggregation systems (Loki, ELK, Cloud Logging, etc.).

Schema:
    {
      "timestamp": "2026-09-14T09:00:00.000Z",
      "level": "INFO",
      "service": "research-agent",
      "research_id": "...",   # optional – set via get_logger() or LogContext
      "task_id": "...",       # optional
      "event": "...",         # optional – short machine-readable tag
      "logger": "deep_research",
      "message": "..."
    }

Usage:
    # Global singleton (backward-compatible)
    from app.utils.logger import logger
    logger.info("plain message")

    # Context-bound logger (recommended for agent code)
    from app.utils.logger import get_logger
    log = get_logger("research.planner", research_id="r_123", task_id="t_456")
    log.info("Planner started", extra={"event": "planner_started"})

    # Temporary context override via LogContext
    from app.utils.logger import LogContext
    with LogContext(research_id="r_999"):
        logger.info("inside context")
"""

import json
import logging
import sys
import threading
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Optional

from app.config.settings import settings
from app.security.logging_filter import SensitiveDataFilter

# ---------------------------------------------------------------------------
# Context variables – propagated across async tasks automatically
# ---------------------------------------------------------------------------

_ctx_research_id: ContextVar[Optional[str]] = ContextVar("research_id", default=None)
_ctx_task_id: ContextVar[Optional[str]] = ContextVar("task_id", default=None)
_ctx_event: ContextVar[Optional[str]] = ContextVar("event", default=None)


class LogContext:
    """
    Async-safe context manager that binds research / task IDs to the log context.

    Example::

        async with LogContext(research_id="r_abc", task_id="t_1"):
            logger.info("Processing source")   # will include research_id + task_id
    """

    def __init__(
        self,
        research_id: Optional[str] = None,
        task_id: Optional[str] = None,
        event: Optional[str] = None,
    ):
        self._research_id = research_id
        self._task_id = task_id
        self._event = event
        self._tokens: list = []

    def __enter__(self):
        if self._research_id is not None:
            self._tokens.append(_ctx_research_id.set(self._research_id))
        if self._task_id is not None:
            self._tokens.append(_ctx_task_id.set(self._task_id))
        if self._event is not None:
            self._tokens.append(_ctx_event.set(self._event))
        return self

    def __exit__(self, *_):
        for tok in reversed(self._tokens):
            tok.var.reset(tok)

    # Also support `async with`
    async def __aenter__(self):
        return self.__enter__()

    async def __aexit__(self, *args):
        self.__exit__(*args)


# ---------------------------------------------------------------------------
# JSON formatter
# ---------------------------------------------------------------------------

class StructuredJsonFormatter(logging.Formatter):
    """
    Formats log records as single-line JSON objects suitable for structured
    log ingestion (Loki, Cloud Logging, ELK, etc.).

    Extra keys accepted on every record:
        event        – short machine-readable tag (e.g. "source_processed")
        research_id  – overrides context-var value
        task_id      – overrides context-var value
    """

    SERVICE_NAME = "research-agent"

    def format(self, record: logging.LogRecord) -> str:  # type: ignore[override]
        message = record.getMessage()

        # Resolve context fields (record extra > context-var > None)
        research_id = getattr(record, "research_id", None) or _ctx_research_id.get()
        task_id = getattr(record, "task_id", None) or _ctx_task_id.get()
        event = getattr(record, "event", None) or _ctx_event.get()

        payload: dict = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "service": self.SERVICE_NAME,
            "logger": record.name,
            "message": message,
        }

        if research_id:
            payload["research_id"] = research_id
        if task_id:
            payload["task_id"] = task_id
        if event:
            payload["event"] = event

        # Attach exception info if present
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Logger factory
# ---------------------------------------------------------------------------

_lock = threading.Lock()
_loggers: dict = {}


def setup_logger(name: str = "deep_research") -> logging.Logger:
    """
    Build or return a cached structured logger.

    This replaces the old plain-text setup while keeping the same call
    signature so existing imports keep working.
    """
    with _lock:
        if name in _loggers:
            return _loggers[name]

        log = logging.getLogger(name)
        log.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)
        log.propagate = False

        if not log.handlers:
            handler = logging.StreamHandler(sys.stdout)
            handler.addFilter(SensitiveDataFilter())
            handler.setFormatter(StructuredJsonFormatter())
            log.addHandler(handler)

        _loggers[name] = log
        return log


def get_logger(
    name: str = "deep_research",
    *,
    research_id: Optional[str] = None,
    task_id: Optional[str] = None,
) -> logging.Logger:
    """
    Return a structured logger.  Optionally sets context-var fields that will
    appear on every log record emitted while those vars are active.

    Example::

        log = get_logger("research.executor", research_id="r_abc")
        log.info("Evidence extracted", extra={"event": "evidence_extracted"})
    """
    log = setup_logger(name)
    if research_id is not None:
        _ctx_research_id.set(research_id)
    if task_id is not None:
        _ctx_task_id.set(task_id)
    return log


# ---------------------------------------------------------------------------
# Module-level singleton — kept 100% backward-compatible
# ---------------------------------------------------------------------------

logger = setup_logger()
