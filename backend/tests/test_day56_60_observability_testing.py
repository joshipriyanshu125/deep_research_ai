"""
Tests for Days 56–60: Structured Logging, Monitoring, Observability, Testing & Evaluation

Day 56 — Structured logging (app/utils/logger.py)
Day 57 — Metrics / monitoring (app/monitoring/metrics.py)
Day 58 — Distributed tracing (app/tracing/tracer.py)
Day 59 — Test patterns (this file IS the Day 59 test suite)
Day 60 — Evaluation framework (app/evaluation/framework.py)
"""

import asyncio
import json
import logging
import pytest
from typing import List
from unittest.mock import patch


# ===========================================================================
# Day 56 — Structured Logging Tests
# ===========================================================================

class TestDay56StructuredLogging:
    """Verify that the logger emits valid, structured JSON records."""

    def test_logger_singleton_importable(self):
        from app.utils.logger import logger
        assert logger is not None
        assert isinstance(logger, logging.Logger)

    def test_get_logger_returns_logger(self):
        from app.utils.logger import get_logger
        log = get_logger("test.day56")
        assert isinstance(log, logging.Logger)
        assert log.name == "test.day56"

    def test_formatter_produces_valid_json(self):
        from app.utils.logger import StructuredJsonFormatter
        formatter = StructuredJsonFormatter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="hello world", args=(), exc_info=None,
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["level"] == "INFO"
        assert parsed["message"] == "hello world"
        assert parsed["service"] == "research-agent"
        assert "timestamp" in parsed
        assert "logger" in parsed

    def test_formatter_includes_research_id_from_extra(self):
        from app.utils.logger import StructuredJsonFormatter
        formatter = StructuredJsonFormatter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="test", args=(), exc_info=None,
        )
        record.research_id = "r_test_123"
        record.event = "source_processed"
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["research_id"] == "r_test_123"
        assert parsed["event"] == "source_processed"

    def test_formatter_includes_task_id_from_extra(self):
        from app.utils.logger import StructuredJsonFormatter
        formatter = StructuredJsonFormatter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="task test", args=(), exc_info=None,
        )
        record.task_id = "t_456"
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["task_id"] == "t_456"

    def test_formatter_omits_none_optional_fields(self):
        from app.utils.logger import StructuredJsonFormatter
        formatter = StructuredJsonFormatter()
        record = logging.LogRecord(
            name="test", level=logging.DEBUG, pathname="", lineno=0,
            msg="plain", args=(), exc_info=None,
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert "research_id" not in parsed
        assert "task_id" not in parsed
        assert "event" not in parsed

    def test_log_context_sets_research_id(self):
        from app.utils.logger import LogContext, StructuredJsonFormatter, _ctx_research_id
        formatter = StructuredJsonFormatter()

        with LogContext(research_id="ctx_r_001"):
            record = logging.LogRecord(
                name="test", level=logging.INFO, pathname="", lineno=0,
                msg="inside context", args=(), exc_info=None,
            )
            output = formatter.format(record)
            parsed = json.loads(output)
            assert parsed["research_id"] == "ctx_r_001"

        # After context exits, research_id should be cleared
        assert _ctx_research_id.get() is None

    def test_log_context_sets_task_id(self):
        from app.utils.logger import LogContext, StructuredJsonFormatter
        formatter = StructuredJsonFormatter()
        with LogContext(task_id="task_789"):
            record = logging.LogRecord(
                name="test", level=logging.INFO, pathname="", lineno=0,
                msg="task context", args=(), exc_info=None,
            )
            output = formatter.format(record)
            parsed = json.loads(output)
            assert parsed["task_id"] == "task_789"

    def test_log_context_is_nestable(self):
        from app.utils.logger import LogContext, StructuredJsonFormatter
        formatter = StructuredJsonFormatter()
        with LogContext(research_id="outer_r"):
            with LogContext(task_id="inner_t"):
                record = logging.LogRecord(
                    name="test", level=logging.INFO, pathname="", lineno=0,
                    msg="nested", args=(), exc_info=None,
                )
                output = formatter.format(record)
                parsed = json.loads(output)
                assert parsed["research_id"] == "outer_r"
                assert parsed["task_id"] == "inner_t"

    @pytest.mark.asyncio
    async def test_log_context_async(self):
        from app.utils.logger import LogContext, StructuredJsonFormatter
        formatter = StructuredJsonFormatter()
        async with LogContext(research_id="async_r_001", event="llm_call"):
            record = logging.LogRecord(
                name="test", level=logging.INFO, pathname="", lineno=0,
                msg="async llm call", args=(), exc_info=None,
            )
            output = formatter.format(record)
            parsed = json.loads(output)
            assert parsed["research_id"] == "async_r_001"
            assert parsed["event"] == "llm_call"

    def test_formatter_captures_exception(self):
        from app.utils.logger import StructuredJsonFormatter
        formatter = StructuredJsonFormatter()
        try:
            raise ValueError("something went wrong")
        except ValueError:
            import sys
            exc_info = sys.exc_info()
        record = logging.LogRecord(
            name="test", level=logging.ERROR, pathname="", lineno=0,
            msg="error!", args=(), exc_info=exc_info,
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert "exception" in parsed
        assert "ValueError" in parsed["exception"]

    def test_setup_logger_is_idempotent(self):
        from app.utils.logger import setup_logger
        log1 = setup_logger("idempotent.test")
        log2 = setup_logger("idempotent.test")
        assert log1 is log2

    def test_all_log_levels_produce_valid_json(self):
        from app.utils.logger import StructuredJsonFormatter
        formatter = StructuredJsonFormatter()
        for level in (logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR, logging.CRITICAL):
            record = logging.LogRecord(
                name="test", level=level, pathname="", lineno=0,
                msg=f"level={level}", args=(), exc_info=None,
            )
            output = formatter.format(record)
            parsed = json.loads(output)
            assert parsed["level"] == logging.getLevelName(level)


# ===========================================================================
# Day 57 — Metrics / Monitoring Tests
# ===========================================================================

class TestDay57Metrics:
    """Verify all metrics counters, histograms, and gauges work correctly."""

    def setup_method(self):
        from app.monitoring.metrics import MetricsCollector
        self.m = MetricsCollector()

    def test_counter_increments(self):
        self.m.api_requests_total.increment()
        snap = self.m.api_requests_total.snapshot()
        assert snap["total"] == 1

    def test_counter_with_labels(self):
        self.m.api_requests_total.increment({"method": "GET", "path": "/health", "status": "200"})
        self.m.api_requests_total.increment({"method": "POST", "path": "/research", "status": "201"})
        snap = self.m.api_requests_total.snapshot()
        assert snap["total"] == 2
        assert len(snap["by_labels"]) == 2

    def test_histogram_observe(self):
        self.m.api_latency_ms.observe(42.0)
        self.m.api_latency_ms.observe(150.0)
        snap = self.m.api_latency_ms.snapshot()
        assert snap["count"] == 2
        assert snap["sum"] == pytest.approx(192.0)
        assert snap["mean"] == pytest.approx(96.0)

    def test_histogram_percentiles(self):
        for v in [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]:
            self.m.api_latency_ms.observe(float(v))
        snap = self.m.api_latency_ms.snapshot()
        assert snap["p50"] <= snap["p95"]
        assert snap["p95"] <= snap["p99"]

    def test_gauge_set(self):
        self.m.queue_size.set(7.0)
        assert self.m.queue_size.snapshot() == pytest.approx(7.0)
        self.m.queue_size.set(3.0)
        assert self.m.queue_size.snapshot() == pytest.approx(3.0)

    def test_record_api_request(self):
        self.m.record_api_request("GET", "/api/v1/health", 200, 12.5)
        assert self.m.api_requests_total.snapshot()["total"] == 1
        assert self.m.api_latency_ms.snapshot()["count"] == 1

    def test_record_llm_call(self):
        self.m.record_llm_call("gpt-4o-mini", "generate", 310.0)
        assert self.m.llm_calls_total.snapshot()["total"] == 1
        assert self.m.llm_latency_ms.snapshot()["count"] == 1

    def test_record_llm_error(self):
        self.m.record_llm_error("gpt-4o-mini", "timeout")
        assert self.m.llm_errors_total.snapshot()["total"] == 1

    def test_record_search_error(self):
        self.m.record_search_error("tavily")
        assert self.m.search_errors_total.snapshot()["total"] == 1

    def test_record_scraping_error(self):
        self.m.record_scraping_error("example.com")
        assert self.m.scraping_errors_total.snapshot()["total"] == 1

    def test_record_worker_failure(self):
        self.m.record_worker_failure()
        self.m.record_worker_failure()
        assert self.m.worker_failures_total.snapshot()["total"] == 2

    def test_set_queue_size(self):
        self.m.set_queue_size(5)
        assert self.m.queue_size.snapshot() == pytest.approx(5.0)

    def test_record_db_operation(self):
        self.m.record_db_operation("find", 8.0)
        assert self.m.db_latency_ms.snapshot()["count"] == 1

    def test_record_research_completed(self):
        self.m.record_research_completed(45000.0)
        assert self.m.research_duration_ms.snapshot()["count"] == 1

    def test_get_snapshot_has_all_keys(self):
        snap = self.m.get_snapshot()
        expected_keys = [
            "uptime_seconds",
            "api_requests_total",
            "api_latency_ms",
            "llm_calls_total",
            "llm_latency_ms",
            "llm_errors_total",
            "search_errors_total",
            "scraping_errors_total",
            "worker_failures_total",
            "queue_size",
            "db_latency_ms",
            "research_duration_ms",
        ]
        for key in expected_keys:
            assert key in snap, f"Missing key: {key}"

    def test_reset_clears_all_metrics(self):
        self.m.record_api_request("GET", "/", 200, 10.0)
        self.m.record_llm_error("model", "err")
        self.m.reset()
        assert self.m.api_requests_total.snapshot()["total"] == 0
        assert self.m.llm_errors_total.snapshot()["total"] == 0

    def test_metrics_collector_singleton_importable(self):
        from app.monitoring.metrics import metrics_collector
        from app.monitoring.metrics import MetricsCollector
        assert isinstance(metrics_collector, MetricsCollector)

    def test_counter_is_thread_safe(self):
        import threading
        counter = self.m.api_requests_total
        threads = [threading.Thread(target=counter.increment) for _ in range(100)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert counter.snapshot()["total"] == 100


# ===========================================================================
# Day 58 — Distributed Tracing Tests
# ===========================================================================

class TestDay58Tracing:
    """Verify span creation, parent-child wiring, and trace tree building."""

    def setup_method(self):
        from app.tracing.tracer import TraceStore
        self.store = TraceStore()

    def test_span_creation(self):
        from app.tracing.tracer import Span
        span = Span(name="Research", trace_id="t_001")
        assert span.name == "Research"
        assert span.trace_id == "t_001"
        assert span.parent_id is None
        assert span.end_time is None
        assert len(span.span_id) == 12

    def test_span_finish(self):
        from app.tracing.tracer import Span
        span = Span(name="Planner", trace_id="t_002")
        span.finish()
        assert span.end_time is not None
        assert span.duration_ms is not None
        assert span.duration_ms >= 0

    def test_span_finish_with_metadata(self):
        from app.tracing.tracer import Span
        span = Span(name="LLM Call", trace_id="t_003")
        span.finish(metadata={"model": "gpt-4o-mini", "tokens": 512})
        assert span.metadata["model"] == "gpt-4o-mini"
        assert span.metadata["tokens"] == 512

    def test_span_to_dict(self):
        from app.tracing.tracer import Span
        span = Span(name="Search", trace_id="t_004")
        span.finish()
        d = span.to_dict()
        assert d["name"] == "Search"
        assert d["trace_id"] == "t_004"
        assert "duration_ms" in d
        assert "children" in d

    def test_trace_context_creates_span(self):
        from app.tracing.tracer import TraceContext
        ctx = TraceContext("Research", trace_id="t_005")
        with ctx as span:
            assert span.name == "Research"
            assert span.trace_id == "t_005"
            assert span.end_time is None
        assert span.end_time is not None

    def test_nested_spans_parent_child_wiring(self):
        from app.tracing.tracer import TraceContext, TraceStore
        store = TraceStore()
        with patch("app.tracing.tracer.trace_store", store):
            from app.tracing import tracer as tracer_mod
            orig_store = tracer_mod.trace_store
            tracer_mod.trace_store = store

            with TraceContext("Research", trace_id="t_006") as root:
                root_id = root.span_id
                with TraceContext("Planner", trace_id="t_006") as planner:
                    planner_id = planner.span_id
                    assert planner.parent_id == root_id
                    with TraceContext("LLM call", trace_id="t_006") as llm:
                        assert llm.parent_id == planner_id

            tracer_mod.trace_store = orig_store

    def test_trace_store_get_or_create(self):
        from app.tracing.tracer import ResearchTrace
        trace = self.store.get_or_create("t_100")
        assert isinstance(trace, ResearchTrace)
        assert trace.trace_id == "t_100"
        # Same trace returned on second call
        assert self.store.get_or_create("t_100") is trace

    def test_trace_store_add_span(self):
        from app.tracing.tracer import Span
        span = Span(name="root", trace_id="t_200", parent_id=None)
        self.store.add_span(span)
        trace = self.store.get_trace("t_200")
        assert trace is not None
        assert len(trace.spans) == 1

    def test_build_tree_nested(self):
        from app.tracing.tracer import Span, ResearchTrace
        root = Span(name="Research", trace_id="t_300", parent_id=None)
        child1 = Span(name="Planner", trace_id="t_300", parent_id=root.span_id)
        child2 = Span(name="Task 1", trace_id="t_300", parent_id=root.span_id)
        grandchild = Span(name="LLM", trace_id="t_300", parent_id=child1.span_id)
        for s in [root, child1, child2, grandchild]:
            s.finish()

        trace = ResearchTrace(trace_id="t_300", spans=[root, child1, child2, grandchild])
        tree = trace.build_tree()
        assert tree is not None
        assert tree["name"] == "Research"
        child_names = {c["name"] for c in tree["children"]}
        assert child_names == {"Planner", "Task 1"}

    def test_get_trace_tree_returns_none_for_unknown(self):
        result = self.store.get_trace_tree("nonexistent_trace")
        assert result is None

    def test_trace_store_list_traces(self):
        from app.tracing.tracer import Span
        s1 = Span(name="r1", trace_id="trace_a")
        s2 = Span(name="r2", trace_id="trace_b")
        self.store.add_span(s1)
        self.store.add_span(s2)
        ids = self.store.list_traces()
        assert "trace_a" in ids
        assert "trace_b" in ids

    def test_trace_store_clear(self):
        from app.tracing.tracer import Span
        self.store.add_span(Span(name="x", trace_id="clear_test"))
        self.store.clear()
        assert self.store.get_trace("clear_test") is None

    def test_start_span_helper(self):
        from app.tracing.tracer import start_span, TraceStore
        store = TraceStore()
        from app.tracing import tracer as tracer_mod
        orig = tracer_mod.trace_store
        tracer_mod.trace_store = store
        try:
            with start_span("Synthesis", trace_id="t_helper") as span:
                assert span.name == "Synthesis"
        finally:
            tracer_mod.trace_store = orig

    def test_end_span_helper(self):
        from app.tracing.tracer import Span, end_span
        span = Span(name="manual", trace_id="t_manual")
        end_span(span, metadata={"source": "manual_close"})
        assert span.end_time is not None
        assert span.metadata["source"] == "manual_close"

    def test_current_trace_id_default_none(self):
        from app.tracing.tracer import current_trace_id
        assert current_trace_id() is None

    @pytest.mark.asyncio
    async def test_trace_context_async(self):
        from app.tracing.tracer import TraceContext, TraceStore
        store = TraceStore()
        from app.tracing import tracer as tracer_mod
        orig = tracer_mod.trace_store
        tracer_mod.trace_store = store
        try:
            async with TraceContext("AsyncResearch", trace_id="t_async") as span:
                assert span.name == "AsyncResearch"
                await asyncio.sleep(0)
            assert span.end_time is not None
        finally:
            tracer_mod.trace_store = orig

    def test_trace_context_captures_exception_in_metadata(self):
        from app.tracing.tracer import TraceContext, TraceStore
        store = TraceStore()
        from app.tracing import tracer as tracer_mod
        orig = tracer_mod.trace_store
        tracer_mod.trace_store = store
        span_ref = None
        try:
            with TraceContext("ErrorSpan", trace_id="t_err") as span:
                span_ref = span
                raise RuntimeError("scraping failed")
        except RuntimeError:
            pass
        finally:
            tracer_mod.trace_store = orig
        assert span_ref is not None
        assert "error" in span_ref.metadata
        assert "scraping failed" in span_ref.metadata["error"]


# ===========================================================================
# Day 59 — Integration Pattern Tests
# ===========================================================================

class TestDay59IntegrationPatterns:
    """
    Verify that the three Day 56–58 systems work together correctly
    without requiring a real DB or LLM.
    """

    def test_logger_and_metrics_together(self):
        from app.utils.logger import get_logger, LogContext
        from app.monitoring.metrics import MetricsCollector

        m = MetricsCollector()
        log = get_logger("integration.test")

        with LogContext(research_id="int_r_001", event="source_processed"):
            m.record_api_request("GET", "/api/v1/research", 200, 55.0)
            log.info("Source processed")

        snap = m.get_snapshot()
        assert snap["api_requests_total"]["total"] == 1
        assert snap["api_latency_ms"]["count"] == 1

    @pytest.mark.asyncio
    async def test_logger_metrics_tracing_together(self):
        from app.utils.logger import LogContext
        from app.monitoring.metrics import MetricsCollector
        from app.tracing.tracer import TraceStore, TraceContext

        m = MetricsCollector()
        store = TraceStore()
        from app.tracing import tracer as tracer_mod
        orig = tracer_mod.trace_store
        tracer_mod.trace_store = store

        try:
            async with LogContext(research_id="r_integration"):
                async with TraceContext("Research", trace_id="r_integration") as root_span:
                    async with TraceContext("Search", trace_id="r_integration"):
                        m.record_api_request("GET", "/search", 200, 120.0)
                        await asyncio.sleep(0)
                    async with TraceContext("LLM", trace_id="r_integration"):
                        m.record_llm_call("gpt-4o-mini", "generate", 350.0)
                        await asyncio.sleep(0)

            tree = store.get_trace_tree("r_integration")
            assert tree is not None
            assert tree["name"] == "Research"
            child_names = {c["name"] for c in tree["children"]}
            assert "Search" in child_names
            assert "LLM" in child_names

            snap = m.get_snapshot()
            assert snap["api_requests_total"]["total"] == 1
            assert snap["llm_calls_total"]["total"] == 1
        finally:
            tracer_mod.trace_store = orig

    def test_research_lifecycle_full_metrics(self):
        from app.monitoring.metrics import MetricsCollector
        m = MetricsCollector()

        # Simulate a research lifecycle
        m.set_queue_size(1)
        m.record_api_request("POST", "/api/v1/research", 202, 25.0)
        m.record_llm_call("gpt-4o-mini", "plan", 200.0)
        m.record_api_request("GET", "/api/v1/research/sources", 200, 10.0)
        m.record_db_operation("insert_evidence", 5.0)
        m.record_llm_call("gpt-4o-mini", "synthesize", 800.0)
        m.set_queue_size(0)
        m.record_research_completed(30000.0)

        snap = m.get_snapshot()
        assert snap["api_requests_total"]["total"] == 2
        assert snap["llm_calls_total"]["total"] == 2
        assert snap["db_latency_ms"]["count"] == 1
        assert snap["research_duration_ms"]["count"] == 1
        assert snap["queue_size"] == pytest.approx(0.0)


# ===========================================================================
# Day 60 — Evaluation Framework Tests
# ===========================================================================

class TestDay60EvaluationFramework:
    """Verify the benchmark question management, scoring, and report generation."""

    def setup_method(self):
        from app.evaluation.framework import EvaluationFramework
        self.fw = EvaluationFramework()

    # --- BenchmarkQuestion ---

    def test_benchmark_question_creation(self):
        from app.evaluation.framework import BenchmarkQuestion
        q = BenchmarkQuestion(
            question_id="q_001",
            question="What is quantum computing?",
            expected_keywords=["qubit", "superposition"],
            topic="Technology",
            difficulty="medium",
        )
        assert q.question_id == "q_001"
        assert q.difficulty == "medium"
        assert "qubit" in q.expected_keywords

    def test_add_question(self):
        from app.evaluation.framework import BenchmarkQuestion
        q = BenchmarkQuestion(question_id="q_002", question="Test?")
        self.fw.add_question(q)
        assert len(self.fw.questions) == 1

    def test_add_questions_bulk(self):
        from app.evaluation.framework import BenchmarkQuestion
        qs = [BenchmarkQuestion(question_id=f"q_{i}", question=f"Q{i}?") for i in range(5)]
        self.fw.add_questions(qs)
        assert len(self.fw.questions) == 5

    # --- Scoring helpers ---

    def test_factual_accuracy_all_found(self):
        from app.evaluation.framework import _score_factual_accuracy
        score = _score_factual_accuracy(
            "The EV market grew with lithium batteries showing high CAGR",
            ["ev", "lithium", "cagr"],
        )
        assert score == pytest.approx(1.0)

    def test_factual_accuracy_none_found(self):
        from app.evaluation.framework import _score_factual_accuracy
        score = _score_factual_accuracy("unrelated text", ["quantum", "blockchain"])
        assert score == pytest.approx(0.0)

    def test_factual_accuracy_partial(self):
        from app.evaluation.framework import _score_factual_accuracy
        score = _score_factual_accuracy("quantum computing is fast", ["quantum", "blockchain"])
        assert score == pytest.approx(0.5)

    def test_factual_accuracy_no_keywords(self):
        from app.evaluation.framework import _score_factual_accuracy
        score = _score_factual_accuracy("any answer", [])
        assert score == pytest.approx(1.0)

    def test_citation_accuracy_with_markers(self):
        from app.evaluation.framework import _score_citation_accuracy
        assert _score_citation_accuracy("Research [[1]] shows growth") == pytest.approx(1.0)
        assert _score_citation_accuracy("See https://example.com for details") == pytest.approx(1.0)

    def test_citation_accuracy_no_citations(self):
        from app.evaluation.framework import _score_citation_accuracy
        assert _score_citation_accuracy("Good answer without citations") == pytest.approx(0.5)
        assert _score_citation_accuracy("") == pytest.approx(0.0)

    def test_reasoning_quality_short_answer(self):
        from app.evaluation.framework import _score_reasoning_quality
        assert _score_reasoning_quality("Short") == pytest.approx(0.0)
        assert _score_reasoning_quality("") == pytest.approx(0.0)

    def test_reasoning_quality_structured_answer(self):
        from app.evaluation.framework import _score_reasoning_quality
        answer = """
        ## Introduction
        **Quantum computing** uses qubits.
        - Therefore it is fast
        - Because of superposition
        1. Step one
        2. Step two
        However, challenges remain.
        """
        score = _score_reasoning_quality(answer)
        assert score > 0.5

    def test_source_quality_no_expected(self):
        from app.evaluation.framework import _score_source_quality
        # Neutral score when no expectation
        score = _score_source_quality("any answer", [])
        assert score == pytest.approx(0.7)

    def test_source_quality_domain_found(self):
        from app.evaluation.framework import _score_source_quality
        score = _score_source_quality(
            "According to nature.com and arxiv.org research",
            ["nature.com", "arxiv.org"],
        )
        assert score == pytest.approx(1.0)

    # --- EvaluationResult ---

    def test_evaluation_result_overall_score(self):
        from app.evaluation.framework import EvaluationResult
        r = EvaluationResult(
            question_id="q_001",
            question="test",
            factual_accuracy=1.0,
            citation_accuracy=1.0,
            citation_completeness=1.0,
            research_completeness=1.0,
            source_quality=1.0,
            reasoning_quality=1.0,
        )
        assert r.overall_score == pytest.approx(1.0)

    def test_evaluation_result_zero_scores(self):
        from app.evaluation.framework import EvaluationResult
        r = EvaluationResult(question_id="q_001", question="test")
        assert r.overall_score == pytest.approx(0.0)

    def test_evaluation_result_to_dict(self):
        from app.evaluation.framework import EvaluationResult
        r = EvaluationResult(
            question_id="q_001",
            question="test",
            factual_accuracy=0.8,
            latency_ms=1500.0,
        )
        d = r.to_dict()
        assert d["question_id"] == "q_001"
        assert d["factual_accuracy"] == pytest.approx(0.8)
        assert d["latency_ms"] == pytest.approx(1500.0)
        assert "overall_score" in d

    # --- run_benchmark ---

    @pytest.mark.asyncio
    async def test_run_benchmark_single_question(self):
        from app.evaluation.framework import BenchmarkQuestion

        async def mock_research(question: str) -> str:
            return (
                "The EV market uses lithium batteries and shows high CAGR. "
                "See https://example.com [[1]] for details. "
                "## Analysis\n**Therefore** this is significant because of growth."
            )

        q = BenchmarkQuestion(
            question_id="q_benchmark_01",
            question="Tell me about EV batteries",
            expected_keywords=["ev", "lithium", "cagr"],
        )
        self.fw.add_question(q)
        report = await self.fw.run_benchmark(mock_research)

        assert report["summary"]["total"] == 1
        assert len(report["results"]) == 1
        result = report["results"][0]
        assert result["factual_accuracy"] == pytest.approx(1.0)
        assert result["citation_accuracy"] == pytest.approx(1.0)

    @pytest.mark.asyncio
    async def test_run_benchmark_multiple_questions(self):
        from app.evaluation.framework import BenchmarkQuestion

        async def mock_fn(q: str) -> str:
            return "Answer with [[1]] citation and ## structure. Therefore good."

        for i in range(3):
            self.fw.add_question(
                BenchmarkQuestion(question_id=f"q_{i}", question=f"Question {i}?")
            )
        report = await self.fw.run_benchmark(mock_fn)
        assert report["summary"]["total"] == 3

    @pytest.mark.asyncio
    async def test_run_benchmark_handles_errors(self):
        from app.evaluation.framework import BenchmarkQuestion

        async def failing_fn(q: str) -> str:
            raise ConnectionError("LLM unavailable")

        self.fw.add_question(
            BenchmarkQuestion(question_id="q_err", question="Fail?")
        )
        report = await self.fw.run_benchmark(failing_fn)
        assert report["summary"]["error_count"] == 1
        assert report["results"][0]["error"] is not None

    @pytest.mark.asyncio
    async def test_run_benchmark_question_id_filter(self):
        from app.evaluation.framework import BenchmarkQuestion

        async def mock_fn(q: str) -> str:
            return "Answer"

        for i in range(5):
            self.fw.add_question(
                BenchmarkQuestion(question_id=f"q_{i}", question=f"Q{i}?")
            )
        report = await self.fw.run_benchmark(mock_fn, question_ids=["q_0", "q_2"])
        assert report["summary"]["total"] == 2

    # --- generate_report ---

    def test_generate_report_empty(self):
        report = self.fw.generate_report([])
        assert report["summary"]["total"] == 0

    def test_generate_report_aggregate_stats(self):
        from app.evaluation.framework import EvaluationResult
        results = [
            EvaluationResult(
                question_id=f"q_{i}",
                question=f"Q{i}",
                factual_accuracy=0.8,
                citation_accuracy=0.9,
                citation_completeness=0.7,
                research_completeness=0.85,
                source_quality=0.75,
                reasoning_quality=0.8,
            )
            for i in range(10)
        ]
        report = self.fw.generate_report(results)
        agg = report["aggregate"]
        assert agg["factual_accuracy"]["mean"] == pytest.approx(0.8)
        assert agg["factual_accuracy"]["min"] == pytest.approx(0.8)
        assert agg["factual_accuracy"]["max"] == pytest.approx(0.8)
        assert "p50" in agg["factual_accuracy"]
        assert "p95" in agg["factual_accuracy"]

    def test_generate_report_pass_rate(self):
        from app.evaluation.framework import EvaluationResult
        # 7 pass (score >= 0.7), 3 fail
        results = []
        for i in range(7):
            r = EvaluationResult(question_id=f"p_{i}", question="Q")
            r.factual_accuracy = 1.0
            r.citation_accuracy = 1.0
            r.citation_completeness = 1.0
            r.research_completeness = 1.0
            r.source_quality = 1.0
            r.reasoning_quality = 1.0
            results.append(r)
        for i in range(3):
            results.append(EvaluationResult(question_id=f"f_{i}", question="Q"))

        report = self.fw.generate_report(results)
        assert report["summary"]["total"] == 10
        assert report["summary"]["passed"] == 7
        assert report["summary"]["pass_rate"] == pytest.approx(0.7)

    def test_evaluation_framework_singleton_importable(self):
        from app.evaluation.framework import evaluation_framework, EvaluationFramework
        assert isinstance(evaluation_framework, EvaluationFramework)
