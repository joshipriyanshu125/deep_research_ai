"""
Day 28 — Fact-checking Agent Test Suite
Comprehensive testing for:
  Claim -> Find supporting evidence -> Compare sources -> Check contradiction -> Confidence
"""

import pytest
from unittest.mock import AsyncMock, patch
from app.database.models.source import Source, SourceType
from app.database.models.evidence import Evidence
from app.database.models.report import FactCheckResult
from app.agents.fact_checker import FactCheckerAgent, fact_checker_agent


@pytest.fixture
def sample_sources():
    return [
        Source(
            id="src-101",
            research_id="res-001",
            url="https://siam.org/ev-report-2025",
            title="SIAM Annual EV Statistical Report 2025",
            domain="siam.org",
            type=SourceType.WEB,
            credibility_score=0.92,
        ),
        Source(
            id="src-102",
            research_id="res-001",
            url="https://bloomberg.com/auto/india-ev",
            title="Bloomberg Green Mobility Tracker",
            domain="bloomberg.com",
            type=SourceType.WEB,
            credibility_score=0.88,
        ),
        Source(
            id="src-103",
            research_id="res-001",
            url="https://nature.com/articles/energy-review",
            title="Nature Energy - Global Electric Transition",
            domain="nature.com",
            type=SourceType.ACADEMIC,
            credibility_score=0.98,
        ),
    ]


@pytest.fixture
def sample_evidence(sample_sources):
    return [
        Evidence(
            id="ev-01",
            research_id="res-001",
            source_id="src-101",
            source_url="https://siam.org/ev-report-2025",
            source_title="SIAM Annual EV Statistical Report 2025",
            claim="EV sales in India grew by 45% YoY in 2025",
            quote="Official registration figures indicate EV sales in India grew by 45% YoY in 2025.",
            evidence="Official registration figures indicate EV sales in India grew by 45% YoY in 2025.",
            confidence=0.95,
            metrics=["45% YoY", "2025"],
            supporting_entities=["India", "SIAM"],
            verification_status="verified",
        ),
        Evidence(
            id="ev-02",
            research_id="res-001",
            source_id="src-102",
            source_url="https://bloomberg.com/auto/india-ev",
            source_title="Bloomberg Green Mobility Tracker",
            claim="Indian EV registrations expanded over 40% throughout 2025",
            quote="Bloomberg tracker recorded an expansion in Indian EV registrations exceeding 40% in 2025.",
            evidence="Bloomberg tracker recorded an expansion in Indian EV registrations exceeding 40% in 2025.",
            confidence=0.90,
            metrics=["40%", "2025"],
            supporting_entities=["India"],
            verification_status="verified",
        ),
        Evidence(
            id="ev-03",
            research_id="res-001",
            source_id="src-103",
            source_url="https://nature.com/articles/energy-review",
            source_title="Nature Energy - Global Electric Transition",
            claim="Solid-state battery energy density reached 450 Wh/kg in laboratory prototypes",
            quote="Laboratory prototypes of solid-state cells achieved 450 Wh/kg specific energy density.",
            evidence="Laboratory prototypes of solid-state cells achieved 450 Wh/kg specific energy density.",
            confidence=0.96,
            metrics=["450 Wh/kg"],
            supporting_entities=["Nature"],
            verification_status="verified",
        ),
    ]


class TestFactCheckerEvidenceRetrieval:
    def test_find_supporting_evidence_direct_match(self, sample_evidence):
        agent = FactCheckerAgent()
        matches = agent.find_supporting_evidence(
            claim="EV sales in India grew by 45% YoY in 2025",
            evidence_pool=sample_evidence,
        )
        assert len(matches) >= 1
        assert matches[0].id == "ev-01"

    def test_find_supporting_evidence_semantic_token_overlap(self, sample_evidence):
        agent = FactCheckerAgent()
        matches = agent.find_supporting_evidence(
            claim="EV market growth in India in 2025",
            evidence_pool=sample_evidence,
        )
        assert len(matches) >= 1
        # Matches EV sales in India
        found_ids = [m.id for m in matches]
        assert "ev-01" in found_ids or "ev-02" in found_ids

    def test_find_supporting_evidence_empty_pool(self):
        agent = FactCheckerAgent()
        matches = agent.find_supporting_evidence(claim="Any claim", evidence_pool=[])
        assert matches == []


class TestFactCheckerSourceComparison:
    def test_compare_sources_aggregates_unique_sources(self, sample_evidence, sample_sources):
        agent = FactCheckerAgent()
        # ev-01 and ev-02 are from src-101 and src-102
        comp = agent.compare_sources(sample_evidence[:2], sample_sources)
        assert comp["distinct_source_count"] == 2
        assert "https://siam.org/ev-report-2025" in comp["unique_sources"]
        assert "https://bloomberg.com/auto/india-ev" in comp["unique_sources"]
        assert comp["avg_credibility"] == pytest.approx(0.90, rel=1e-2)

    def test_compare_sources_without_sources_list(self, sample_evidence):
        agent = FactCheckerAgent()
        comp = agent.compare_sources(sample_evidence[:1], sources=None)
        assert comp["distinct_source_count"] == 1
        assert comp["unique_sources"][0] == "https://siam.org/ev-report-2025"


class TestFactCheckerContradictionDetection:
    def test_detect_no_contradictions_on_aligned_evidence(self, sample_evidence):
        agent = FactCheckerAgent()
        contradictions = agent.check_contradictions(
            claim="EV sales in India increased in 2025",
            supporting_evidences=sample_evidence[:2],
        )
        assert len(contradictions) == 0

    def test_detect_contradiction_on_opposing_trend(self, sample_evidence):
        agent = FactCheckerAgent()
        conflicting_ev = Evidence(
            id="ev-dispute",
            source_id="src-999",
            claim="EV sales in India suffered severe decline and dropped in 2025",
            quote="Registrations collapsed and EV sales dropped sharply.",
            confidence=0.75,
            verification_status="disputed",
        )
        contradictions = agent.check_contradictions(
            claim="EV sales in India grew and increased in 2025",
            supporting_evidences=[conflicting_ev],
            evidence_pool=sample_evidence + [conflicting_ev],
        )
        assert len(contradictions) > 0
        assert any("disputed" in c.lower() or "conflicting" in c.lower() for c in contradictions)


class TestFactCheckerConfidenceCalculation:
    def test_confidence_boosted_by_multi_source(self, sample_evidence):
        agent = FactCheckerAgent()
        # 1 source vs 3 sources
        conf_single = agent.calculate_confidence(
            supporting_evidences=sample_evidence[:1],
            distinct_source_count=1,
            contradictions=[],
            avg_source_credibility=0.90,
        )
        conf_multi = agent.calculate_confidence(
            supporting_evidences=sample_evidence,
            distinct_source_count=3,
            contradictions=[],
            avg_source_credibility=0.90,
        )
        assert conf_multi > conf_single
        assert 0.0 <= conf_multi <= 1.0

    def test_confidence_penalized_by_contradiction(self, sample_evidence):
        agent = FactCheckerAgent()
        conf_clean = agent.calculate_confidence(
            supporting_evidences=sample_evidence[:2],
            distinct_source_count=2,
            contradictions=[],
            avg_source_credibility=0.90,
        )
        conf_contradicted = agent.calculate_confidence(
            supporting_evidences=sample_evidence[:2],
            distinct_source_count=2,
            contradictions=["Conflicting data point in report B"],
            avg_source_credibility=0.90,
        )
        assert conf_contradicted < conf_clean


@pytest.mark.asyncio
class TestFactCheckerPipeline:
    async def test_fact_check_claim_supported(self, sample_evidence, sample_sources):
        agent = FactCheckerAgent()
        result: FactCheckResult = await agent.fact_check_claim(
            claim="EV sales in India grew by 45% YoY in 2025",
            evidence_pool=sample_evidence,
            sources=sample_sources,
        )
        assert result.claim == "EV sales in India grew by 45% YoY in 2025"
        assert result.supported is True
        assert result.confidence >= 0.85
        assert len(result.sources) >= 1
        assert "https://siam.org/ev-report-2025" in result.sources

        # Output format check matching Day 28 spec
        out_dict = result.to_dict()
        assert "claim" in out_dict
        assert "supported" in out_dict
        assert "confidence" in out_dict
        assert "sources" in out_dict
        assert isinstance(out_dict["sources"], list)
        assert isinstance(out_dict["supported"], bool)
        assert isinstance(out_dict["confidence"], float)

    async def test_fact_check_claim_unsupported_missing_evidence(self, sample_sources):
        agent = FactCheckerAgent()
        result: FactCheckResult = await agent.fact_check_claim(
            claim="Commercial fusion reactors powered 30% of global grids in 2025",
            evidence_pool=[],
            sources=sample_sources,
        )
        assert result.supported is False
        assert result.confidence <= 0.50
        assert result.sources == []

    async def test_fact_check_batch(self, sample_evidence, sample_sources):
        agent = FactCheckerAgent()
        claims = [
            "EV sales in India grew by 45% YoY in 2025",
            "Solid-state battery energy density reached 450 Wh/kg in laboratory prototypes",
        ]
        results = await agent.fact_check_batch(claims, sample_evidence, sample_sources)
        assert len(results) == 2
        assert all(r.supported is True for r in results)
        assert all(isinstance(r, FactCheckResult) for r in results)

    async def test_verify_evidence_backward_compatibility(self, sample_evidence, sample_sources):
        agent = FactCheckerAgent()
        verified = await agent.verify_evidence(sample_evidence, sample_sources)
        assert len(verified) == 3
        for ev in verified:
            assert ev.verification_status in ("verified", "disputed", "unverified")
            assert 0.0 <= ev.confidence <= 1.0
            assert "fact_check" in ev.metadata

    async def test_fact_check_with_llm_mock(self, sample_evidence, sample_sources):
        agent = FactCheckerAgent()
        mock_llm_json = """
        {
          "claim": "EV sales in India grew by 45% YoY in 2025",
          "supported": true,
          "confidence": 0.94,
          "sources": ["https://siam.org/ev-report-2025"],
          "contradictions": [],
          "reasoning": "Directly confirmed by SIAM statistical annual data."
        }
        """
        with patch.object(agent.llm, "execute_prompt", new=AsyncMock(return_value=mock_llm_json)):
            result = await agent.fact_check_claim(
                claim="EV sales in India grew by 45% YoY in 2025",
                evidence_pool=sample_evidence,
                sources=sample_sources,
                use_llm=True,
            )
            assert result.supported is True
            assert result.confidence == 0.94
            assert "SIAM" in result.reasoning
