"""Day 30 confidence representation for research conclusions."""

import re
from datetime import datetime
from typing import List, Optional, Sequence

from pydantic import BaseModel, Field

from app.database.models.evidence import Evidence
from app.database.models.source import Source


class ConfidenceAssessment(BaseModel):
    """Numeric confidence plus an explainable ordinal representation."""

    score: float = Field(ge=0.0, le=1.0)
    level: str
    factors: List[str] = Field(default_factory=list)

    def to_dict(self) -> dict:
        return {"score": round(self.score, 4), "level": self.level, "factors": self.factors}


def assess_confidence(
    evidence: Sequence[Evidence],
    sources: Sequence[Source],
    contradictions: Optional[Sequence[str]] = None,
    model_uncertainty: float = 0.0,
) -> ConfidenceAssessment:
    """Combine source quality, corroboration, evidence strength and uncertainty."""
    contradictions = contradictions or []
    if not evidence:
        return ConfidenceAssessment(score=0.3, level="LOW", factors=["No direct evidence"])

    source_by_id = {source.source_id: source for source in sources}
    scores = [float(ev.confidence) for ev in evidence]
    source_quality = [
        float(source_by_id[ev.source_id].credibility_score)
        for ev in evidence
        if ev.source_id in source_by_id
    ]
    source_count = len({ev.source_id for ev in evidence})
    evidence_strength = sum(scores) / len(scores)
    quality = sum(source_quality) / len(source_quality) if source_quality else evidence_strength
    current_year = datetime.now().year
    recency_scores = []
    for source in sources:
        match = re.search(r"\b(20\d{2})\b", str(source.published_at or source.publication_date or ""))
        if match:
            recency_scores.append(max(0.4, min(1.0, 1.0 - (current_year - int(match.group(1))) * 0.1)))
    recency = sum(recency_scores) / len(recency_scores) if recency_scores else 0.6
    corroboration = min(1.0, 0.55 + (0.15 * min(source_count, 3)))
    score = (
        (evidence_strength * 0.35)
        + (quality * 0.25)
        + (recency * 0.10)
        + (corroboration * 0.20)
        + (0.10 * (1.0 - model_uncertainty))
    )
    if contradictions:
        score -= min(0.45, 0.15 * len(contradictions))

    score = round(max(0.0, min(1.0, score)), 4)
    level = "HIGH" if score >= 0.78 else "MEDIUM" if score >= 0.55 else "LOW"
    factors = [
        f"Evidence strength: {evidence_strength:.2f}",
        f"Source quality: {quality:.2f}",
        f"Evidence recency: {recency:.2f}",
        f"Independent source count: {source_count}",
        f"Source agreement: {'reduced by contradictions' if contradictions else 'corroborated'}",
    ]
    if model_uncertainty:
        factors.append(f"Model uncertainty penalty: {model_uncertainty:.2f}")
    return ConfidenceAssessment(score=score, level=level, factors=factors)
