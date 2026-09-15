"""
Day 57 — Monitoring / Metrics

Pure-Python in-memory metrics collector.  No external dependencies (Prometheus
client, StatsD, etc.) are required — this is intentionally self-contained so
the service works in any environment.

Tracked metrics
---------------
API
    api_requests_total          – Counter  {method, path, status}
    api_latency_ms              – Histogram

LLM
    llm_calls_total             – Counter  {model, operation}
    llm_latency_ms              – Histogram
    llm_errors_total            – Counter  {model, error_type}

Search
    search_errors_total         – Counter  {provider}

Scraping
    scraping_errors_total       – Counter  {url_domain}

Worker
    worker_failures_total       – Counter
    queue_size                  – Gauge (last observed)

Database
    db_latency_ms               – Histogram {operation}

Research
    research_duration_ms        – Histogram

Usage::

    from app.monitoring.metrics import metrics_collector

    metrics_collector.record_api_request("GET", "/api/v1/research", 200, 42.3)
    metrics_collector.record_llm_call("gpt-4o-mini", "generate", 310.0)
    metrics_collector.record_llm_error("gpt-4o-mini", "timeout")

    snapshot = metrics_collector.get_snapshot()
    # → {"api_requests_total": {...}, "api_latency_ms": {...}, ...}
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Primitives
# ---------------------------------------------------------------------------

class Counter:
    """Thread-safe monotonically increasing counter."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._value: int = 0
        self._labels: Dict[str, int] = defaultdict(int)

    def increment(self, labels: Optional[Dict[str, str]] = None, amount: int = 1) -> None:
        with self._lock:
            self._value += amount
            if labels:
                key = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
                self._labels[key] += amount

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return {"total": self._value, "by_labels": dict(self._labels)}


class Histogram:
    """
    Thread-safe histogram with configurable bucket boundaries.

    Default buckets (ms): 5, 25, 50, 100, 250, 500, 1000, 2500, 5000, +Inf
    """

    DEFAULT_BUCKETS = (5.0, 25.0, 50.0, 100.0, 250.0, 500.0, 1000.0, 2500.0, 5000.0, float("inf"))

    def __init__(self, buckets: tuple = DEFAULT_BUCKETS) -> None:
        self._lock = threading.Lock()
        self._buckets = sorted(buckets)
        self._counts: List[int] = [0] * len(self._buckets)
        self._sum: float = 0.0
        self._total: int = 0

    def observe(self, value: float) -> None:
        with self._lock:
            self._sum += value
            self._total += 1
            for i, boundary in enumerate(self._buckets):
                if value <= boundary:
                    self._counts[i] += 1
                    break

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "count": self._total,
                "sum": round(self._sum, 3),
                "mean": round(self._sum / self._total, 3) if self._total else 0.0,
                "p50": self._percentile(50),
                "p95": self._percentile(95),
                "p99": self._percentile(99),
                "buckets": {
                    str(b): self._counts[i] for i, b in enumerate(self._buckets)
                },
            }

    def _percentile(self, pct: float) -> float:
        """Approximate percentile from bucket data."""
        if self._total == 0:
            return 0.0
        target = self._total * pct / 100
        cumulative = 0
        for i, count in enumerate(self._counts):
            cumulative += count
            if cumulative >= target:
                return self._buckets[i]
        return self._buckets[-1]


class Gauge:
    """Thread-safe last-value gauge."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._value: float = 0.0

    def set(self, value: float) -> None:
        with self._lock:
            self._value = value

    def snapshot(self) -> float:
        with self._lock:
            return self._value


# ---------------------------------------------------------------------------
# MetricsCollector
# ---------------------------------------------------------------------------

class MetricsCollector:
    """
    Central metrics registry.

    All ``record_*`` methods are synchronous and thread-safe so they can be
    called from both sync and async code without awaiting.
    """

    def __init__(self) -> None:
        # API
        self.api_requests_total = Counter()
        self.api_latency_ms = Histogram()

        # LLM
        self.llm_calls_total = Counter()
        self.llm_latency_ms = Histogram()
        self.llm_errors_total = Counter()

        # Search / Scraping
        self.search_errors_total = Counter()
        self.scraping_errors_total = Counter()

        # Worker
        self.worker_failures_total = Counter()
        self.queue_size = Gauge()

        # Database
        self.db_latency_ms = Histogram()

        # Research lifecycle
        self.research_duration_ms = Histogram()

        self._start_time = time.time()

    # ------------------------------------------------------------------ #
    # Record helpers
    # ------------------------------------------------------------------ #

    def record_api_request(
        self,
        method: str,
        path: str,
        status: int,
        latency_ms: float,
    ) -> None:
        """Record one completed HTTP request."""
        self.api_requests_total.increment(
            {"method": method, "path": path, "status": str(status)}
        )
        self.api_latency_ms.observe(latency_ms)

    def record_llm_call(
        self,
        model: str,
        operation: str,
        latency_ms: float,
    ) -> None:
        """Record a successful LLM call."""
        self.llm_calls_total.increment({"model": model, "operation": operation})
        self.llm_latency_ms.observe(latency_ms)

    def record_llm_error(self, model: str, error_type: str) -> None:
        """Record an LLM error."""
        self.llm_errors_total.increment({"model": model, "error_type": error_type})

    def record_search_error(self, provider: str) -> None:
        """Record a search API failure."""
        self.search_errors_total.increment({"provider": provider})

    def record_scraping_error(self, domain: str) -> None:
        """Record a scraping failure."""
        self.scraping_errors_total.increment({"domain": domain})

    def record_worker_failure(self) -> None:
        """Record a worker failure."""
        self.worker_failures_total.increment()

    def set_queue_size(self, size: int) -> None:
        """Update the current research job queue size."""
        self.queue_size.set(float(size))

    def record_db_operation(self, operation: str, latency_ms: float) -> None:
        """Record a database operation latency."""
        self.db_latency_ms.observe(latency_ms)

    def record_research_completed(self, duration_ms: float) -> None:
        """Record total end-to-end research duration."""
        self.research_duration_ms.observe(duration_ms)

    # ------------------------------------------------------------------ #
    # Snapshot
    # ------------------------------------------------------------------ #

    def get_snapshot(self) -> Dict[str, Any]:
        """
        Return a full metrics snapshot as a plain dict.

        Suitable for a ``/metrics`` endpoint or dashboard ingestion.
        """
        return {
            "uptime_seconds": round(time.time() - self._start_time, 1),
            "api_requests_total": self.api_requests_total.snapshot(),
            "api_latency_ms": self.api_latency_ms.snapshot(),
            "llm_calls_total": self.llm_calls_total.snapshot(),
            "llm_latency_ms": self.llm_latency_ms.snapshot(),
            "llm_errors_total": self.llm_errors_total.snapshot(),
            "search_errors_total": self.search_errors_total.snapshot(),
            "scraping_errors_total": self.scraping_errors_total.snapshot(),
            "worker_failures_total": self.worker_failures_total.snapshot(),
            "queue_size": self.queue_size.snapshot(),
            "db_latency_ms": self.db_latency_ms.snapshot(),
            "research_duration_ms": self.research_duration_ms.snapshot(),
        }

    def to_prometheus_text(self) -> str:
        """
        Export all metrics in standard Prometheus exposition text format (version 0.0.4).
        Compatible with Prometheus server scraping.
        """
        lines: List[str] = []
        now = time.time()
        uptime = round(now - self._start_time, 2)

        # Uptime
        lines.append("# HELP deep_research_uptime_seconds System uptime in seconds.")
        lines.append("# TYPE deep_research_uptime_seconds gauge")
        lines.append(f"deep_research_uptime_seconds {uptime}")

        # API requests
        lines.append("# HELP deep_research_api_requests_total Total HTTP requests handled.")
        lines.append("# TYPE deep_research_api_requests_total counter")
        api_snap = self.api_requests_total.snapshot()
        lines.append(f"deep_research_api_requests_total {api_snap['total']}")
        for label_str, count in api_snap.get("by_labels", {}).items():
            # e.g. method=GET,path=/api/v1/research,status=200 -> method="GET",path="/api/v1/research",status="200"
            parts = label_str.split(",")
            prom_labels = ",".join(f'{k.strip()}="{v.strip()}"' for part in parts if "=" in part for k, v in [part.split("=", 1)])
            lines.append(f"deep_research_api_requests_total{{{prom_labels}}} {count}")

        # LLM calls
        lines.append("# HELP deep_research_llm_calls_total Total LLM API invocations.")
        lines.append("# TYPE deep_research_llm_calls_total counter")
        llm_snap = self.llm_calls_total.snapshot()
        lines.append(f"deep_research_llm_calls_total {llm_snap['total']}")
        for label_str, count in llm_snap.get("by_labels", {}).items():
            parts = label_str.split(",")
            prom_labels = ",".join(f'{k.strip()}="{v.strip()}"' for part in parts if "=" in part for k, v in [part.split("=", 1)])
            lines.append(f"deep_research_llm_calls_total{{{prom_labels}}} {count}")

        # LLM errors
        lines.append("# HELP deep_research_llm_errors_total Total LLM API error occurrences.")
        lines.append("# TYPE deep_research_llm_errors_total counter")
        llm_err_snap = self.llm_errors_total.snapshot()
        lines.append(f"deep_research_llm_errors_total {llm_err_snap['total']}")

        # Queue Size
        lines.append("# HELP deep_research_queue_size Current research job queue depth.")
        lines.append("# TYPE deep_research_queue_size gauge")
        lines.append(f"deep_research_queue_size {self.queue_size.snapshot()}")

        # Worker failures
        lines.append("# HELP deep_research_worker_failures_total Total background worker job failures.")
        lines.append("# TYPE deep_research_worker_failures_total counter")
        lines.append(f"deep_research_worker_failures_total {self.worker_failures_total.snapshot()['total']}")

        # Latency histograms
        lines.append("# HELP deep_research_api_latency_ms API request latency in milliseconds.")
        lines.append("# TYPE deep_research_api_latency_ms summary")
        api_lat = self.api_latency_ms.snapshot()
        lines.append(f"deep_research_api_latency_ms_count {api_lat['count']}")
        lines.append(f"deep_research_api_latency_ms_sum {api_lat['sum']}")

        lines.append("")
        return "\n".join(lines)

    def reset(self) -> None:
        """Reset all metrics to zero (useful in tests)."""
        self.__init__()  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

metrics_collector = MetricsCollector()
