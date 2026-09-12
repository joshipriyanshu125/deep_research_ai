import pytest

from app.agents.fact_checker import FactCheckerAgent
from app.database.models.evidence import Evidence
from app.database.models.source import Source
from app.research.confidence import assess_confidence
from app.research.contradictions import contradiction_detector


def _evidence(source_id: str, claim: str, confidence: float = 0.8) -> Evidence:
    return Evidence(
        source_id=source_id,
        source_title=source_id,
        claim=claim,
        quote=claim,
        confidence=confidence,
    )


def test_contradiction_reports_conflict_and_likely_cause():
    claim = "EV sales increased by 45% in 2024 according to the registry dataset."
    opposing = _evidence(
        "source-b",
        "EV sales decreased by 12% in 2025 according to the survey dataset.",
    )

    findings = contradiction_detector.detect(claim, [opposing])

    assert len(findings) == 1
    formatted = findings[0].format()
    assert formatted.startswith("CONTRADICTION:")
    assert "different years" in formatted
    assert "different datasets" in formatted
    assert "before choosing an estimate" in formatted


@pytest.mark.asyncio
async def test_fact_check_exposes_contradiction_and_confidence_representation():
    evidence = [
        _evidence("source-a", "EV sales increased by 45% in 2024.", 0.9),
        _evidence("source-b", "EV sales decreased by 12% in 2025.", 0.8),
    ]
    sources = [
        Source(source_id="source-a", url="https://example.org/a", title="A", credibility_score=0.9),
        Source(source_id="source-b", url="https://example.org/b", title="B", credibility_score=0.8),
    ]

    result = await FactCheckerAgent().fact_check_claim(
        evidence[0].claim, evidence, sources=sources
    )

    assert result.contradictions
    assert all(item.startswith("CONTRADICTION:") for item in result.contradictions)
    assert result.supported is False
    assert result.confidence_level in {"HIGH", "MEDIUM", "LOW"}
    assert result.confidence_factors


def test_confidence_uses_evidence_sources_and_uncertainty():
    evidence = [_evidence("source-a", "A measured result", 0.95)]
    sources = [
        Source(
            source_id="source-a",
            url="https://example.org/a",
            title="A",
            credibility_score=0.95,
            published_at="2025-01-01",
        )
    ]

    assessment = assess_confidence(evidence, sources, model_uncertainty=0.2)

    assert 0.0 <= assessment.score <= 1.0
    assert assessment.level in {"HIGH", "MEDIUM", "LOW"}
    assert any("recency" in factor.lower() for factor in assessment.factors)
