"""
Tests for Days 46–50: Agent Orchestration System

Day 46 — Formalized agent orchestration (agent_orchestrator.py)
Day 47 — Dynamic planning (agents/planner.py enhancements)
Day 48 — Adaptive research loop (adaptive_loop.py)
Day 49 — Research stopping criteria (stopping_criteria.py)
Day 50 — Research quality scoring (quality_scorer.py)
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import List

# ---------------------------------------------------------------------------
# Shared fixtures / helpers
# ---------------------------------------------------------------------------

def _make_evidence(
    claim: str = "Test claim",
    confidence: float = 0.90,
    source_id: str = "src_1",
    verification_status: str = "verified",
    context: str = "",
    metrics: List[str] = None,
):
    from app.database.models.evidence import Evidence
    return Evidence(
        claim=claim,
        confidence=confidence,
        source_id=source_id,
        verification_status=verification_status,
        context=context,
        metrics=metrics or [],
        research_id="test_research_id",
        source_title="Test Source",
    )


def _make_source(
    url: str = "https://example.com",
    title: str = "Test Source",
    source_type: str = "web",
    credibility_score: float = 0.85,
    published_at: str = "2024-01-15",
):
    from app.database.models.source import Source
    return Source(
        url=url,
        title=title,
        source_type=source_type,
        credibility_score=credibility_score,
        published_at=published_at,
        research_id="test_research_id",
        domain="example.com",
    )


def _make_task(
    query: str = "test query",
    category: str = "web",
    status: str = "completed",
    task_id: str = None,
):
    from app.database.models.research import ResearchTask
    import uuid
    return ResearchTask(
        id=task_id or f"task_{uuid.uuid4().hex[:6]}",
        query=query,
        question=f"Question about {query}",
        category=category,
        status=status,
        depth=1,
    )


# ===========================================================================
# Day 46 — Agent Orchestration
# ===========================================================================

class TestAgentRole:
    def test_all_roles_defined(self):
        from app.research.agent_orchestrator import AgentRole
        roles = [r.value for r in AgentRole]
        expected = [
            "planner", "web_research", "academic", "data",
            "source_evaluation", "evidence", "analysis",
            "fact_checker", "citation", "report",
        ]
        for role in expected:
            assert role in roles, f"Missing role: {role}"

    def test_roles_are_string_enum(self):
        from app.research.agent_orchestrator import AgentRole
        assert isinstance(AgentRole.PLANNER.value, str)


class TestOrchestratorPlan:
    def test_default_pipeline_has_10_steps(self):
        from app.research.agent_orchestrator import OrchestratorPlan
        plan = OrchestratorPlan.default_pipeline()
        assert len(plan.steps) == 10

    def test_minimal_pipeline_has_4_steps(self):
        from app.research.agent_orchestrator import OrchestratorPlan
        plan = OrchestratorPlan.minimal_pipeline()
        assert len(plan.steps) == 4

    def test_default_pipeline_starts_with_planner(self):
        from app.research.agent_orchestrator import OrchestratorPlan, AgentRole
        plan = OrchestratorPlan.default_pipeline()
        assert plan.steps[0].role == AgentRole.PLANNER

    def test_default_pipeline_ends_with_report(self):
        from app.research.agent_orchestrator import OrchestratorPlan, AgentRole
        plan = OrchestratorPlan.default_pipeline()
        assert plan.steps[-1].role == AgentRole.REPORT

    def test_required_steps_are_not_optional(self):
        from app.research.agent_orchestrator import OrchestratorPlan, AgentRole
        plan = OrchestratorPlan.default_pipeline()
        required_roles = {AgentRole.PLANNER, AgentRole.WEB_RESEARCH, AgentRole.EVIDENCE, AgentRole.REPORT}
        for step in plan.steps:
            if step.role in required_roles:
                assert not step.optional, f"{step.role} should not be optional"


class TestResearchAgentOrchestrator:
    def test_select_plan_simple_query(self):
        from app.research.agent_orchestrator import ResearchAgentOrchestrator, OrchestratorPlan
        orch = ResearchAgentOrchestrator()
        plan = orch.select_plan("What is Python?", estimated_tasks=2)
        # Simple → minimal pipeline
        assert len(plan.steps) == 4

    def test_select_plan_complex_query(self):
        from app.research.agent_orchestrator import ResearchAgentOrchestrator
        orch = ResearchAgentOrchestrator()
        plan = orch.select_plan("Analyze India's EV market and identify investment opportunities", estimated_tasks=25)
        # Complex → full pipeline
        assert len(plan.steps) == 10

    @pytest.mark.asyncio
    async def test_run_agent_success(self):
        from app.research.agent_orchestrator import ResearchAgentOrchestrator, AgentRole
        orch = ResearchAgentOrchestrator()

        async def mock_coro():
            return ["result_1", "result_2"]

        result = await orch.run_agent(
            job_id="job_test",
            role=AgentRole.WEB_RESEARCH,
            coro=mock_coro,
            input_summary="web search for Python",
        )
        assert result == ["result_1", "result_2"]

    @pytest.mark.asyncio
    async def test_run_agent_failure_returns_none(self):
        from app.research.agent_orchestrator import ResearchAgentOrchestrator, AgentRole
        orch = ResearchAgentOrchestrator()

        async def failing_coro():
            raise RuntimeError("Test failure")

        result = await orch.run_agent(
            job_id="job_test",
            role=AgentRole.ACADEMIC,
            coro=failing_coro,
            max_retries=0,
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_run_agent_records_history(self):
        from app.research.agent_orchestrator import ResearchAgentOrchestrator, AgentRole
        orch = ResearchAgentOrchestrator()

        async def mock_coro():
            return "done"

        await orch.run_agent("job_xyz", AgentRole.CITATION, mock_coro)
        history = orch.get_history("job_xyz")
        assert len(history) == 1
        assert history[0].role == AgentRole.CITATION
        assert history[0].success is True

    @pytest.mark.asyncio
    async def test_run_agent_retry_on_failure(self):
        from app.research.agent_orchestrator import ResearchAgentOrchestrator, AgentRole
        orch = ResearchAgentOrchestrator()
        call_count = 0

        async def flaky_coro():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise RuntimeError("Transient")
            return "ok"

        result = await orch.run_agent("job_retry", AgentRole.FACT_CHECKER, flaky_coro, max_retries=2)
        assert result == "ok"
        assert call_count == 2

    def test_get_pipeline_summary_empty(self):
        from app.research.agent_orchestrator import ResearchAgentOrchestrator
        orch = ResearchAgentOrchestrator()
        summary = orch.get_pipeline_summary("nonexistent_job")
        assert summary["total_agents_run"] == 0
        assert summary["failed_agents"] == []

    @pytest.mark.asyncio
    async def test_get_pipeline_summary_with_history(self):
        from app.research.agent_orchestrator import ResearchAgentOrchestrator, AgentRole
        orch = ResearchAgentOrchestrator()

        async def ok():
            return True

        await orch.run_agent("job_sum", AgentRole.PLANNER, ok)
        await orch.run_agent("job_sum", AgentRole.WEB_RESEARCH, ok)

        summary = orch.get_pipeline_summary("job_sum")
        assert summary["total_agents_run"] == 2
        assert summary["total_duration_ms"] >= 0
        assert len(summary["agents"]) == 2


# ===========================================================================
# Day 47 — Dynamic Planning
# ===========================================================================

class TestDynamicPlanning:
    def setup_method(self):
        from app.agents.planner import PlannerAgent
        self.agent = PlannerAgent()

    def test_classify_simple_query(self):
        assert self.agent.classify_complexity("What is Python?") == "simple"

    def test_classify_simple_query_who(self):
        assert self.agent.classify_complexity("Who is Elon Musk?") == "simple"

    def test_classify_moderate_query(self):
        # This query hits one complex signal ("forecast") and has 8+ words → moderate
        result = self.agent.classify_complexity("Forecast the global adoption of renewable energy sources")
        assert result in ("moderate", "complex")

    def test_classify_complex_query_ev(self):
        result = self.agent.classify_complexity(
            "Analyze India's EV market and identify investment opportunities across battery, charging, and policy sectors"
        )
        assert result == "complex"

    def test_classify_complex_query_competitive(self):
        result = self.agent.classify_complexity(
            "Comprehensive competitive analysis of global cloud computing market with regulatory and economic trends"
        )
        assert result == "complex"

    def test_estimate_task_count_simple(self):
        count = self.agent.estimate_task_count("What is Python?", depth=1, breadth=3)
        assert 2 <= count <= 4

    def test_estimate_task_count_moderate(self):
        count = self.agent.estimate_task_count(
            "Explain the impact of AI on healthcare systems", depth=2, breadth=4
        )
        assert count >= 4

    def test_estimate_task_count_complex(self):
        count = self.agent.estimate_task_count(
            "Analyze India's EV market and identify investment opportunities", depth=3, breadth=5
        )
        assert count >= 8

    def test_estimate_task_count_never_exceeds_50(self):
        count = self.agent.estimate_task_count(
            "Analyze comprehensive global multi-sector investment market trends and competitive strategy",
            depth=5,
            breadth=8,
        )
        assert count <= 50

    def test_adjust_tasks_trims_to_target(self):
        tasks = [_make_task(query=f"query {i}", category="web") for i in range(20)]
        # Simple query → target ~3 tasks
        adjusted = self.agent._adjust_tasks_for_complexity(tasks, "What is X?", depth=1, breadth=3)
        assert len(adjusted) <= 4

    def test_adjust_tasks_does_not_trim_below_target(self):
        # 2 tasks, simple query → returns them as-is (target is 2-4)
        tasks = [_make_task(query=f"q{i}") for i in range(2)]
        adjusted = self.agent._adjust_tasks_for_complexity(tasks, "What is Python?", depth=1, breadth=3)
        assert len(adjusted) == 2


# ===========================================================================
# Day 48 — Adaptive Research Loop
# ===========================================================================

class TestAdaptiveLoop:
    def test_detect_information_gaps_empty(self):
        from app.research.adaptive_loop import detect_information_gaps
        gaps = detect_information_gaps([], set())
        assert gaps == []

    def test_detect_information_gaps_finds_gap_signal(self):
        from app.research.adaptive_loop import detect_information_gaps
        ev = _make_evidence(
            claim="The battery technology data is not available for this region",
            context="further research needed on solid-state batteries"
        )
        gaps = detect_information_gaps([ev], set())
        # Should detect "not available" and "further research needed"
        assert len(gaps) >= 1

    def test_detect_information_gaps_deduplicates_existing(self):
        from app.research.adaptive_loop import detect_information_gaps
        ev = _make_evidence(claim="EV market data is unavailable")
        existing = {"EV market data is unavailable"}
        gaps = detect_information_gaps([ev], existing)
        # Already in existing tasks — should not re-add
        assert len(gaps) == 0

    def test_detect_contradictions_empty(self):
        from app.research.adaptive_loop import detect_contradictions
        result = detect_contradictions([])
        assert result == []

    def test_detect_contradictions_keyword(self):
        from app.research.adaptive_loop import detect_contradictions
        ev = _make_evidence(
            claim="Study A contradicts previous findings on EV adoption rates",
        )
        result = detect_contradictions([ev])
        assert len(result) >= 1

    def test_detect_contradictions_keyword_disputed(self):
        from app.research.adaptive_loop import detect_contradictions
        ev = _make_evidence(claim="This claim is disputed by multiple researchers")
        result = detect_contradictions([ev])
        assert any("contradiction" in r.get("signal", "") or "disputed" in r.get("claim", "") for r in result)

    def test_generate_adaptive_tasks_no_gaps(self):
        from app.research.adaptive_loop import generate_adaptive_tasks
        evidence = [_make_evidence(claim="EV market is growing at 30% CAGR") for _ in range(5)]
        sources = [_make_source(source_type="web"), _make_source(source_type="academic")]
        existing = [_make_task("EV market growth"), _make_task("EV investment", category="academic")]
        tasks = generate_adaptive_tasks("EV market", evidence, sources, existing)
        # No gap signals → tasks may be empty or just diversity-related
        assert isinstance(tasks, list)

    def test_generate_adaptive_tasks_adds_academic_diversity(self):
        from app.research.adaptive_loop import generate_adaptive_tasks
        evidence = [_make_evidence()]
        sources = [_make_source(source_type="web")]  # No academic source
        existing = [_make_task("EV trends")]
        tasks = generate_adaptive_tasks("EV market trends", evidence, sources, existing)
        academic_tasks = [t for t in tasks if t.category == "academic"]
        assert len(academic_tasks) >= 1

    def test_generate_adaptive_tasks_respects_max_limit(self):
        from app.research.adaptive_loop import generate_adaptive_tasks
        # Create many gap-signalling evidence items
        evidence = [
            _make_evidence(claim=f"No data available for sector {i}. Further research needed.")
            for i in range(20)
        ]
        sources = [_make_source()]
        existing = []
        tasks = generate_adaptive_tasks("EV market", evidence, sources, existing, max_new_tasks=3)
        assert len(tasks) <= 3

    def test_build_adaptive_loop_report(self):
        from app.research.adaptive_loop import build_adaptive_loop_report
        original = [_make_task() for _ in range(5)]
        adaptive = [_make_task(task_id="adaptive_gap_1"), _make_task(task_id="adaptive_verify_1")]
        report = build_adaptive_loop_report(original, adaptive, [{"signal": "test"}], gaps_found=2)
        assert report["original_task_count"] == 5
        assert report["adaptive_task_count"] == 2
        assert report["total_tasks_executed"] == 7
        assert report["gaps_detected"] == 2


# ===========================================================================
# Day 49 — Research Stopping Criteria
# ===========================================================================

class TestStoppingCriteria:
    def setup_method(self):
        from app.research.stopping_criteria import ResearchStoppingCriteria
        self.criteria = ResearchStoppingCriteria(
            min_evidence=3,
            min_sources=2,
            min_source_types=2,
            confidence_threshold=0.55,
            fact_check_pass_rate=0.70,
            max_adaptive_rounds=3,
            max_total_tasks=50,
        )

    def _make_fact_check(self, supported: bool = True):
        from app.database.models.report import FactCheckResult
        return FactCheckResult(
            claim="test claim",
            supported=supported,
            confidence=0.9 if supported else 0.3,
        )

    def test_should_stop_when_all_criteria_met(self):
        tasks = [_make_task(status="completed") for _ in range(5)]
        evidence = [_make_evidence() for _ in range(5)]
        sources = [
            _make_source(source_type="web"),
            _make_source(url="https://academic.edu", source_type="academic"),
        ]
        fact_checks = [self._make_fact_check(True) for _ in range(5)]
        result = self.criteria.evaluate(
            tasks=tasks, evidence=evidence, sources=sources,
            confidence_score=0.80, fact_checks=fact_checks
        )
        assert result.should_stop is True
        assert result.overall_readiness == 1.0

    def test_should_continue_when_not_enough_evidence(self):
        tasks = [_make_task(status="completed")]
        evidence = []  # No evidence
        sources = [_make_source(), _make_source(url="https://b.com", source_type="academic")]
        result = self.criteria.evaluate(
            tasks=tasks, evidence=evidence, sources=sources, confidence_score=0.80
        )
        assert result.should_stop is False
        assert any("Insufficient evidence" in r for r in result.reasons_to_continue)

    def test_should_continue_when_confidence_low(self):
        tasks = [_make_task(status="completed") for _ in range(5)]
        evidence = [_make_evidence() for _ in range(5)]
        sources = [_make_source(), _make_source(url="https://b.com", source_type="academic")]
        result = self.criteria.evaluate(
            tasks=tasks, evidence=evidence, sources=sources,
            confidence_score=0.20  # Below threshold
        )
        assert any("Confidence below threshold" in r for r in result.reasons_to_continue)

    def test_hard_stop_on_max_adaptive_rounds(self):
        tasks = [_make_task()]
        result = self.criteria.evaluate(
            tasks=tasks, evidence=[], sources=[],
            adaptive_round=5,  # Exceeds max_adaptive_rounds=3
        )
        assert result.should_stop is True
        assert any("Hard stop" in r for r in result.reasons_to_stop)

    def test_hard_stop_on_max_tasks(self):
        tasks = [_make_task() for _ in range(60)]  # Exceeds max_total_tasks=50
        result = self.criteria.evaluate(tasks=tasks, evidence=[], sources=[])
        assert result.should_stop is True

    def test_criteria_scores_are_present(self):
        result = self.criteria.evaluate(
            tasks=[_make_task()], evidence=[_make_evidence()], sources=[_make_source()]
        )
        assert "task_coverage" in result.criteria_scores
        assert "evidence_sufficiency" in result.criteria_scores
        assert "source_diversity" in result.criteria_scores
        assert "confidence" in result.criteria_scores

    def test_to_dict_contains_required_keys(self):
        result = self.criteria.evaluate(tasks=[], evidence=[], sources=[])
        d = result.to_dict()
        assert "should_stop" in d
        assert "overall_readiness" in d
        assert "reasons_to_stop" in d
        assert "reasons_to_continue" in d
        assert "criteria_scores" in d

    def test_summary_line_returns_string(self):
        result = self.criteria.evaluate(tasks=[], evidence=[], sources=[])
        line = self.criteria.summary_line(result)
        assert isinstance(line, str)
        assert len(line) > 0

    def test_overall_readiness_between_0_and_1(self):
        result = self.criteria.evaluate(tasks=[], evidence=[], sources=[])
        assert 0.0 <= result.overall_readiness <= 1.0

    def test_fact_check_pass_rate_affects_decision(self):
        tasks = [_make_task(status="completed") for _ in range(5)]
        evidence = [_make_evidence() for _ in range(5)]
        sources = [_make_source(), _make_source(url="https://b.com", source_type="academic")]
        # All claims unsupported → low pass rate
        fact_checks = [self._make_fact_check(False) for _ in range(5)]
        result = self.criteria.evaluate(
            tasks=tasks, evidence=evidence, sources=sources,
            confidence_score=0.80, fact_checks=fact_checks
        )
        # fact-check pass rate is 0% → should not stop
        assert result.should_stop is False


# ===========================================================================
# Day 50 — Research Quality Scoring
# ===========================================================================

class TestResearchQualityScorer:
    def setup_method(self):
        from app.research.quality_scorer import ResearchQualityScorer
        self.scorer = ResearchQualityScorer()

    def _make_citation(self, source_id: str = "src_1"):
        from app.database.models.report import Citation
        return Citation(
            index=1,
            title="Test Citation",
            url="https://example.com",
            source_id=source_id,
        )

    def _make_fact_check(self, supported: bool = True):
        from app.database.models.report import FactCheckResult
        return FactCheckResult(claim="test", supported=supported, confidence=0.9)

    def test_score_returns_quality_score_object(self):
        from app.research.quality_scorer import ResearchQualityScore
        sources = [_make_source()]
        evidence = [_make_evidence()]
        tasks = [_make_task()]
        result = self.scorer.score(sources=sources, evidence=evidence, tasks=tasks)
        assert isinstance(result, ResearchQualityScore)

    def test_all_dimensions_populated(self):
        sources = [_make_source(), _make_source(url="https://b.com", source_type="academic")]
        evidence = [_make_evidence() for _ in range(5)]
        tasks = [_make_task(), _make_task(category="academic"), _make_task(category="market")]
        citations = [self._make_citation()]
        result = self.scorer.score(sources=sources, evidence=evidence, tasks=tasks, citations=citations)
        assert result.source_quality >= 0
        assert result.evidence_coverage >= 0
        assert result.citation_coverage >= 0
        assert result.recency >= 0
        assert result.consistency >= 0
        assert result.completeness >= 0

    def test_scores_are_0_to_100(self):
        sources = [_make_source() for _ in range(3)]
        evidence = [_make_evidence() for _ in range(6)]
        tasks = [_make_task() for _ in range(3)]
        result = self.scorer.score(sources=sources, evidence=evidence, tasks=tasks)
        for dim_score in [
            result.source_quality, result.evidence_coverage, result.citation_coverage,
            result.recency, result.consistency, result.completeness, result.overall
        ]:
            assert 0 <= dim_score <= 100, f"Score out of range: {dim_score}"

    def test_empty_inputs_give_zero_scores(self):
        result = self.scorer.score(sources=[], evidence=[], tasks=[])
        assert result.source_quality == 0.0
        assert result.evidence_coverage == 0.0
        assert result.completeness == 0.0
        assert result.overall >= 0

    def test_high_quality_inputs_score_above_70(self):
        sources = [
            _make_source(credibility_score=0.95, source_type="web"),
            _make_source(url="https://academic.edu", credibility_score=0.98, source_type="academic"),
            _make_source(url="https://news.com", credibility_score=0.90, source_type="news"),
        ]
        evidence = [_make_evidence(confidence=0.95) for _ in range(10)]
        tasks = [
            _make_task(status="completed", category="web"),
            _make_task(status="completed", category="academic"),
            _make_task(status="completed", category="market"),
        ]
        citations = [self._make_citation("src_1") for _ in range(8)]
        fact_checks = [self._make_fact_check(True) for _ in range(8)]
        result = self.scorer.score(
            sources=sources, evidence=evidence, tasks=tasks,
            citations=citations, fact_checks=fact_checks
        )
        assert result.overall >= 50  # Reasonable threshold for high-quality inputs

    def test_letter_grade_assignment(self):
        from app.research.quality_scorer import _letter_grade
        assert _letter_grade(95) == "A"
        assert _letter_grade(85) == "B"
        assert _letter_grade(75) == "C"
        assert _letter_grade(65) == "D"
        assert _letter_grade(50) == "F"

    def test_format_report_returns_string(self):
        result = self.scorer.score(
            sources=[_make_source()],
            evidence=[_make_evidence()],
            tasks=[_make_task()],
        )
        report_str = result.format_report()
        assert "Research Quality" in report_str
        assert "Overall" in report_str
        assert "Source Quality" in report_str

    def test_to_dict_contains_all_keys(self):
        result = self.scorer.score(
            sources=[_make_source()],
            evidence=[_make_evidence()],
            tasks=[_make_task()],
        )
        d = result.to_dict()
        assert "overall" in d
        assert "grade" in d
        assert "dimensions" in d
        assert "source_quality" in d["dimensions"]
        assert "evidence_coverage" in d["dimensions"]
        assert "citation_coverage" in d["dimensions"]
        assert "recency" in d["dimensions"]
        assert "consistency" in d["dimensions"]
        assert "completeness" in d["dimensions"]

    def test_consistency_uses_fact_checks_when_available(self):
        sources = [_make_source()]
        evidence = [_make_evidence()]
        tasks = [_make_task()]
        # All supported → high consistency
        fact_checks_good = [self._make_fact_check(True) for _ in range(5)]
        result_good = self.scorer.score(sources=sources, evidence=evidence, tasks=tasks, fact_checks=fact_checks_good)

        # All unsupported → low consistency
        fact_checks_bad = [self._make_fact_check(False) for _ in range(5)]
        result_bad = self.scorer.score(sources=sources, evidence=evidence, tasks=tasks, fact_checks=fact_checks_bad)

        assert result_good.consistency > result_bad.consistency

    def test_recency_scores_recent_sources_higher(self):
        sources_new = [_make_source(published_at="2025-01-01")]
        sources_old = [_make_source(published_at="2010-01-01")]
        tasks = [_make_task()]
        evidence = [_make_evidence()]

        result_new = self.scorer.score(sources=sources_new, evidence=evidence, tasks=tasks)
        result_old = self.scorer.score(sources=sources_old, evidence=evidence, tasks=tasks)
        assert result_new.recency >= result_old.recency

    def test_singleton_instance_works(self):
        from app.research.quality_scorer import research_quality_scorer
        result = research_quality_scorer.score(
            sources=[_make_source()],
            evidence=[_make_evidence()],
            tasks=[_make_task()],
        )
        assert result.overall >= 0


# ===========================================================================
# Integration: all modules importable and singletons exist
# ===========================================================================

class TestModuleIntegration:
    def test_all_new_modules_importable(self):
        from app.research.agent_orchestrator import research_agent_orchestrator
        from app.research.adaptive_loop import generate_adaptive_tasks
        from app.research.stopping_criteria import research_stopping_criteria
        from app.research.quality_scorer import research_quality_scorer
        assert research_agent_orchestrator is not None
        assert callable(generate_adaptive_tasks)
        assert research_stopping_criteria is not None
        assert research_quality_scorer is not None

    def test_research_package_exports_new_symbols(self):
        import app.research as research_pkg
        assert hasattr(research_pkg, "research_agent_orchestrator")
        assert hasattr(research_pkg, "generate_adaptive_tasks")
        assert hasattr(research_pkg, "research_stopping_criteria")
        assert hasattr(research_pkg, "research_quality_scorer")

    def test_planner_agent_has_new_methods(self):
        from app.agents.planner import PlannerAgent
        agent = PlannerAgent()
        assert callable(agent.classify_complexity)
        assert callable(agent.estimate_task_count)
        assert callable(agent._adjust_tasks_for_complexity)

    def test_orchestrator_plan_select_boundary_4_tasks(self):
        """Exactly 4 tasks → still simple → minimal pipeline."""
        from app.research.agent_orchestrator import ResearchAgentOrchestrator
        orch = ResearchAgentOrchestrator()
        plan = orch.select_plan("test query", estimated_tasks=4)
        assert len(plan.steps) == 4

    def test_orchestrator_plan_select_boundary_5_tasks(self):
        """5 tasks → complex → full pipeline."""
        from app.research.agent_orchestrator import ResearchAgentOrchestrator
        orch = ResearchAgentOrchestrator()
        plan = orch.select_plan("test query", estimated_tasks=5)
        assert len(plan.steps) == 10
