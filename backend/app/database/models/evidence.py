from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, model_validator, field_serializer
from app.utils.helpers import generate_uuid, get_utc_now


class Evidence(BaseModel):
    """
    Day 18 — Atomic Evidence Model
    Captures verifiable claims, supporting source quotes, confidence ratings, and extraction metadata.
    Enforces the grounding hierarchy: Source -> Relevant Passage -> Evidence -> Claim.
    """
    id: str = Field(default_factory=generate_uuid)
    research_id: str = ""
    source_id: str
    claim: str
    quote: str = ""
    evidence: str = ""  # Explicit alias for quote to match {"claim": ..., "evidence": ..., "source_id": ..., "confidence": ...}
    passage: Optional[str] = None
    confidence: float = 0.90
    sub_topic: Optional[str] = None
    supporting_entities: List[str] = Field(default_factory=list)
    metrics: List[str] = Field(default_factory=list)
    evidence_type: str = "empirical"  # empirical, statistic, quote, policy_event, comparative
    verification_status: str = "verified"  # verified, disputed, unverified
    relevance_score: float = 1.0
    source_url: Optional[str] = None
    source_title: Optional[str] = None
    context: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=get_utc_now)

    model_config = {
        "populate_by_name": True,
    }

    @model_validator(mode="before")
    @classmethod
    def sync_quote_and_evidence(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Synchronize quote and evidence fields
            quote_val = data.get("quote") or data.get("evidence") or ""
            data["quote"] = quote_val
            data["evidence"] = quote_val

            # Ensure id exists
            if not data.get("id"):
                data["id"] = generate_uuid()

            # Ensure confidence is clamped 0.0 to 1.0
            if "confidence" in data and data["confidence"] is not None:
                try:
                    data["confidence"] = max(0.0, min(1.0, float(data["confidence"])))
                except (ValueError, TypeError):
                    data["confidence"] = 0.90
        return data

    @field_serializer("created_at")
    def _serialize_dt(self, dt: datetime) -> str:
        return dt.isoformat()

    def to_claim_dict(self) -> Dict[str, Any]:
        """Returns standard Day 18 atomic claim dictionary representation."""
        return {
            "claim": self.claim,
            "evidence": self.evidence or self.quote,
            "source_id": self.source_id,
            "confidence": round(self.confidence, 4),
        }

