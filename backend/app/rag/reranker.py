"""
Day 25 — Hybrid RAG Scoring and Reranker

Combines 5 complementary ranking signals:
  1. Semantic Similarity:  Dense vector cosine score from VectorStore
  2. Keyword / Lexical:    BM25 / TF-IDF style term-overlap with stopword removal
  3. Source Quality:       Domain authority, academic/peer-review flag, reliability score
  4. Recency:              Time-decay based on publication date / year
  5. Research Context:     Alignment with overarching research goal / subtopic

Formula:
  Score = w_sem * S_sem + w_lex * S_lex + w_qual * S_qual + w_rec * S_rec + w_ctx * S_ctx
"""

import math
import re
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from app.utils.logger import logger


# ---------------------------------------------------------------------------
# Stopwords and Tokenizer
# ---------------------------------------------------------------------------

_STOP_WORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "need", "of", "in", "on",
    "at", "by", "for", "with", "to", "from", "as", "and", "or", "but",
    "not", "no", "nor", "so", "yet", "both", "either", "neither", "than",
    "that", "this", "these", "those", "what", "which", "who", "when",
    "where", "why", "how", "all", "any", "some", "such", "each", "other",
    "into", "through", "during", "before", "after", "above", "below",
}


def _stem(word: str) -> str:
    """Lightweight English suffix normalizer for plural and tense inflections."""
    if word.endswith("ies") and len(word) > 4:
        return word[:-3] + "y"
    if word.endswith("es") and len(word) > 3:
        return word[:-2]
    if word.endswith("s") and not word.endswith("ss") and len(word) > 3:
        return word[:-1]
    if word.endswith("ing") and len(word) > 4:
        return word[:-3]
    return word


def tokenize(text: str) -> List[str]:
    """Extract lowercased alphanumeric word tokens, filtering short & stop words."""
    if not text:
        return []
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    return [_stem(t) for t in tokens if t not in _STOP_WORDS and len(t) > 1]


# ---------------------------------------------------------------------------
# 1. Lexical Scorer (BM25-style term frequency matching)
# ---------------------------------------------------------------------------

class LexicalScorer:
    """Computes BM25-style lexical relevance between query and chunk text."""

    def __init__(self, k1: float = 1.5, b: float = 0.75, avg_doc_len: float = 150.0):
        self.k1 = k1
        self.b = b
        self.avg_doc_len = avg_doc_len

    def score(self, query: str, document_text: str) -> float:
        """
        Calculates lexical relevance score normalized to [0.0, 1.0].
        """
        q_tokens = tokenize(query)
        if not q_tokens or not document_text:
            return 0.0

        doc_tokens = tokenize(document_text)
        if not doc_tokens:
            return 0.0

        doc_len = len(doc_tokens)
        doc_counts: Dict[str, int] = {}
        for token in doc_tokens:
            doc_counts[token] = doc_counts.get(token, 0) + 1

        score = 0.0
        for token in q_tokens:
            tf = doc_counts.get(token, 0)
            if tf > 0:
                # BM25 term frequency saturation component
                numerator = tf * (self.k1 + 1)
                denominator = tf + self.k1 * (1 - self.b + self.b * (doc_len / self.avg_doc_len))
                score += numerator / denominator

        # Normalize score against max theoretical score for this query
        max_possible = len(q_tokens) * (self.k1 + 1)
        normalized = score / (max_possible + 1e-9)
        return min(max(normalized, 0.0), 1.0)


# ---------------------------------------------------------------------------
# 2. Source Quality Scorer
# ---------------------------------------------------------------------------

_HIGH_AUTHORITY_DOMAINS = {
    ".gov", ".gov.in", ".nic.in", ".edu", ".ac.uk",
    "arxiv.org", "biorxiv.org", "medrxiv.org", "nature.com",
    "sciencedirect.com", "springer.com", "ieee.org", "acm.org",
    "ncbi.nlm.nih.gov", "pubmed.ncbi.nlm.nih.gov", "cell.com",
    "thelancet.com", "reuters.com", "bloomberg.com", "ft.com",
    "statista.com", "iea.org", "worldbank.org", "imf.org",
}

_LOW_QUALITY_PATTERNS = {
    "pinterest.com", "quora.com", "reddit.com/r/", "yahoo.com/answers",
    "ehow.com", "answers.com", "wikihow.com",
}


class SourceQualityScorer:
    """Scores reliability, authority, and peer-review quality of a source."""

    def score(self, chunk: Dict[str, Any]) -> float:
        metadata = chunk.get("metadata") or {}
        source_type = (
            chunk.get("source_type")
            or metadata.get("source_type")
            or ""
        ).lower()
        url = (chunk.get("url") or metadata.get("url") or "").lower()
        domain = (chunk.get("domain") or metadata.get("domain") or "").lower()

        # Explicit credibility score in metadata
        if "credibility_score" in metadata:
            try:
                return float(metadata["credibility_score"])
            except (ValueError, TypeError):
                pass

        # Academic / Peer-reviewed sources get top authority
        if source_type in ("academic", "paper", "journal"):
            return 1.0

        # Check domain blacklist
        for bad in _LOW_QUALITY_PATTERNS:
            if bad in url or bad in domain:
                return 0.1

        # Check high authority domains
        for high in _HIGH_AUTHORITY_DOMAINS:
            if high in url or high in domain:
                return 0.95

        # News / Company sources
        if source_type == "news":
            return 0.75
        if source_type == "company":
            return 0.70

        # HTTPS bonus
        if url.startswith("https://"):
            return 0.60

        return 0.50


# ---------------------------------------------------------------------------
# 3. Recency Scorer (Time-decay model)
# ---------------------------------------------------------------------------

class RecencyScorer:
    """
    Computes time-decay score based on publication date.
    Uses exponential decay with half-life (default 2 years / 730 days).
    """

    def __init__(self, half_life_days: float = 730.0, default_score: float = 0.5):
        self.half_life_days = half_life_days
        self.default_score = default_score
        self.lambda_decay = math.log(2) / self.half_life_days

    def score(self, chunk: Dict[str, Any], current_date: Optional[datetime] = None) -> float:
        now = current_date or datetime.now()
        metadata = chunk.get("metadata") or {}

        # Look for date fields
        raw_date = (
            chunk.get("published_at")
            or metadata.get("published_at")
            or metadata.get("publication_date")
            or metadata.get("date")
            or metadata.get("year")
        )

        if not raw_date:
            return self.default_score

        pub_dt = self._parse_date(raw_date)
        if not pub_dt:
            return self.default_score

        days_ago = max((now - pub_dt).total_seconds() / 86400.0, 0.0)
        # Exponential decay: e^(-lambda * days)
        decay = math.exp(-self.lambda_decay * days_ago)
        return min(max(decay, 0.05), 1.0)

    @staticmethod
    def _parse_date(val: Any) -> Optional[datetime]:
        if isinstance(val, datetime):
            return val
        if isinstance(val, int) and 1900 <= val <= 2100:
            return datetime(val, 1, 1)

        val_str = str(val).strip()
        # Check year only (e.g. "2024")
        if re.match(r"^\d{4}$", val_str):
            try:
                return datetime(int(val_str), 1, 1)
            except ValueError:
                pass

        # Try ISO / common formats
        date_formats = [
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d",
            "%Y/%m/%d",
            "%d-%m-%Y",
            "%d/%m/%Y",
            "%B %d, %Y",
            "%b %d, %Y",
            "%Y",
        ]
        for fmt in date_formats:
            try:
                return datetime.strptime(val_str, fmt)
            except ValueError:
                continue

        # Regex fallback for year
        year_match = re.search(r"\b(19\d\d|20\d\d)\b", val_str)
        if year_match:
            try:
                return datetime(int(year_match.group(1)), 1, 1)
            except ValueError:
                pass

        return None


# ---------------------------------------------------------------------------
# 4. Context Alignment Scorer
# ---------------------------------------------------------------------------

class ContextAlignmentScorer:
    """Measures relevance of chunk to an overarching research context / topic."""

    def __init__(self):
        self._lexical = LexicalScorer()

    def score(self, context: Optional[str], chunk_text: str) -> float:
        if not context or not context.strip():
            return 0.5  # Neutral when no research context is provided

        return self._lexical.score(context, chunk_text)


# ---------------------------------------------------------------------------
# 5. Hybrid Reranker Engine
# ---------------------------------------------------------------------------

class HybridReranker:
    """
    Day 25 — Production Hybrid Reranker.
    Blends:
      - Semantic similarity (0.40)
      - Keyword / Lexical match (0.25)
      - Source Quality (0.15)
      - Recency decay (0.10)
      - Research Context alignment (0.10)
    """

    def __init__(
        self,
        weight_semantic: float = 0.40,
        weight_lexical: float = 0.25,
        weight_quality: float = 0.15,
        weight_recency: float = 0.10,
        weight_context: float = 0.10,
    ):
        total = (
            weight_semantic
            + weight_lexical
            + weight_quality
            + weight_recency
            + weight_context
        )
        self.w_sem = weight_semantic / total
        self.w_lex = weight_lexical / total
        self.w_qual = weight_quality / total
        self.w_rec = weight_recency / total
        self.w_ctx = weight_context / total

        self.lexical_scorer = LexicalScorer()
        self.quality_scorer = SourceQualityScorer()
        self.recency_scorer = RecencyScorer()
        self.context_scorer = ContextAlignmentScorer()

    def rerank(
        self,
        query: str,
        candidates: List[Tuple[Dict[str, Any], float]],
        research_context: Optional[str] = None,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Reranks a list of (candidate_doc, semantic_score) tuples.

        Returns list of ranked document dicts enriched with:
          - hybrid_score
          - score_breakdown: {semantic, lexical, quality, recency, context}
        """
        if not candidates:
            return []

        scored_results: List[Dict[str, Any]] = []

        for doc, sem_score in candidates:
            content = doc.get("content") or doc.get("text") or ""

            # 1. Semantic score (clamp to [0, 1])
            s_sem = max(min(float(sem_score), 1.0), 0.0)

            # 2. Lexical score
            s_lex = self.lexical_scorer.score(query, content)

            # 3. Source Quality score
            s_qual = self.quality_scorer.score(doc)

            # 4. Recency score
            s_rec = self.recency_scorer.score(doc)

            # 5. Research Context alignment
            s_ctx = self.context_scorer.score(research_context, content)

            # Composite hybrid score
            hybrid_score = (
                self.w_sem * s_sem
                + self.w_lex * s_lex
                + self.w_qual * s_qual
                + self.w_rec * s_rec
                + self.w_ctx * s_ctx
            )

            scored_item = {
                **doc,
                "content": content,
                "hybrid_score": round(hybrid_score, 4),
                "score_breakdown": {
                    "semantic": round(s_sem, 4),
                    "lexical": round(s_lex, 4),
                    "quality": round(s_qual, 4),
                    "recency": round(s_rec, 4),
                    "context": round(s_ctx, 4),
                },
                "score": round(hybrid_score, 4),  # backward-compat alias
            }
            scored_results.append(scored_item)

        # Sort descending by composite hybrid score
        scored_results.sort(key=lambda x: x["hybrid_score"], reverse=True)
        return scored_results[:top_k]


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

hybrid_reranker = HybridReranker()
