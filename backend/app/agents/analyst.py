from typing import List, Dict, Any
from app.llm.service import get_llm_service
from app.llm.prompts import analyst_prompt
from app.database.models.evidence import Evidence
from app.scraping.text_normalizer import text_normalizer


class AnalystAgent:
    def __init__(self, provider_type: str = None):
        self.llm = get_llm_service()

    def build_analysis(self, evidence_items: List[Evidence]) -> Dict[str, List[str]]:
        """Group clean, verified claims into the writer's analysis dimensions."""
        analysis = {"market": [], "growth": [], "competition": [], "opportunities": [], "risks": []}
        clean_claims: List[str] = []
        for evidence in evidence_items:
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
        narrative = await self.llm.execute_prompt(
            analyst_prompt,
            variables={"claims_text": claims_text or "No clean verified claims were available."},
        )
        return {
            "synthesis": narrative,
            "analysis": analysis_data,
            "key_patterns": list(dict.fromkeys(
                claim for claims in analysis_data.values() for claim in claims
            ))[:5],
        }


analyst_agent = AnalystAgent()
