import json
import re
from typing import List, Dict, Any, Optional, Union
from app.llm.service import LLMService, get_llm_service
from app.llm.prompts import fact_check_prompt, FACT_CHECKER_SYSTEM_PROMPT
from app.database.models.evidence import Evidence
from app.database.models.source import Source
from app.database.models.report import FactCheckResult
from app.utils.logger import logger
from app.research.contradictions import contradiction_detector
from app.research.confidence import assess_confidence


class FactCheckerAgent:
    """
    Day 28 — Fact-checking Agent
    High-value verification pipeline for empirical research claims:
      Claim
        ↓
      Find supporting evidence
        ↓
      Compare sources
        ↓
      Check contradiction
        ↓
      Confidence
    """

    def __init__(self, provider_type: Optional[str] = None):
        self.llm = get_llm_service()

    def find_supporting_evidence(
        self,
        claim: str,
        evidence_pool: List[Evidence],
    ) -> List[Evidence]:
        """
        Step 1: Find supporting evidence from the pool for a given claim.
        Matches based on semantic relevance, token overlap, and key entity mentions.
        """
        if not evidence_pool:
            return []

        # Tokenize claim for keyword / entity overlap
        clean_claim = re.sub(r"[^\w\s]", " ", claim.lower())
        claim_tokens = set([w for w in clean_claim.split() if len(w) > 2])

        scored_evidences = []
        for ev in evidence_pool:
            # Direct match if evidence is for this exact claim
            if ev.claim.strip().lower() == claim.strip().lower():
                scored_evidences.append((ev, 1.0))
                continue

            # Compare against evidence text, quote, and passage
            ev_text = f"{ev.claim} {ev.quote} {ev.evidence} {ev.passage or ''}".lower()
            ev_tokens = set([w for w in re.sub(r"[^\w\s]", " ", ev_text).split() if len(w) > 2])

            overlap = claim_tokens.intersection(ev_tokens)
            score = len(overlap) / max(len(claim_tokens), 1)

            # Check matching supporting entities or metrics
            for ent in ev.supporting_entities:
                if ent.lower() in clean_claim:
                    score += 0.15
            for metric in ev.metrics:
                if metric.lower() in clean_claim:
                    score += 0.20

            if score >= 0.25:
                scored_evidences.append((ev, score))

        # Sort descending by match score
        scored_evidences.sort(key=lambda x: x[1], reverse=True)
        return [ev for ev, _ in scored_evidences]

    def compare_sources(
        self,
        supporting_evidences: List[Evidence],
        sources: Optional[List[Source]] = None,
    ) -> Dict[str, Any]:
        """
        Step 2: Compare sources contributing evidence for the claim.
        Collects unique source identifiers, domains, URLs, and evaluates source diversity.
        """
        source_map: Dict[str, Source] = {}
        if sources:
            for s in sources:
                source_map[s.id] = s

        unique_sources: List[str] = []
        unique_urls: List[str] = []
        source_credibility_scores: List[float] = []

        for ev in supporting_evidences:
            src = source_map.get(ev.source_id)
            url = ev.source_url or (src.url if src else None)
            title = ev.source_title or (src.title if src else None)
            identifier = url or title or ev.source_id

            if identifier and identifier not in unique_sources:
                unique_sources.append(identifier)
            if url and url not in unique_urls:
                unique_urls.append(url)

            if src and hasattr(src, "credibility_score") and src.credibility_score is not None:
                source_credibility_scores.append(src.credibility_score)

        avg_credibility = (
            sum(source_credibility_scores) / len(source_credibility_scores)
            if source_credibility_scores
            else 0.85
        )

        return {
            "unique_sources": unique_sources,
            "unique_urls": unique_urls,
            "distinct_source_count": len(unique_sources),
            "avg_credibility": avg_credibility,
        }

    def check_contradictions(
        self,
        claim: str,
        supporting_evidences: List[Evidence],
        evidence_pool: Optional[List[Evidence]] = None,
    ) -> List[str]:
        """
        Step 3: Check for contradictions or conflicting assertions.
        Detects opposing numerical trends, negation discrepancies, or explicitly disputed evidence.
        """
        contradictions: List[str] = []
        search_pool = evidence_pool or supporting_evidences

        # Check for explicitly disputed status in evidence
        for ev in supporting_evidences:
            if ev.verification_status in ("disputed", "refuted"):
                contradictions.append(
                    f"Evidence from source '{ev.source_title or ev.source_id}' is flagged as {ev.verification_status}."
                )

        contradictions.extend(
            finding.format()
            for finding in contradiction_detector.detect(claim, search_pool)
        )

        return list(dict.fromkeys(contradictions))  # Deduplicate

    def calculate_confidence(
        self,
        supporting_evidences: List[Evidence],
        distinct_source_count: int,
        contradictions: List[str],
        avg_source_credibility: float = 0.85,
    ) -> float:
        """
        Step 4: Compute calibrated confidence score (0.0 to 1.0).
        Boosts confidence with multi-source corroboration and penalizes contradictions.
        """
        if not supporting_evidences:
            return 0.30

        # Base confidence from top supporting evidence items
        ev_confidences = [ev.confidence for ev in supporting_evidences if ev.confidence is not None]
        base_confidence = max(ev_confidences) if ev_confidences else 0.85

        # Factor in source credibility
        calibrated = (base_confidence * 0.7) + (avg_source_credibility * 0.3)

        # Multi-source corroboration bonus (+0.05 for 2 sources, +0.10 for 3+ sources)
        if distinct_source_count >= 3:
            calibrated += 0.08
        elif distinct_source_count >= 2:
            calibrated += 0.04

        # Contradiction penalty
        if contradictions:
            penalty = 0.25 * len(contradictions)
            calibrated -= min(0.50, penalty)

        return round(max(0.0, min(1.0, calibrated)), 2)

    async def fact_check_claim(
        self,
        claim: str,
        evidence_pool: List[Evidence],
        sources: Optional[List[Source]] = None,
        use_llm: bool = False,
    ) -> FactCheckResult:
        """
        Full 5-step fact check verification pipeline for a single claim.
        Returns FactCheckResult matching:
        {
          "claim": "...",
          "supported": true,
          "confidence": 0.91,
          "sources": ["..."]
        }
        """
        # Step 1: Find supporting evidence
        supporting = self.find_supporting_evidence(claim, evidence_pool)

        # Step 2: Compare sources
        source_comp = self.compare_sources(supporting, sources)
        unique_sources = source_comp["unique_sources"]

        # Step 3: Check contradictions
        contradictions = self.check_contradictions(claim, supporting, evidence_pool)

        # Step 4: Calculate confidence
        confidence = self.calculate_confidence(
            supporting_evidences=supporting,
            distinct_source_count=source_comp["distinct_source_count"],
            contradictions=contradictions,
            avg_source_credibility=source_comp["avg_credibility"],
        )
        assessment = assess_confidence(
            evidence=supporting,
            sources=sources or [],
            contradictions=contradictions,
        )
        confidence = min(confidence, assessment.score) if contradictions else max(confidence, assessment.score)

        # Step 5: Formulate verdict
        is_supported = len(supporting) > 0 and confidence >= 0.60 and len(contradictions) == 0

        supporting_quotes = [
            (ev.evidence or ev.quote or ev.claim)
            for ev in supporting[:3]
            if (ev.evidence or ev.quote or ev.claim)
        ]

        reasoning = (
            f"Verified against {len(supporting)} evidence passage(s) across "
            f"{source_comp['distinct_source_count']} source(s)."
        )
        if contradictions:
            reasoning += f" Contradictions identified: {len(contradictions)}."

        status = "verified" if is_supported else ("disputed" if contradictions else "unverified")

        # Optional LLM-assisted verification refinement
        if use_llm:
            try:
                evidence_text = "\n".join([f"- {ev.claim} (Quote: {ev.quote})" for ev in supporting[:5]])
                sources_text = "\n".join([s for s in unique_sources[:5]])
                llm_response = await self.llm.execute_prompt(
                    fact_check_prompt,
                    variables={
                        "claim": claim,
                        "evidence_context": evidence_text or "No direct evidence provided.",
                        "sources_context": sources_text or "No direct sources provided.",
                    },
                )
                parsed = self._parse_llm_fact_check(llm_response)
                if parsed:
                    if "supported" in parsed:
                        is_supported = bool(parsed["supported"])
                    if "confidence" in parsed and isinstance(parsed["confidence"], (int, float)):
                        confidence = round(max(0.0, min(1.0, float(parsed["confidence"]))), 2)
                    if "reasoning" in parsed and parsed["reasoning"]:
                        reasoning = parsed["reasoning"]
                    if "contradictions" in parsed and isinstance(parsed["contradictions"], list):
                        contradictions.extend(parsed["contradictions"])
                        contradictions = list(dict.fromkeys(contradictions))
            except Exception as e:
                logger.warning(f"LLM fact checking exception: {e}")

        return FactCheckResult(
            claim=claim,
            supported=is_supported,
            confidence=confidence,
            sources=unique_sources,
            contradictions=contradictions,
            supporting_evidence=supporting_quotes,
            reasoning=reasoning,
            verification_status=status,
            confidence_level=assessment.level,
            confidence_factors=assessment.factors,
        )

    async def fact_check_batch(
        self,
        claims: Union[List[str], List[Evidence]],
        evidence_pool: List[Evidence],
        sources: Optional[List[Source]] = None,
        use_llm: bool = False,
    ) -> List[FactCheckResult]:
        """Fact checks a batch of claims or evidence items."""
        results: List[FactCheckResult] = []
        for item in claims:
            claim_text = item.claim if isinstance(item, Evidence) else str(item)
            res = await self.fact_check_claim(
                claim=claim_text,
                evidence_pool=evidence_pool,
                sources=sources,
                use_llm=use_llm,
            )
            results.append(res)
        return results

    async def verify_evidence(
        self,
        evidence_list: List[Evidence],
        sources: Optional[List[Source]] = None,
    ) -> List[Evidence]:
        """
        Audits evidence list and enriches each Evidence instance with verified status and confidence.
        Maintains backward compatibility with Day 1-26 workflows.
        """
        verified: List[Evidence] = []
        for ev in evidence_list:
            fc = await self.fact_check_claim(
                claim=ev.claim,
                evidence_pool=evidence_list,
                sources=sources,
                use_llm=False,
            )
            ev.verification_status = fc.verification_status
            ev.confidence = fc.confidence
            ev.metadata["fact_check"] = fc.to_dict()
            verified.append(ev)
        return verified

    def _parse_llm_fact_check(self, text: str) -> Optional[Dict[str, Any]]:
        """Safely parses structured JSON response from LLM."""
        try:
            # Look for JSON markdown fence or raw object
            match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
            json_str = match.group(1) if match else text.strip()
            # If not in fences, find outer braces
            if not match:
                start = json_str.find("{")
                end = json_str.rfind("}")
                if start != -1 and end != -1:
                    json_str = json_str[start : end + 1]
            return json.loads(json_str)
        except Exception:
            return None


fact_checker_agent = FactCheckerAgent()
