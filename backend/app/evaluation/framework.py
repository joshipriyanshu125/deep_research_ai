"""
Day 60 — Evaluation Framework

Separates a real AI research product from a demo.  Creates structured
benchmark questions, runs them through the research pipeline, and measures
eight quality dimensions.

Dimensions measured
-------------------
- factual_accuracy       : are stated facts correct?
- citation_accuracy      : do citations match the claim they support?
- citation_completeness  : what fraction of facts are cited?
- research_completeness  : how many benchmark sub-topics are covered?
- source_quality         : credibility / peer-review score of sources
- reasoning_quality      : logical coherence of the argument
- latency_ms             : wall-clock time for the full research run
- cost_usd               : estimated token cost (if provider reports it)

Usage::

    from app.evaluation.framework import evaluation_framework, BenchmarkQuestion

    q = BenchmarkQuestion(
        question_id="q_001",
        question="What is the global market size of EV batteries in 2025?",
        expected_keywords=["billion", "lithium", "CAGR"],
        topic="Energy",
        difficulty="medium",
    )
    evaluation_framework.add_question(q)

    # Run with a coroutine that takes (question_str) -> research_result_str
    report = await evaluation_framework.run_benchmark(my_research_fn)
    print(report["aggregate"])
"""

from __future__ import annotations

import asyncio
import statistics
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, Dict, List, Optional


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class BenchmarkQuestion:
    """
    One question in the evaluation benchmark.

    Attributes
    ----------
    question_id       : unique identifier (e.g. "q_001")
    question          : the natural-language research question
    expected_keywords : list of keywords/phrases that a good answer must mention
    topic             : thematic grouping (e.g. "Energy", "Healthcare")
    difficulty        : "easy" | "medium" | "hard"
    expected_sources  : optional list of authoritative source domains
    max_latency_ms    : acceptable latency budget in milliseconds
    """

    question_id: str
    question: str
    expected_keywords: List[str] = field(default_factory=list)
    topic: str = "general"
    difficulty: str = "medium"
    expected_sources: List[str] = field(default_factory=list)
    max_latency_ms: float = 120_000.0  # 2 minutes default


@dataclass
class EvaluationResult:
    """
    Scores for one benchmark question run.

    All scores are in [0.0, 1.0] unless stated otherwise.
    """

    question_id: str
    question: str
    answer: str = ""

    # Quality dimensions
    factual_accuracy: float = 0.0
    citation_accuracy: float = 0.0
    citation_completeness: float = 0.0
    research_completeness: float = 0.0
    source_quality: float = 0.0
    reasoning_quality: float = 0.0

    # Performance
    latency_ms: float = 0.0
    cost_usd: float = 0.0

    # Meta
    error: Optional[str] = None

    @property
    def overall_score(self) -> float:
        """Weighted average of the six quality dimensions."""
        weights = {
            "factual_accuracy": 0.25,
            "citation_accuracy": 0.15,
            "citation_completeness": 0.15,
            "research_completeness": 0.20,
            "source_quality": 0.10,
            "reasoning_quality": 0.15,
        }
        return round(
            sum(
                getattr(self, dim) * w for dim, w in weights.items()
            ),
            4,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "question_id": self.question_id,
            "question": self.question,
            "factual_accuracy": self.factual_accuracy,
            "citation_accuracy": self.citation_accuracy,
            "citation_completeness": self.citation_completeness,
            "research_completeness": self.research_completeness,
            "source_quality": self.source_quality,
            "reasoning_quality": self.reasoning_quality,
            "overall_score": self.overall_score,
            "latency_ms": self.latency_ms,
            "cost_usd": self.cost_usd,
            "error": self.error,
        }


# ---------------------------------------------------------------------------
# Scoring helpers
# ---------------------------------------------------------------------------

def _score_factual_accuracy(answer: str, expected_keywords: List[str]) -> float:
    """
    Keyword-presence heuristic.

    Checks what fraction of expected keywords appear in the answer (case-insensitive).
    In production this would call a fact-checking LLM or external verifier.
    """
    if not expected_keywords:
        return 1.0
    answer_lower = answer.lower()
    found = sum(1 for kw in expected_keywords if kw.lower() in answer_lower)
    return round(found / len(expected_keywords), 4)


def _score_citation_accuracy(answer: str) -> float:
    """
    Heuristic: presence of citation markers ([[1]], [Source:...], etc.).
    Returns 1.0 if citations are present, 0.5 if answer is non-empty without
    citations, 0.0 if answer is empty.
    """
    if not answer.strip():
        return 0.0
    citation_markers = ["[[", "[source", "[ref", "(source", "http://", "https://"]
    if any(m in answer.lower() for m in citation_markers):
        return 1.0
    return 0.5


def _score_citation_completeness(answer: str, expected_keywords: List[str]) -> float:
    """
    Heuristic: for each keyword found, check if a citation follows nearby.
    """
    if not expected_keywords or not answer:
        return 0.0
    answer_lower = answer.lower()
    cited = 0
    for kw in expected_keywords:
        idx = answer_lower.find(kw.lower())
        if idx == -1:
            continue
        # Check if a citation marker appears within 200 chars after the keyword
        snippet = answer_lower[idx: idx + 200]
        if any(m in snippet for m in ["[", "(source", "http"]):
            cited += 1
    return round(cited / len(expected_keywords), 4) if expected_keywords else 0.0


def _score_research_completeness(answer: str, expected_keywords: List[str]) -> float:
    """Same as factual_accuracy at this heuristic level — proxy for topic coverage."""
    return _score_factual_accuracy(answer, expected_keywords)


def _score_source_quality(answer: str, expected_sources: List[str]) -> float:
    """Check if expected authoritative domains appear in the answer."""
    if not expected_sources:
        return 0.7  # neutral when no expectation set
    answer_lower = answer.lower()
    found = sum(1 for src in expected_sources if src.lower() in answer_lower)
    return round(found / len(expected_sources), 4)


def _score_reasoning_quality(answer: str) -> float:
    """
    Simple proxy: longer, structured answers tend to show better reasoning.
    Checks for structural markers (sections, bullet points, numbered lists).
    """
    if not answer or len(answer) < 100:
        return 0.0
    markers = ["##", "**", "- ", "1.", "2.", "3.", "therefore", "because", "however"]
    found = sum(1 for m in markers if m in answer.lower())
    return min(1.0, round(found / 5, 4))


# ---------------------------------------------------------------------------
# EvaluationFramework
# ---------------------------------------------------------------------------

class EvaluationFramework:
    """
    Orchestrates benchmark runs and aggregates scores.

    Design
    ------
    - ``add_question()``  — register benchmark questions
    - ``run_benchmark()`` — pass a coroutine factory; framework calls it per question
    - ``generate_report()`` — compute aggregate statistics from results
    """

    def __init__(self) -> None:
        self._questions: List[BenchmarkQuestion] = []
        self._results: List[EvaluationResult] = []

    # ------------------------------------------------------------------ #
    # Question management
    # ------------------------------------------------------------------ #

    def add_question(self, question: BenchmarkQuestion) -> None:
        """Register a benchmark question."""
        self._questions.append(question)

    def add_questions(self, questions: List[BenchmarkQuestion]) -> None:
        """Bulk-register benchmark questions."""
        self._questions.extend(questions)

    def clear_questions(self) -> None:
        self._questions.clear()

    @property
    def questions(self) -> List[BenchmarkQuestion]:
        return list(self._questions)

    # ------------------------------------------------------------------ #
    # Benchmark execution
    # ------------------------------------------------------------------ #

    async def run_benchmark(
        self,
        research_fn: Callable[[str], Coroutine[Any, Any, str]],
        *,
        question_ids: Optional[List[str]] = None,
        concurrency: int = 1,
    ) -> Dict[str, Any]:
        """
        Run benchmark questions through ``research_fn`` and return a full report.

        Parameters
        ----------
        research_fn   : async callable (question: str) -> answer: str
        question_ids  : optional subset of question IDs to run; runs all if None
        concurrency   : max parallel questions (default 1 = sequential)

        Returns
        -------
        dict with keys "results" (list) and "aggregate" (dict of stats).
        """
        targets = [
            q for q in self._questions
            if question_ids is None or q.question_id in question_ids
        ]

        sem = asyncio.Semaphore(concurrency)

        async def _run_one(q: BenchmarkQuestion) -> EvaluationResult:
            async with sem:
                return await self._evaluate_one(q, research_fn)

        tasks = [_run_one(q) for q in targets]
        results: List[EvaluationResult] = await asyncio.gather(*tasks)
        self._results.extend(results)
        return self.generate_report(results)

    async def _evaluate_one(
        self,
        q: BenchmarkQuestion,
        research_fn: Callable[[str], Coroutine[Any, Any, str]],
    ) -> EvaluationResult:
        result = EvaluationResult(question_id=q.question_id, question=q.question)
        start = time.perf_counter()
        try:
            answer = await research_fn(q.question)
            result.answer = answer
            result.latency_ms = round((time.perf_counter() - start) * 1000, 2)

            # Score all dimensions
            result.factual_accuracy = _score_factual_accuracy(answer, q.expected_keywords)
            result.citation_accuracy = _score_citation_accuracy(answer)
            result.citation_completeness = _score_citation_completeness(answer, q.expected_keywords)
            result.research_completeness = _score_research_completeness(answer, q.expected_keywords)
            result.source_quality = _score_source_quality(answer, q.expected_sources)
            result.reasoning_quality = _score_reasoning_quality(answer)

            # Latency penalty (soft — does not lower other scores)
            if result.latency_ms > q.max_latency_ms:
                result.error = f"latency_exceeded:{result.latency_ms:.0f}ms"

        except Exception as exc:
            result.latency_ms = round((time.perf_counter() - start) * 1000, 2)
            result.error = str(exc)

        return result

    # ------------------------------------------------------------------ #
    # Report generation
    # ------------------------------------------------------------------ #

    def generate_report(
        self,
        results: Optional[List[EvaluationResult]] = None,
    ) -> Dict[str, Any]:
        """
        Generate an aggregate report from a list of results (or all stored results).

        Returns a dict with:
        - ``results``   : list of per-question result dicts
        - ``aggregate`` : mean, p50, p95 for every metric
        - ``summary``   : counts and pass rates
        """
        rs = results if results is not None else self._results
        if not rs:
            return {"results": [], "aggregate": {}, "summary": {"total": 0}}

        dims = [
            "factual_accuracy",
            "citation_accuracy",
            "citation_completeness",
            "research_completeness",
            "source_quality",
            "reasoning_quality",
            "overall_score",
        ]

        def _stats(values: List[float]) -> Dict[str, float]:
            if not values:
                return {"mean": 0.0, "p50": 0.0, "p95": 0.0, "min": 0.0, "max": 0.0}
            srt = sorted(values)
            n = len(srt)
            p50 = srt[int(n * 0.50)]
            p95 = srt[min(int(n * 0.95), n - 1)]
            return {
                "mean": round(statistics.mean(values), 4),
                "p50": round(p50, 4),
                "p95": round(p95, 4),
                "min": round(min(values), 4),
                "max": round(max(values), 4),
            }

        aggregate: Dict[str, Any] = {}
        for dim in dims:
            vals = [getattr(r, dim) for r in rs if not r.error]
            aggregate[dim] = _stats(vals)

        latencies = [r.latency_ms for r in rs if not r.error]
        aggregate["latency_ms"] = _stats(latencies)

        costs = [r.cost_usd for r in rs if not r.error]
        aggregate["cost_usd"] = _stats(costs)

        errors = [r for r in rs if r.error]
        pass_threshold = 0.7
        passed = [r for r in rs if r.overall_score >= pass_threshold and not r.error]

        summary = {
            "total": len(rs),
            "passed": len(passed),
            "failed": len(rs) - len(passed),
            "error_count": len(errors),
            "pass_rate": round(len(passed) / len(rs), 4) if rs else 0.0,
            "pass_threshold": pass_threshold,
        }

        return {
            "results": [r.to_dict() for r in rs],
            "aggregate": aggregate,
            "summary": summary,
        }

    @property
    def all_results(self) -> List[EvaluationResult]:
        return list(self._results)

    def clear_results(self) -> None:
        self._results.clear()


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

evaluation_framework = EvaluationFramework()
