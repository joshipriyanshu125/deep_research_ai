"""
Day 27 — Synthesis Agent Test Suite
Comprehensive testing for multi-dimensional research synthesis:
  Input:
    Task results + Evidence + Sources + Previous context
  Output:
    Key findings, Market analysis, Trends, Opportunities, Risks, Contradictions, Uncertainty
"""

import pytest
from unittest.mock import AsyncMock, patch
from app.database.models.source import Source, SourceType
from app.database.models.evidence import Evidence
from app.database.models.research import ResearchTask
from app.database.models.report import (
    ResearchReport,
    ReportSection,
    Citation,
    CitationTrace,
    FactCheckResult,
)
from app.agents.synthesizer import (
    SynthesizerAgent,
    SynthesisResult,
    synthesizer_agent,
)


@pytest.fixture
def sample_sources():
    return [
        Source(
            id="src-001",
            research_id="res-synth-1",
            url="https://iea.org/reports/global-ev-outlook",
            title="Global EV Outlook 2025 - IEA",
            domain="iea.org",
            type=SourceType.WEB,
            credibility_score=0.95,
        ),
        Source(
            id="src-002",
            research_id="res-synth-1",
            url="https://nature.com/articles/solid-state-2025",
            title="Next-Gen Solid State Battery Architectures",
            domain="nature.com",
            type=SourceType.ACADEMIC,
            credibility_score=0.98,
        ),
        Source(
            id="src-003",
            research_id="res-synth-1",
            url="https://goldmansachs.com/insights/battery-capex",
            title="Battery Metal Capex and Supply Chain Projections",
            domain="goldmansachs.com",
            type=SourceType.WEB,
            credibility_score=0.91,
        ),
    ]


@pytest.fixture
def sample_evidence():
    return [
        Evidence(
            id="ev-001",
            research_id="res-synth-1",
            source_id="src-001",
            source_url="https://iea.org/reports/global-ev-outlook",
            source_title="Global EV Outlook 2025 - IEA",
            claim="Global EV sales reached 18.5 million units in 2025",
            quote="Global passenger electric vehicle registrations surpassed 18.5 million units in 2025.",
            evidence="Global passenger electric vehicle registrations surpassed 18.5 million units in 2025.",
            confidence=0.96,
            metrics=["18.5 million", "2025"],
            supporting_entities=["IEA"],
            verification_status="verified",
        ),
        Evidence(
            id="ev-002",
            research_id="res-synth-1",
            source_id="src-002",
            source_url="https://nature.com/articles/solid-state-2025",
            source_title="Next-Gen Solid State Battery Architectures",
            claim="Solid-state cells demonstrated 450 Wh/kg specific energy density in testing",
            quote="Laboratory prototypes of all-solid-state cells achieved 450 Wh/kg gravimetric energy density.",
            evidence="Laboratory prototypes of all-solid-state cells achieved 450 Wh/kg gravimetric energy density.",
            confidence=0.94,
            metrics=["450 Wh/kg"],
            supporting_entities=["Nature"],
            verification_status="verified",
        ),
        Evidence(
            id="ev-003",
            research_id="res-synth-1",
            source_id="src-003",
            source_url="https://goldmansachs.com/insights/battery-capex",
            source_title="Battery Metal Capex and Supply Chain Projections",
            claim="Lithium battery pack costs dropped below $85/kWh",
            quote="Volume manufacturing pushed average LFP battery pack prices to $84.50 per kilowatt-hour.",
            evidence="Volume manufacturing pushed average LFP battery pack prices to $84.50 per kilowatt-hour.",
            confidence=0.92,
            metrics=["$85/kWh", "$84.50"],
            supporting_entities=["Goldman Sachs"],
            verification_status="verified",
        ),
    ]


@pytest.fixture
def sample_task_results():
    return [
        ResearchTask(
            id="task-1",
            query="Global electric vehicle market sizing and growth",
            question="What is the global market volume of EVs in 2025?",
            category="market",
            status="completed",
            results_count=12,
        ),
        ResearchTask(
            id="task-2",
            query="Solid-state battery commercialization breakthroughs",
            question="What are recent solid-state battery energy density benchmarks?",
            category="academic",
            status="completed",
            results_count=8,
        ),
    ]


@pytest.fixture
def sample_fact_checks():
    return [
        FactCheckResult(
            claim="Global EV sales reached 18.5 million units in 2025",
            supported=True,
            confidence=0.96,
            sources=["https://iea.org/reports/global-ev-outlook"],
            contradictions=[],
            supporting_evidence=["Global passenger EV registrations surpassed 18.5 million..."],
        ),
        FactCheckResult(
            claim="Solid-state cells demonstrated 450 Wh/kg specific energy density in testing",
            supported=True,
            confidence=0.94,
            sources=["https://nature.com/articles/solid-state-2025"],
            contradictions=[],
            supporting_evidence=["Laboratory prototypes of all-solid-state cells achieved 450 Wh/kg..."],
        ),
    ]


class TestSynthesisResultModel:
    def test_synthesis_result_creation_and_to_dict(self):
        result = SynthesisResult(
            key_findings=["EV adoption accelerated 30% YoY", "Pack costs under $85/kWh"],
            market_analysis="Global EV market reached $620B with rising commercial penetration.",
            trends=["Adoption of 800V silicon-carbide architecture", "LFP cell chemistry dominance"],
            opportunities=["Fleet electrification", "Fast-charging corridor infrastructure"],
            risks=["Raw material geopolitical bottlenecks", "Grid transmission capacity constraints"],
            contradictions=["Commercial deployment timelines vary from 2026 to 2029"],
            uncertainty=["Cell degradation rates after 1500 fast-charge cycles"],
            executive_summary="Executive synthesis on EV battery transition.",
        )
        d = result.to_dict()
        assert len(d["key_findings"]) == 2
        assert "620B" in d["market_analysis"]
        assert len(d["trends"]) == 2
        assert len(d["opportunities"]) == 2
        assert len(d["risks"]) == 2
        assert len(d["contradictions"]) == 1
        assert len(d["uncertainty"]) == 1
        assert d["executive_summary"] == "Executive synthesis on EV battery transition."


@pytest.mark.asyncio
class TestSynthesizerAgent:
    async def test_synthesize_heuristic_combines_all_inputs(
        self,
        sample_sources,
        sample_evidence,
        sample_task_results,
        sample_fact_checks,
    ):
        agent = SynthesizerAgent()
        synthesis: SynthesisResult = await agent.synthesize(
            query="Next-Generation Electric Vehicles & Battery Technologies",
            evidence=sample_evidence,
            sources=sample_sources,
            task_results=sample_task_results,
            previous_context="Objective: Evaluate global EV growth and solid-state battery progress.",
            fact_checks=sample_fact_checks,
            use_llm=False,
        )

        # Verify all 7 required dimensions exist and are populated
        assert len(synthesis.key_findings) > 0
        assert len(synthesis.market_analysis) > 20
        assert len(synthesis.trends) > 0
        assert len(synthesis.opportunities) > 0
        assert len(synthesis.risks) > 0
        assert len(synthesis.contradictions) > 0
        assert len(synthesis.uncertainty) > 0
        assert len(synthesis.executive_summary) > 20

    async def test_synthesize_with_llm_json_mock(
        self,
        sample_sources,
        sample_evidence,
        sample_task_results,
        sample_fact_checks,
    ):
        agent = SynthesizerAgent()
        mock_llm_response = """
        {
          "key_findings": [
            "Global EV registrations exceeded 18.5 million in 2025",
            "Solid-state battery prototypes reached 450 Wh/kg",
            "Battery pack prices fell below $85/kWh threshold"
          ],
          "market_analysis": "The EV battery market is experiencing explosive double-digit growth driven by cost parity.",
          "trends": [
            "Structural battery pack integration (Cell-to-Chassis)",
            "Rapid expansion of Megawatt charging standards"
          ],
          "opportunities": [
            "Next-gen sodium-ion batteries for urban mobility",
            "Second-life grid storage applications"
          ],
          "risks": [
            "Grid distribution transformer overload",
            "Supply chain vulnerability in critical rare earths"
          ],
          "contradictions": [
            "Discrepancy between lab solid-state yields and pilot production projections"
          ],
          "uncertainty": [
            "Extreme sub-zero temperature retention in solid-state electrolytes"
          ],
          "executive_summary": "Comprehensive empirical synthesis of next-generation EV ecosystem."
        }
        """
        with patch.object(agent.llm, "execute_prompt", new=AsyncMock(return_value=mock_llm_response)):
            res: SynthesisResult = await agent.synthesize(
                query="EV Battery Tech 2025",
                evidence=sample_evidence,
                sources=sample_sources,
                task_results=sample_task_results,
                previous_context="Depth 2, Breadth 3",
                fact_checks=sample_fact_checks,
                use_llm=True,
            )
            assert len(res.key_findings) == 3
            assert "Cell-to-Chassis" in res.trends[0]
            assert "sodium-ion" in res.opportunities[0]
            assert "Grid distribution" in res.risks[0]
            assert "yields" in res.contradictions[0]
            assert "sub-zero" in res.uncertainty[0]

    async def test_synthesize_report_populates_all_dimensions(
        self,
        sample_sources,
        sample_evidence,
        sample_task_results,
        sample_fact_checks,
    ):
        agent = SynthesizerAgent()
        report: ResearchReport = await agent.synthesize_report(
            query="Next-Generation Electric Vehicles",
            sources=sample_sources,
            evidence=sample_evidence,
            task_results=sample_task_results,
            previous_context={"depth": 2, "breadth": 3},
            fact_checks=sample_fact_checks,
        )

        assert isinstance(report, ResearchReport)
        assert report.title == "Deep Research Report: Next-Generation Electric Vehicles"
        assert len(report.citations) >= 1
        assert len(report.traceability_matrix) >= 1
        assert len(report.sections) >= 5

        # Check Day 27 fields in ResearchReport
        assert len(report.key_findings) > 0
        assert report.market_analysis is not None
        assert len(report.trends) > 0
        assert len(report.opportunities) > 0
        assert len(report.risks) > 0
        assert len(report.contradictions) > 0
        assert len(report.uncertainty) > 0
        assert len(report.fact_checks) == 2
        assert report.quality_score >= 9.0

    async def test_synthesize_report_backward_compatibility_no_optional_args(
        self,
        sample_sources,
        sample_evidence,
    ):
        agent = SynthesizerAgent()
        # Backward-compatible call signature with only query, sources, evidence
        report: ResearchReport = await agent.synthesize_report(
            query="Quantum Computing Architecture",
            sources=sample_sources,
            evidence=sample_evidence,
        )
        assert isinstance(report, ResearchReport)
        assert report.title == "Deep Research Report: Quantum Computing Architecture"
        assert len(report.key_findings) > 0
        assert report.market_analysis is not None
        assert len(report.trends) > 0
        assert len(report.opportunities) > 0
        assert len(report.risks) > 0
        assert len(report.contradictions) > 0
        assert len(report.uncertainty) > 0
