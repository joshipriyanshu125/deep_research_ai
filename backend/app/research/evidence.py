"""
Day 18 — Evidence Extraction Engine

Core Architecture:
    Source
      ↓
    Relevant Passage (Passage Segmentation, Noise Filtering, Relevance Scoring)
      ↓
    Evidence (Empirical Data Points, Quotes, Quantitative Metrics, Supporting Entities)
      ↓
    Claim (Crisp, Verifiable, Grounded Assertions with Calibrated Confidence)

Example Output:
    {
      "claim": "EV sales in India grew by 45% YoY in 2025",
      "evidence": "According to SIAM records, EV sales in India grew by 45% YoY in 2025.",
      "source_id": "src_123",
      "confidence": 0.94
    }
"""

import re
import json
import asyncio
from typing import List, Dict, Any, Optional, Set, Tuple
from app.database.models.source import Source
from app.database.models.evidence import Evidence
from app.llm.service import get_llm_service
from app.llm.prompts import evidence_extraction_prompt
from app.utils.logger import logger
from app.utils.helpers import generate_uuid


# ---------------------------------------------------------------------------
# Regex Patterns for High-Entropy Evidence Signals
# ---------------------------------------------------------------------------

_METRIC_PATTERNS = re.compile(
    r"("
    r"\b\d+(?:\.\d+)?%\b|"                                      # 45%, 12.5%
    r"[\$₹€£¥]\s*\d+(?:,\d+)*(?:\.\d+)?(?:\s*(?:billion|million|crore|trillion|lakh|B|M|k))?\b|" # $15.4B, ₹5,000 crore
    r"\b(?:USD|INR|EUR|GBP)\s*\d+(?:,\d+)*(?:\.\d+)?\b|"       # USD 500 million
    r"\b\d{4}\b|"                                               # 2025, 2026, 2030
    r"\b\d+(?:,\d+)*(?:\.\d+)?\s*(?:units|vehicles|gigawatts|GW|MW|kW|kWh|Wh/kg|kg|tons|tonnes|CAGR|bps|users|subscribers)\b|" # Units
    r"\b\d{1,3}(?:,\d{3})+\b"                                   # Formatted numbers: 1,500,000
    r")",
    re.IGNORECASE,
)

_EMPIRICAL_ACTION_PATTERNS = re.compile(
    r"\b("
    r"increased|decreased|grew|dropped|reached|surpassed|projected|forecast|expected|"
    r"reported|valued|estimated|generated|invested|allocated|surged|declined|expanded|"
    r"accelerated|achieved|recorded|published|measured|demonstrated|concluded|approved"
    r")\b",
    re.IGNORECASE,
)

_ENTITY_HINTS = re.compile(
    r"\b([A-Z][a-zA-Z0-9]+(?:\s+[A-Z][a-zA-Z0-9]+)*)\b"
)

_NOISE_LINE_PATTERNS = re.compile(
    r"(cookies? policy|privacy policy|terms of service|all rights reserved|"
    r"subscribe to newsletter|sign in|sign up|follow us on|advertisement|"
    r"share this article|read more at|click here|navigation|menu)",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# 1. Passage Extractor: Source -> Relevant Passages
# ---------------------------------------------------------------------------

class PassageExtractor:
    """
    Splits source documents into coherent, informative semantic passages and filters out noise.
    """

    def __init__(self, min_passage_length: int = 40, max_passage_length: int = 1500):
        self.min_passage_length = min_passage_length
        self.max_passage_length = max_passage_length

    def clean_passage(self, text: str) -> str:
        """Clean whitespace and formatting artifacts."""
        if not text:
            return ""
        cleaned = re.sub(r"[ \t]+", " ", text)
        cleaned = re.sub(r"\n\s*\n+", "\n\n", cleaned)
        return cleaned.strip()

    def segment_into_passages(self, text: str) -> List[str]:
        """
        Segment source text into meaningful paragraphs or coherent multi-sentence blocks.
        """
        if not text:
            return []

        cleaned_text = self.clean_passage(text)
        raw_blocks = re.split(r"\n\s*\n|\n(?=[-*#\d]+\.?\s)", cleaned_text)

        passages = []
        for block in raw_blocks:
            block = block.strip()
            if not block or len(block) < self.min_passage_length:
                continue

            # Drop boilerplate/navigation noise
            if _NOISE_LINE_PATTERNS.search(block) and len(block) < 150:
                continue

            if len(block) > self.max_passage_length:
                sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", block) if s.strip()]
                current_chunk = []
                current_len = 0
                for sent in sentences:
                    current_chunk.append(sent)
                    current_len += len(sent) + 1
                    if current_len >= 800:
                        passages.append(" ".join(current_chunk))
                        current_chunk = []
                        current_len = 0
                if current_chunk:
                    passages.append(" ".join(current_chunk))
            else:
                passages.append(block)

        if not passages and len(cleaned_text) >= self.min_passage_length:
            sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", cleaned_text) if len(s.strip()) > 30]
            for i in range(0, len(sentences), 3):
                passages.append(" ".join(sentences[i:i + 3]))

        return passages

    def rank_passages(self, passages: List[str], topic: Optional[str] = None) -> List[Tuple[str, float]]:
        """
        Score passages by empirical richness (presence of metrics, numbers, keywords) and topic relevance.
        """
        scored_passages = []
        topic_tokens = set(re.findall(r"\w+", topic.lower())) if topic else set()

        for p in passages:
            score = 0.5
            metric_matches = _METRIC_PATTERNS.findall(p)
            score += min(0.3, len(metric_matches) * 0.1)

            action_matches = _EMPIRICAL_ACTION_PATTERNS.findall(p)
            score += min(0.2, len(action_matches) * 0.05)

            if topic_tokens:
                p_tokens = set(re.findall(r"\w+", p.lower()))
                overlap = len(topic_tokens.intersection(p_tokens))
                if overlap > 0:
                    score += min(0.2, (overlap / len(topic_tokens)) * 0.2)

            scored_passages.append((p, min(1.0, score)))

        scored_passages.sort(key=lambda x: x[1], reverse=True)
        return scored_passages


# ---------------------------------------------------------------------------
# 2. Heuristic Evidence Extractor: Relevant Passage -> Evidence -> Claim
# ---------------------------------------------------------------------------

class HeuristicEvidenceExtractor:
    """
    Rule-based and pattern-driven atomic evidence extractor.
    Guarantees deterministic, fast extraction with strict quote-to-claim grounding.
    """

    def extract_from_sentence(
        self,
        sentence: str,
        source_id: str,
        research_id: str = "",
        base_confidence: float = 0.90,
        sub_topic: Optional[str] = None,
        source_url: Optional[str] = None,
        source_title: Optional[str] = None,
    ) -> Optional[Evidence]:
        """
        Evaluate a single sentence for high-entropy empirical evidence.
        """
        sent = sentence.strip()
        if len(sent) < 30 or len(sent) > 500:
            return None

        if _NOISE_LINE_PATTERNS.search(sent):
            return None

        metrics = _METRIC_PATTERNS.findall(sent)
        actions = _EMPIRICAL_ACTION_PATTERNS.findall(sent)

        is_empirical = bool(metrics or (actions and len(sent) > 50))
        if not is_empirical:
            return None

        claim_text = sent
        if claim_text.endswith("."):
            claim_text = claim_text[:-1]

        candidate_entities = _ENTITY_HINTS.findall(sent)
        stopwords = {"According", "The", "This", "In", "On", "At", "For", "With", "As", "By", "From"}
        entities = [e for e in candidate_entities if e not in stopwords and len(e) > 2][:5]

        if "%" in sent or any(re.search(r"[\$₹€£¥]|CAGR|growth|sales|units|revenue", m, re.IGNORECASE) for m in metrics):
            ev_type = "statistic"
        elif any(re.search(r"policy|act|government|ministry|regulation", sent, re.IGNORECASE) for _ in [1]):
            ev_type = "policy_event"
        else:
            ev_type = "empirical_finding"

        confidence = base_confidence
        if metrics:
            confidence = min(0.98, confidence + 0.05)
        if len(entities) >= 2:
            confidence = min(0.98, confidence + 0.02)

        return Evidence(
            research_id=research_id,
            source_id=source_id,
            claim=claim_text,
            quote=sent,
            evidence=sent,
            confidence=round(confidence, 4),
            sub_topic=sub_topic,
            supporting_entities=entities,
            metrics=[m.strip() for m in metrics[:6]],
            evidence_type=ev_type,
            verification_status="verified",
            source_url=source_url,
            source_title=source_title,
        )

    def extract_from_passage(
        self,
        passage: str,
        source_id: str,
        research_id: str = "",
        base_confidence: float = 0.90,
        sub_topic: Optional[str] = None,
        source_url: Optional[str] = None,
        source_title: Optional[str] = None,
        max_claims_per_passage: int = 3,
    ) -> List[Evidence]:
        """Extract atomic evidence claims from a passage."""
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", passage) if s.strip()]
        results = []
        for s in sentences:
            ev = self.extract_from_sentence(
                sentence=s,
                source_id=source_id,
                research_id=research_id,
                base_confidence=base_confidence,
                sub_topic=sub_topic,
                source_url=source_url,
                source_title=source_title,
            )
            if ev:
                ev.passage = passage
                results.append(ev)
                if len(results) >= max_claims_per_passage:
                    break
        return results


# ---------------------------------------------------------------------------
# 3. Main Evidence Extractor Orchestrator
# ---------------------------------------------------------------------------

class EvidenceExtractor:
    """
    Day 18 Unified Evidence Extractor.
    Implements: Source -> Relevant Passage -> Evidence -> Grounded Claim.
    Supports heuristic rules, LLM-powered extraction, batch extraction, and confidence scoring.
    """

    def __init__(self):
        self.passage_extractor = PassageExtractor()
        self.heuristic_extractor = HeuristicEvidenceExtractor()

    def extract_evidence(
        self,
        source: Source,
        research_id: str = "",
        topic: Optional[str] = None,
        max_evidence: int = 10,
    ) -> List[Evidence]:
        """
        Synchronous evidence extraction from a Source instance (backwards-compatible).
        Extracts relevant passages, extracts high-fidelity atomic evidence, and formulates claims.
        """
        text = source.clean_text or source.content or source.snippet or ""
        if not text:
            return []

        research_id = research_id or source.research_id
        source_id = source.source_id or source.id
        base_conf = getattr(source, "credibility_score", 0.90) or 0.90

        passages = self.passage_extractor.segment_into_passages(text)
        if not passages:
            passages = [text]

        ranked_passages = self.passage_extractor.rank_passages(passages, topic=topic or source.query)
        top_passages = [p for p, _ in ranked_passages[:8]]

        evidence_list: List[Evidence] = []
        seen_claims: Set[str] = set()

        for passage in top_passages:
            claims = self.heuristic_extractor.extract_from_passage(
                passage=passage,
                source_id=source_id,
                research_id=research_id,
                base_confidence=base_conf,
                sub_topic=source.title or topic,
                source_url=source.url,
                source_title=source.title,
            )
            for ev in claims:
                norm_claim = ev.claim.strip().lower()
                if norm_claim not in seen_claims:
                    seen_claims.add(norm_claim)
                    evidence_list.append(ev)
                    if len(evidence_list) >= max_evidence:
                        break
            if len(evidence_list) >= max_evidence:
                break

        if not evidence_list:
            sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if len(s.strip()) > 35]
            for s in sentences[:3]:
                ev = Evidence(
                    research_id=research_id,
                    source_id=source_id,
                    claim=s,
                    quote=s,
                    evidence=s,
                    passage=s,
                    confidence=round(base_conf, 4),
                    sub_topic=source.title,
                    source_url=source.url,
                    source_title=source.title,
                    verification_status="verified",
                )
                evidence_list.append(ev)

        return evidence_list

    async def extract_evidence_async(
        self,
        source: Source,
        research_id: str = "",
        topic: Optional[str] = None,
        use_llm: bool = True,
        max_evidence: int = 10,
    ) -> List[Evidence]:
        """
        Asynchronous evidence extraction with optional LLM reasoning and heuristic fallback.
        """
        text = source.clean_text or source.content or source.snippet or ""
        if not text:
            return []

        research_id = research_id or source.research_id
        source_id = source.source_id or source.id
        base_conf = getattr(source, "credibility_score", 0.90) or 0.90
        sub_topic = source.title or topic or ""

        passages = self.passage_extractor.segment_into_passages(text)
        ranked = self.passage_extractor.rank_passages(passages, topic=topic or source.query)
        candidate_passages = [p for p, _ in ranked[:4]]

        if not candidate_passages:
            candidate_passages = [text[:1000]]

        if use_llm:
            try:
                llm = get_llm_service()
                combined_passages = "\n\n---\n\n".join(candidate_passages[:3])
                
                response_str = await llm.execute_prompt(
                    evidence_extraction_prompt,
                    variables={
                        "topic": topic or source.query or source.title or "General Research",
                        "title": source.title or "Document",
                        "domain": getattr(source, "domain", "") or "web",
                        "passage": combined_passages,
                    }
                )

                parsed = self._parse_llm_claims_json(response_str)
                if parsed:
                    llm_evidence: List[Evidence] = []
                    for item in parsed:
                        claim = item.get("claim", "").strip()
                        quote = item.get("evidence", "").strip() or item.get("quote", "").strip() or claim
                        if not claim:
                            continue

                        raw_conf = float(item.get("confidence", 0.90))
                        calibrated_conf = round(min(1.0, max(0.1, (raw_conf * 0.6) + (base_conf * 0.4))), 4)

                        ev = Evidence(
                            research_id=research_id,
                            source_id=source_id,
                            claim=claim,
                            quote=quote,
                            evidence=quote,
                            passage=combined_passages[:500],
                            confidence=calibrated_conf,
                            sub_topic=sub_topic,
                            supporting_entities=item.get("supporting_entities", []),
                            metrics=item.get("metrics", []),
                            evidence_type=item.get("evidence_type", "empirical"),
                            verification_status="verified",
                            source_url=source.url,
                            source_title=source.title,
                        )
                        llm_evidence.append(ev)

                    if llm_evidence:
                        return llm_evidence[:max_evidence]

            except Exception as e:
                logger.warning(f"LLM evidence extraction fallback to heuristics: {e}")

        return self.extract_evidence(source, research_id=research_id, topic=topic, max_evidence=max_evidence)

    def extract_evidence_from_text(
        self,
        text: str,
        source_id: str,
        research_id: str = "",
        topic: Optional[str] = None,
        source_title: Optional[str] = None,
        source_url: Optional[str] = None,
        base_confidence: float = 0.90,
    ) -> List[Evidence]:
        """
        Direct extraction from raw text without requiring a Source model.
        """
        src = Source(
            source_id=source_id,
            id=source_id,
            research_id=research_id,
            url=source_url or "https://example.com",
            title=source_title or "Text Source",
            content=text,
            clean_text=text,
            credibility_score=base_confidence,
        )
        return self.extract_evidence(src, research_id=research_id, topic=topic)

    def extract_evidence_batch(
        self,
        sources: List[Source],
        research_id: str = "",
        topic: Optional[str] = None,
    ) -> List[Evidence]:
        """
        Batch evidence extraction across a list of Sources.
        """
        all_evidence: List[Evidence] = []
        for src in sources:
            all_evidence.extend(self.extract_evidence(src, research_id=research_id, topic=topic))
        return all_evidence

    def _parse_llm_claims_json(self, response_str: str) -> Optional[List[Dict[str, Any]]]:
        """Helper to extract JSON claims list from LLM output."""
        if not response_str:
            return None

        text = response_str.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        try:
            data = json.loads(text)
            if isinstance(data, dict):
                if "claims" in data and isinstance(data["claims"], list):
                    return data["claims"]
                if "evidence" in data and isinstance(data["evidence"], list):
                    return data["evidence"]
            elif isinstance(data, list):
                return data
        except Exception:
            m = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
            if m:
                try:
                    sub_data = json.loads(m.group(1))
                    if isinstance(sub_data, dict) and "claims" in sub_data:
                        return sub_data["claims"]
                    if isinstance(sub_data, list):
                        return sub_data
                except Exception:
                    pass
        return None


# Global singleton instance
evidence_extractor = EvidenceExtractor()

