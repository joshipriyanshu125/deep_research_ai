"""
Regression test suite covering the 4 instructor feedback points:
1. Evidence extraction corruption & snippet fallback
2. Eliminating generic AI template from report synthesis
3. Rejecting fake/placeholder TechCrunch sources
4. Fixing cross-region contradiction detection (India vs Canada) and repeated counting
"""
import pytest
from unittest.mock import AsyncMock, patch
from app.database.models.source import Source, SourceType
from app.database.models.evidence import Evidence
from app.research.source_validator import source_validator
from app.research.credibility import source_credibility_scorer
from app.research.contradictions import contradiction_detector
from app.research.evidence import evidence_extractor
from app.scraping.text_normalizer import text_normalizer
from app.llm.provider import MockLLMProvider
from app.agents.synthesizer import SynthesizerAgent, synthesizer_agent, SynthesisResult


# ---------------------------------------------------------------------------
# Test 1: Source Validation rejects fake TechCrunch placeholder sources
# ---------------------------------------------------------------------------
def test_placeholder_techcrunch_rejected_and_zero_credibility():
    fake_source = Source(
        id="src-fake-1",
        url="https://techcrunch.com/news/current-market-size-and-growth",
        title="Industry Update: Breakthroughs in current market size",
        snippet="Market analysis and commercial roadmap milestones announced for Current market size.",
        source_type=SourceType.NEWS,
    )

    # 1. Source validator detects it as placeholder
    is_ph, reason = source_validator.is_placeholder(fake_source)
    assert is_ph is True

    validation = source_validator.validate(fake_source)
    assert validation.is_valid is False
    assert validation.is_placeholder is True

    # 2. Credibility scorer sets it to 0.0 (never 1.0)
    evaluation = source_credibility_scorer.evaluate_source(fake_source)
    assert evaluation.overall_score == 0.0


# ---------------------------------------------------------------------------
# Test 2: Evidence extraction falls back to clean snippet and rejects corrupted text
# ---------------------------------------------------------------------------
def test_evidence_extraction_snippet_fallback_and_corruption_rejection():
    # Source where web page has corrupted unicode/binary junk, but snippet is clean
    corrupted_source = Source(
        id="src-fe-1",
        url="https://www.financialexpress.com/auto/electric-vehicles-india",
        title="Financial Express - EV Growth",
        snippet="A 4x jump in EV wiring content and 35% ISG penetration across domestic manufacturers.",
        clean_text="\x00\x01\x02\ufffd\ufffd raw corrupted binary stream",
        content="\x00\x01\x02\ufffd\ufffd raw corrupted binary stream",
        credibility_score=0.85,
    )

    evidence_items = evidence_extractor.extract_evidence(corrupted_source)
    assert len(evidence_items) > 0

    for ev in evidence_items:
        # Quote and claim must NOT be corrupted
        assert not text_normalizer.is_corrupted_text(ev.claim)
        assert not text_normalizer.is_corrupted_text(ev.quote)
        assert "\ufffd" not in ev.claim
        assert "\ufffd" not in ev.quote
        # The clean snippet content should be captured
        assert "4x" in ev.claim or "ISG" in ev.claim or "wiring" in ev.claim


def test_binary_symbol_debris_is_rejected_as_corrupted_text():
    assert text_normalizer.is_corrupted_text("$J% &WM*{,h-_ru]\\GC+%4h?C)BW3...") is True


# ---------------------------------------------------------------------------
# Test 3: Contradiction detection avoids cross-region false positives (India vs Canada)
# ---------------------------------------------------------------------------
def test_contradiction_ignores_cross_region_claims():
    india_ev = Evidence(
        source_id="src-india",
        claim="EV sales in India grew by 45% YoY in 2025 across passenger segments.",
        quote="EV sales in India grew by 45% YoY in 2025 across passenger segments.",
    )
    canada_ev = Evidence(
        source_id="src-canada",
        claim="Canada EV commercial grant project funding decreased by 10% in 2024.",
        quote="Canada EV commercial grant project funding decreased by 10% in 2024.",
    )

    # India vs Canada should NOT be flagged as a contradiction
    findings = contradiction_detector.detect(india_ev.claim, [canada_ev])
    assert len(findings) == 0


def test_contradiction_ignores_different_metrics_and_forecasts():
    penetration_forecast = "EV penetration may increase to 10-12% by 2030 in India."
    growth_actual = Evidence(
        source_id="src-growth",
        claim="EV passenger vehicles grew 57% in India during 2025.",
        quote="EV passenger vehicles grew 57% in India during 2025.",
    )

    assert contradiction_detector.detect(penetration_forecast, [growth_actual]) == []


def test_contradiction_detects_genuine_conflict_and_deduplicates():
    claim_a = "EV passenger vehicle registrations in India increased by 45% in 2024."
    claim_b = Evidence(
        source_id="src-oppose",
        claim="EV passenger vehicle registrations in India decreased by 20% in 2024.",
        quote="EV passenger vehicle registrations in India decreased by 20% in 2024.",
    )

    findings = contradiction_detector.detect(claim_a, [claim_b])
    assert len(findings) == 1
    assert "CONTRADICTION:" in findings[0].format()

    # Repeated calls should deduplicate globally
    all_findings = contradiction_detector.detect_all([
        Evidence(source_id="1", claim=claim_a, quote=claim_a),
        claim_b,
        claim_b,  # Duplicate in pool
    ])
    assert len(all_findings) == 1


# ---------------------------------------------------------------------------
# Test 4: Report synthesizer does not emit generic AI templates
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_synthesizer_generates_grounded_report_without_frontier_ai_template():
    provider = MockLLMProvider()
    prompt = """Research Subject: Indian Electric Vehicle Market & Component Localization
Verified Evidence Pool:
[1] Claim: A 4x jump in EV wiring content and 35% ISG penetration in India | Source: Financial Express
[2] Claim: India EV sales grew by 45% YoY in 2025 | Source: PIB
"""

    report_text = await provider.generate_text(prompt)
    assert "Comprehensive empirical research demonstrates exponential progress across frontier AI architectures" not in report_text
    assert "Indian Electric Vehicle" in report_text or "EV" in report_text
    assert "Market analysis and commercial roadmap milestones announced for Current market size" not in report_text

    # Verify structured JSON synthesis as well
    json_str = await provider.generate_structured_json(
        prompt="Synthesize research data for research topic: 'Indian EV Market'",
        system_prompt="You are a Lead Synthesis Agent. Output JSON with key_findings and market_analysis."
    )
    import json
    data = json.loads(json_str)
    assert "key_findings" in data
    assert "market_analysis" in data
    assert len(data["key_findings"]) > 0
    for kf in data["key_findings"]:
        assert "frontier AI architectures" not in kf
        assert "commercial roadmap milestones announced for" not in kf


@pytest.mark.asyncio
async def test_writer_receives_clean_structured_research_data():
    source = Source(
        id="src-writer-1",
        research_id="res-writer-1",
        url="https://pib.gov.in/ev-update",
        title="PIB EV Update",
        credibility_score=0.95,
    )
    evidence = Evidence(
        research_id="res-writer-1",
        source_id="src-writer-1",
        source_title="PIB EV Update",
        source_url=source.url,
        claim="India EV sales grew 45% in 2025.",
        quote="India EV sales grew 45% in 2025.",
        confidence=0.95,
    )
    agent = SynthesizerAgent()
    synthesis_json = '{"key_findings": ["India EV sales grew 45% in 2025."]}'

    with patch.object(
        agent.llm,
        "execute_prompt",
        new=AsyncMock(side_effect=[synthesis_json, "# Evidence-grounded report"]),
    ) as mock_execute:
        await agent.synthesize_report("India EV market", [source], [evidence])

    writer_variables = mock_execute.await_args_list[1].kwargs["variables"]
    structured_data = writer_variables["research_data"]
    assert "verified_evidence" in structured_data
    assert "analysis" in structured_data
    assert "epistemic hallucinations" not in structured_data.lower()
