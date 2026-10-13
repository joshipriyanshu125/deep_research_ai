from typing import List, Dict, Any
from app.llm.service import get_llm_service
from app.llm.prompts import analyst_prompt
from app.database.models.evidence import Evidence
from app.scraping.text_normalizer import text_normalizer


class AnalystAgent:
    def __init__(self, provider_type: str = None):
        self.llm = get_llm_service(provider_type=provider_type)

    def build_analysis(self, evidence_items: List[Evidence]) -> Dict[str, List[str]]:
        """Group clean, verified claims into the writer's analysis dimensions."""
        analysis = {"market": [], "growth": [], "competition": [], "opportunities": [], "risks": []}
        clean_claims: List[str] = []
        for evidence in evidence_items:
            metadata = getattr(evidence, "metadata", {}) or {}
            if (
                metadata.get("content_provenance") == "metadata-only"
                or metadata.get("evidence_eligible") is False
                or metadata.get("quote_validated") is False
            ):
                continue
            if evidence.verification_status in {"disputed", "refuted"}:
                continue
            claim = text_normalizer.sanitize_for_evidence(evidence.claim or "")
            if text_normalizer.is_corrupted_text(claim):
                continue
            clean_claims.append(claim)
            normalized = claim.lower()
            if any(term in normalized for term in ("market", "sales", "revenue", "demand", "adoption")):
                analysis["market"].append(claim)
            if any(term in normalized for term in ("growth", "grew", "increased", "cagr", "expanded")):
                analysis["growth"].append(claim)
            if any(term in normalized for term in ("compet", "share", "manufacturer", "company", "oem")):
                analysis["competition"].append(claim)
            if any(term in normalized for term in ("opportunity", "investment", "potential", "expand")):
                analysis["opportunities"].append(claim)
            if any(term in normalized for term in ("risk", "challenge", "constraint", "shortage", "volatility")):
                analysis["risks"].append(claim)

        if clean_claims and not analysis["market"]:
            analysis["market"] = clean_claims[:5]
        return {key: list(dict.fromkeys(values))[:5] for key, values in analysis.items()}

    async def analyze_findings(self, evidence_items: List[Evidence]) -> Dict[str, Any]:
        analysis_data = self.build_analysis(evidence_items)
        claims_text = "\n".join(
            f"- {claim}" for claims in analysis_data.values() for claim in claims
        )
        llm_used = False
        llm_error = None
        try:
            narrative = await self.llm.execute_prompt(
                analyst_prompt,
                variables={"claims_text": claims_text or "No clean verified claims were available."},
            )
            # The structured analysis remains the source of truth.  A model
            # narrative is retained only when it discusses supplied claims;
            # otherwise it is more truthful to state the local limitation.
            claim_tokens = {
                token
                for token in " ".join(
                    claim for claims in analysis_data.values() for claim in claims
                ).lower().split()
                if len(token) > 3
            }
            narrative_tokens = {token.strip(".,:;()[]") for token in narrative.lower().split() if len(token) > 3}
            llm_used = bool(claim_tokens.intersection(narrative_tokens)) if claim_tokens else False
            if not llm_used:
                narrative = self._fallback_narrative(analysis_data)
        except Exception as exc:
            llm_error = type(exc).__name__
            narrative = self._fallback_narrative(analysis_data)

        provider = getattr(self.llm, "provider", None)
        return {
            "synthesis": narrative,
            "analysis": analysis_data,
            "key_patterns": list(dict.fromkeys(
                claim for claims in analysis_data.values() for claim in claims
            ))[:5],
            "llm_used": llm_used,
            "llm_provider": str(getattr(provider, "provider_type", "unknown")) if llm_used else "none",
            "llm_model": str(getattr(provider, "model", "") or "") if llm_used else "",
            "llm_error": llm_error,
        }

    @staticmethod
    def _fallback_narrative(analysis_data: Dict[str, List[str]]) -> str:
        claims = [claim for values in analysis_data.values() for claim in values]
        if not claims:
            return "No clean verified claims were available for analysis."
        return "The analysis is limited to the following verified claims: " + " ".join(claims[:5])


analyst_agent = AnalystAgent()
