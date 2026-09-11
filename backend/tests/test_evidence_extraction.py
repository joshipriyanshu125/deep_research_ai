"""
Day 18 — Evidence Extraction Test Suite
Comprehensive testing for:
  Source -> Relevant Passage -> Evidence -> Grounded Claim
"""

import pytest
from unittest.mock import AsyncMock, patch
from app.database.models.source import Source, SourceType
from app.database.models.evidence import Evidence
from app.research.evidence import (
    PassageExtractor,
    HeuristicEvidenceExtractor,
    EvidenceExtractor,
    evidence_extractor,
)
from app.database.repositories.evidence_repo import EvidenceRepository, evidence_repo


class TestEvidenceModel:
    def test_evidence_model_dual_alias_quote_and_evidence(self):
        ev = Evidence(
            research_id="res-101",
            source_id="src-001",
            claim="EV sales in India grew by 45% YoY in 2025",
            evidence="According to SIAM records, EV sales in India grew by 45% YoY in 2025.",
            confidence=0.94,
        )
        assert ev.claim == "EV sales in India grew by 45% YoY in 2025"
        assert ev.evidence == "According to SIAM records, EV sales in India grew by 45% YoY in 2025."
        assert ev.quote == "According to SIAM records, EV sales in India grew by 45% YoY in 2025."
        assert ev.confidence == 0.94
        assert ev.source_id == "src-001"

    def test_evidence_model_instantiated_with_quote(self):
        ev = Evidence(
            research_id="res-102",
            source_id="src-002",
            claim="Solid-state batteries reach 450 Wh/kg",
            quote="Laboratory testing demonstrated that solid-state batteries reach 450 Wh/kg.",
            confidence=0.96,
        )
        assert ev.evidence == "Laboratory testing demonstrated that solid-state batteries reach 450 Wh/kg."
        assert ev.quote == "Laboratory testing demonstrated that solid-state batteries reach 450 Wh/kg."

    def test_to_claim_dict_format(self):
        ev = Evidence(
            research_id="res-103",
            source_id="src-003",
            claim="EV sales increased 45%",
            evidence="Relevant extracted passage on EV sales...",
            confidence=0.94,
        )
        claim_dict = ev.to_claim_dict()
        assert claim_dict == {
            "claim": "EV sales increased 45%",
            "evidence": "Relevant extracted passage on EV sales...",
            "source_id": "src-003",
            "confidence": 0.94,
        }

    def test_confidence_clamping(self):
        ev_high = Evidence(source_id="s1", claim="c1", quote="q1", confidence=1.5)
        assert ev_high.confidence == 1.0

        ev_low = Evidence(source_id="s2", claim="c2", quote="q2", confidence=-0.5)
        assert ev_low.confidence == 0.0


class TestPassageExtractor:
    def test_segment_into_passages(self):
        extractor = PassageExtractor(min_passage_length=30)
        raw_text = """The Indian electric vehicle market is witnessing unprecedented momentum in 2026.
Government policies and subsidies have accelerated domestic battery cell manufacturing.

According to NITI Aayog forecasts, electric two-wheeler adoption will surpass 50% by 2030.
Key manufacturers are expanding annual production capacity to meet growing consumer demand.

Subscribe to newsletter and all rights reserved.

A third paragraph discussing solid-state battery research and public charging infrastructure across highways."""

        passages = extractor.segment_into_passages(raw_text)
        assert len(passages) >= 2
        # Boilerplate should be filtered
        assert not any("subscribe to newsletter" in p.lower() for p in passages)

    def test_rank_passages_by_metrics_and_topic(self):
        extractor = PassageExtractor()
        passages = [
            "This is a generic overview of automotive technologies without numbers.",
            "EV two-wheeler sales reached 1,200,000 units in 2025, showing a 45% increase YoY.",
            "Government allocated ₹10,000 crore for electric vehicle charging infrastructure.",
        ]
        ranked = extractor.rank_passages(passages, topic="EV sales growth")
        assert len(ranked) == 3
        top_passage, top_score = ranked[0]
        assert "45%" in top_passage or "1,200,000" in top_passage
        assert top_score > 0.6


class TestHeuristicEvidenceExtractor:
    def test_extract_statistic_evidence(self):
        extractor = HeuristicEvidenceExtractor()
        sentence = "In fiscal year 2025, commercial EV registrations increased by 38.5% reaching 150,000 units across India."
        ev = extractor.extract_from_sentence(
            sentence=sentence,
            source_id="src-test-1",
            research_id="res-test",
            base_confidence=0.90,
            sub_topic="Commercial EV Growth",
        )
        assert ev is not None
        assert ev.source_id == "src-test-1"
        assert "38.5%" in ev.metrics or "150,000 units" in ev.metrics
        assert ev.evidence_type == "statistic"
        assert ev.confidence >= 0.90
        assert ev.quote == sentence

    def test_extract_currency_and_investment_evidence(self):
        extractor = HeuristicEvidenceExtractor()
        sentence = "The Ministry of Heavy Industries approved ₹10,900 crore under the PM E-DRIVE scheme for EV adoption."
        ev = extractor.extract_from_sentence(
            sentence=sentence,
            source_id="src-test-2",
            research_id="res-test",
            base_confidence=0.92,
        )
        assert ev is not None
        assert ev.evidence_type in ("statistic", "policy_event")
        assert any("₹10,900" in m or "crore" in m for m in ev.metrics)

    def test_reject_low_entropy_or_noise(self):
        extractor = HeuristicEvidenceExtractor()
        assert extractor.extract_from_sentence("Click here to read more.", source_id="s") is None
        assert extractor.extract_from_sentence("Cars are nice.", source_id="s") is None


class TestEvidenceExtractorPipeline:
    def test_extract_evidence_from_source(self):
        src = Source(
            source_id="src-auto-1",
            research_id="res-auto",
            url="https://autocarpro.in/news/ev-sales-surge",
            title="India EV Sales Surge in 2025",
            content="""India recorded total EV sales of 1,530,000 units in 2025, representing a 42% YoY growth rate.
Tata Motors maintained a 68% market share in the electric passenger vehicle segment.
The fast-charging network expanded by 120% with over 8,500 public stations installed nationwide.""",
            credibility_score=0.92,
        )

        evidence_items = evidence_extractor.extract_evidence(src, research_id="res-auto", max_evidence=5)
        assert len(evidence_items) >= 2
        for ev in evidence_items:
            assert isinstance(ev, Evidence)
            assert ev.source_id == "src-auto-1"
            assert ev.research_id == "res-auto"
            assert ev.quote
            assert ev.claim
            assert ev.confidence >= 0.85
            # Test claim dict serialization
            claim_dict = ev.to_claim_dict()
            assert "claim" in claim_dict
            assert "evidence" in claim_dict
            assert "source_id" in claim_dict
            assert "confidence" in claim_dict

    def test_extract_evidence_batch(self):
        src1 = Source(
            source_id="src-b1",
            url="https://reuters.com/ev1",
            title="Reuters EV Market Update",
            content="Global battery pack prices dropped to $115 per kWh in 2025.",
            credibility_score=0.95,
        )
        src2 = Source(
            source_id="src-b2",
            url="https://bloomberg.com/ev2",
            title="Bloomberg Energy Outlook",
            content="Lithium iron phosphate chemistries captured 55% of global passenger EV sales.",
            credibility_score=0.95,
        )

        batch_results = evidence_extractor.extract_evidence_batch([src1, src2], research_id="res-batch")
        assert len(batch_results) >= 2
        source_ids = {e.source_id for e in batch_results}
        assert "src-b1" in source_ids
        assert "src-b2" in source_ids

    @pytest.mark.asyncio
    async def test_extract_evidence_async_with_llm(self):
        src = Source(
            source_id="src-llm-1",
            research_id="res-llm",
            url="https://niti.gov.in/ev-report",
            title="NITI Aayog EV Roadmap",
            content="NITI Aayog projects 70% of commercial vehicles and 80% of two-wheelers will be electric by 2030.",
            credibility_score=0.96,
        )

        # Mock LLM return
        mock_response = """{
            "claims": [
                {
                    "claim": "80% of two-wheelers in India will be electric by 2030.",
                    "evidence": "NITI Aayog projects 70% of commercial vehicles and 80% of two-wheelers will be electric by 2030.",
                    "confidence": 0.95,
                    "metrics": ["80%", "2030", "70%"],
                    "supporting_entities": ["NITI Aayog", "India"],
                    "evidence_type": "statistic"
                }
            ]
        }"""

        with patch("app.research.evidence.get_llm_service") as mock_get_llm:
            mock_service = AsyncMock()
            mock_service.execute_prompt.return_value = mock_response
            mock_get_llm.return_value = mock_service

            evidence_items = await evidence_extractor.extract_evidence_async(
                source=src,
                research_id="res-llm",
                topic="EV Adoption Targets",
                use_llm=True,
            )

            assert len(evidence_items) >= 1
            first_ev = evidence_items[0]
            assert "80%" in first_ev.claim or "two-wheelers" in first_ev.claim
            assert first_ev.source_id == "src-llm-1"
            assert first_ev.confidence >= 0.90


class TestEvidenceRepository:
    @pytest.mark.asyncio
    async def test_evidence_crud_and_querying(self):
        repo = EvidenceRepository()
        ev1 = Evidence(
            research_id="res-repo-1",
            source_id="src-repo-1",
            claim="EV sales grew 50%",
            quote="Market report indicates EV sales grew 50% YoY.",
            confidence=0.94,
            evidence_type="statistic",
        )
        ev2 = Evidence(
            research_id="res-repo-1",
            source_id="src-repo-2",
            claim="Battery plant established in Gujarat",
            quote="Tata announced a new battery Gigafactory in Gujarat.",
            confidence=0.88,
            evidence_type="policy_event",
        )

        await repo.create_evidence(ev1)
        await repo.create_evidence(ev2)

        # Retrieve single
        fetched = await repo.get_evidence(ev1.id)
        assert fetched is not None
        assert fetched.claim == "EV sales grew 50%"

        # Query by research
        all_res = await repo.get_evidence_by_research("res-repo-1")
        assert len(all_res) == 2

        # Query by source
        src1_ev = await repo.get_evidence_by_source("src-repo-1")
        assert len(src1_ev) == 1
        assert src1_ev[0].id == ev1.id

        # Query with confidence filter
        high_conf = await repo.get_evidence_by_research("res-repo-1", min_confidence=0.90)
        assert len(high_conf) == 1
        assert high_conf[0].id == ev1.id

        # Delete
        del_success = await repo.delete_evidence(ev1.id)
        assert del_success is True
        assert await repo.get_evidence(ev1.id) is None


class TestStrictGroundingHierarchy:
    """
    Validates:
      Source -> Relevant Passage -> Evidence -> Grounded Claim
    """
    def test_pipeline_hierarchy_flow(self):
        source = Source(
            source_id="src-hier-1",
            research_id="res-hier",
            url="https://economictimes.indiatimes.com/ev-growth",
            title="Electric Vehicle Boom in India",
            content="""
Industry experts note that consumer awareness regarding EV range anxiety has dropped by 40% since 2023.
Over 45,000 public chargers have been deployed across tier-1 and tier-2 cities.
Total annual battery pack investments reached $2.4 billion in 2025.
""",
            credibility_score=0.91,
        )

        # Step 1: Passage Extraction
        extractor = PassageExtractor()
        passages = extractor.segment_into_passages(source.content)
        assert len(passages) >= 1

        # Step 2: Evidence & Claim Extraction
        evidence_list = evidence_extractor.extract_evidence(source, research_id="res-hier")
        assert len(evidence_list) >= 2

        for ev in evidence_list:
            # Check claim is backed by quote in the source text
            assert ev.quote in source.content
            assert ev.claim
            assert ev.confidence > 0.80

            # Match Day 18 output contract
            out = ev.to_claim_dict()
            assert "claim" in out
            assert "evidence" in out
            assert "source_id" in out
            assert "confidence" in out
            assert out["source_id"] == "src-hier-1"
            assert isinstance(out["confidence"], float)
