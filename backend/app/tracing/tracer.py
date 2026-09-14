"""
Day 58 — Observability / Distributed Tracing

Lightweight span-based tracer.  No OpenTelemetry or third-party dependencies —
uses only Python's ``contextvars`` for async-safe context propagation.

Trace shape (matches the task spec)::

    Research (trace_id="t_abc")
     ├── Planner
     │    └── LLM call
     │
     ├── Task 1
     │    ├── Search
     │    ├── Scrape
     │    └── LLM
     │
     ├── Task 2
     │    ├── Search
     │    └── Paper extraction
     │
     └── Synthesis
          └── LLM

Usage::

    from app.tracing.tracer import start_span, end_span, trace_store

    trace_id = "research_abc"

    with start_span("Research", trace_id=trace_id) as root:
        with start_span("Planner", trace_id=trace_id):
            with start_span("LLM call", trace_id=trace_id):
                pass  # do actual LLM work here

    tree = trace_store.get_trace_tree(trace_id)

Or as async context manager::

    async with start_span("Research", trace_id=trace_id):
        ...
"""

from __future__ import annotations

import threading
import time
import uuid
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Span:
    """
    A single unit of work within a trace.

    Attributes
    ----------
    span_id    : unique ID for this span
    trace_id   : links all spans in one research request
    parent_id  : span_id of the enclosing span, or None for the root
    name       : human-readable operation name
    start_time : epoch seconds (float)
    end_time   : epoch seconds or None while span is open
    metadata   : arbitrary key-value data attached to this span
    children   : child spans (populated by TraceStore)
    """

    span_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    trace_id: str = ""
    parent_id: Optional[str] = None
    name: str = ""
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    children: List["Span"] = field(default_factory=list)

    # ------------------------------------------------------------------ #

    def finish(self, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Mark the span as complete."""
        self.end_time = time.time()
        if metadata:
            self.metadata.update(metadata)

    @property
    def duration_ms(self) -> Optional[float]:
        if self.end_time is None:
            return None
        return round((self.end_time - self.start_time) * 1000, 3)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "span_id": self.span_id,
            "trace_id": self.trace_id,
            "parent_id": self.parent_id,
            "name": self.name,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": self.duration_ms,
            "metadata": self.metadata,
            "children": [c.to_dict() for c in self.children],
        }


@dataclass
class ResearchTrace:
    """Container for all spans belonging to one research request."""

    trace_id: str
    spans: List[Span] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    def add_span(self, span: Span) -> None:
        self.spans.append(span)

    def get_root_span(self) -> Optional[Span]:
        """Return the span with no parent (root of the tree)."""
        for s in self.spans:
            if s.parent_id is None:
                return s
        return None

    def build_tree(self) -> Optional[Dict[str, Any]]:
        """Build a nested dict tree from flat span list."""
        index: Dict[str, Span] = {s.span_id: s for s in self.spans}
        # Clear previously built children to avoid duplicates on re-call
        for span in self.spans:
            span.children = []
        # Attach children
        for span in self.spans:
            if span.parent_id and span.parent_id in index:
                index[span.parent_id].children.append(span)
        root = self.get_root_span()
        return root.to_dict() if root else None


# ---------------------------------------------------------------------------
# Context variables
# ---------------------------------------------------------------------------

_ctx_trace_id: ContextVar[Optional[str]] = ContextVar("trace_id", default=None)
_ctx_span_id: ContextVar[Optional[str]] = ContextVar("span_id", default=None)


def current_trace_id() -> Optional[str]:
    """Return the active trace ID from the current async context."""
    return _ctx_trace_id.get()


# ---------------------------------------------------------------------------
# TraceStore — in-memory trace registry
# ---------------------------------------------------------------------------

class TraceStore:
    """Thread-safe in-memory store for all active and completed traces."""

    def __init__(self, max_traces: int = 1000) -> None:
        self._lock = threading.Lock()
        self._traces: Dict[str, ResearchTrace] = {}
        self._max = max_traces

    def get_or_create(self, trace_id: str) -> ResearchTrace:
        with self._lock:
            if trace_id not in self._traces:
                if len(self._traces) >= self._max:
                    # Evict oldest
                    oldest = min(self._traces.values(), key=lambda t: t.created_at)
                    del self._traces[oldest.trace_id]
                self._traces[trace_id] = ResearchTrace(trace_id=trace_id)
            return self._traces[trace_id]

    def add_span(self, span: Span) -> None:
        trace = self.get_or_create(span.trace_id)
        trace.add_span(span)

    def get_trace(self, trace_id: str) -> Optional[ResearchTrace]:
        with self._lock:
            return self._traces.get(trace_id)

    def get_trace_tree(self, trace_id: str) -> Optional[Dict[str, Any]]:
        """Return the full nested span tree for a trace ID."""
        trace = self.get_trace(trace_id)
        if trace is None:
            return None
        return trace.build_tree()

    def list_traces(self) -> List[str]:
        with self._lock:
            return list(self._traces.keys())

    def clear(self) -> None:
        with self._lock:
            self._traces.clear()


# Module-level singleton
trace_store = TraceStore()


# ---------------------------------------------------------------------------
# TraceContext — sync / async context manager
# ---------------------------------------------------------------------------

class TraceContext:
    """
    Context manager that opens a span, sets context vars, and closes the span
    on exit.  Works as both ``with`` and ``async with``.

    Example::

        with TraceContext("Planner", trace_id="r_abc") as span:
            # span is open here
            pass
        # span is closed, duration recorded

    The outermost span has no parent.  Nested calls automatically wire
    parent_id from the enclosing context.
    """

    def __init__(
        self,
        name: str,
        trace_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._name = name
        self._trace_id = trace_id
        self._metadata = metadata or {}
        self._span: Optional[Span] = None
        self._tokens: list = []

    def __enter__(self) -> Span:
        parent_id = _ctx_span_id.get()
        self._span = Span(
            name=self._name,
            trace_id=self._trace_id,
            parent_id=parent_id,
            metadata=dict(self._metadata),
        )
        trace_store.add_span(self._span)

        # Push context
        self._tokens.append(_ctx_trace_id.set(self._trace_id))
        self._tokens.append(_ctx_span_id.set(self._span.span_id))
        return self._span

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._span is not None:
            if exc_type is not None:
                self._span.metadata["error"] = str(exc_val)
            self._span.finish()
        for tok in reversed(self._tokens):
            tok.var.reset(tok)

    async def __aenter__(self) -> Span:
        return self.__enter__()

    async def __aexit__(self, *args) -> None:
        self.__exit__(*args)


# ---------------------------------------------------------------------------
# Convenience functions
# ---------------------------------------------------------------------------

def start_span(
    name: str,
    trace_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> TraceContext:
    """
    Return a ``TraceContext`` (use as ``with`` or ``async with``).

    If ``trace_id`` is omitted, the active trace from context-vars is used.
    If neither is set, a new random trace ID is generated.
    """
    effective_trace_id = trace_id or _ctx_trace_id.get() or uuid.uuid4().hex
    return TraceContext(name, trace_id=effective_trace_id, metadata=metadata)


def end_span(span: Span, metadata: Optional[Dict[str, Any]] = None) -> None:
    """
    Manually close a span (for use when the context-manager pattern is
    not possible, e.g., across coroutine boundaries).
    """
    span.finish(metadata=metadata)
