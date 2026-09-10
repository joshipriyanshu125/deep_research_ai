"""
Day 17 — Source Credibility System
Multi-dimensional credibility scoring across six core pillars:
  1. Authority (Domain & Publisher Category: Government/Academic > Company/News > Blog > Forum/Social)
  2. Recency (Publication date decay)
  3. Relevance (Query/topic token alignment with title, snippet, and content)
  4. Primary vs Secondary (Empirical datasets, official filings vs aggregators/commentary)
  5. Specificity (Density of quantitative metrics, percentages, currencies, dates)
  6. Cross-Source Agreement (Corroboration across gathered source batch)
"""
import re
from datetime import datetime
from typing import List, Dict, Any, Optional, Set
from pydantic import BaseModel, Field

from app.database.models.source import Source, SourceType


# ---------------------------------------------------------------------------
# Domain Authority Tables
# ---------------------------------------------------------------------------

_GOVERNMENT_DOMAINS = {
    ".gov", ".gov.in", ".nic.in", ".gov.uk", ".gov.au",
    "pib.gov.in", "niti.gov.in", "whitehouse.gov", "sec.gov",
    "rbi.org.in", "sebi.gov.in", "isro.gov.in", "europa.eu",
    "who.int", "worldbank.org", "imf.org", "un.org", "iea.org",
}

_ACADEMIC_DOMAINS = {
    ".edu", ".ac.in", ".ac.uk", "arxiv.org", "nature.com",
    "science.org", "sciencedirect.com", "ieee.org", "springer.com",
    "ncbi.nlm.nih.gov", "jstor.org", "cell.com", "pnas.org",
    "researchgate.net", "scholar.google.com",
}

_TIER1_NEWS_DOMAINS = {
    "reuters.com", "bloomberg.com", "wsj.com", "ft.com",
    "economist.com", "bbc.com", "nytimes.com", "apnews.com",
    "thehindu.com", "livemint.com", "business-standard.com",
    "cnbc.com", "forbes.com",
}

_INDUSTRY_DOMAINS = {
    "techcrunch.com", "electrek.co", "autocarpro.in", "pv-magazine.com",
    "statista.com", "mckinsey.com", "bcg.com", "bain.com", "gartner.com",
    "counterpointresearch.com", "idc.com",
}

_BLOG_DOMAINS = {
    "medium.com", "substack.com", "wordpress.com", "blogspot.com",
    "hashnode.dev", "dev.to", "tumblr.com",
}

_FORUM_SOCIAL_DOMAINS = {
    "reddit.com", "quora.com", "twitter.com", "x.com", "facebook.com",
    "instagram.com", "tiktok.com", "pinterest.com", "yahoo.com/answers",
}

_PRIMARY_PATTERNS = re.compile(
    r"(official report|annual report|sec filing|form 10-k|form 10-q|"
    r"gazette notification|ministry of|department of|press release|"
    r"empirical study|experimental results|methodology|doi\.org|"
    r"dataset|peer-reviewed|clinical trial|whitepaper)",
    re.IGNORECASE,
)

_METRIC_PATTERNS = re.compile(
    r"(\b\d+(?:\.\d+)?%\b|"                                # percentages: 45%, 12.5%, 28.5%
    r"[\$₹€£¥]\s*\d+(?:,\d+)*(?:\.\d+)?(?:\s*(?:billion|million|crore|trillion|B|M|k))?\b|" # currencies: $15.4B
    r"\b\d{4}\b|"                                           # years: 2026, 2025
    r"\b\d+(?:,\d+)*(?:\.\d+)?\s*(?:units|vehicles|gigawatts|GW|MW|kWh|Wh/kg|kg|tons|tonnes|CAGR|crore)\b|" # units
    r"\b\d{1,3}(?:,\d{3})+\b)",                             # formatted numbers: 1,200,000, 50,000
    re.IGNORECASE,
)

_STOP_WORDS = {
    "what", "how", "why", "when", "where", "who", "which",
    "is", "are", "was", "were", "the", "and", "for", "in",
    "of", "to", "with", "a", "an", "on", "at", "by", "from",
}


class CredibilityEvaluation(BaseModel):
    """
    Detailed evaluation breakdown for a source's credibility.
    """
    overall_score: float
    tier: str  # "very_high", "high", "medium_high", "medium", "low"
    authority_score: float
    recency_score: float
    relevance_score: float
    primary_source_score: float
    specificity_score: float
    agreement_score: float
    signals: List[str] = Field(default_factory=list)


class SourceCredibilityScorer:
    """
    Evaluates source credibility based on authority, recency, relevance,
    primary vs secondary nature, specificity, and cross-source agreement.
    """

    # Composite Pillar Weights
    _W_AUTHORITY = 0.30
    _W_RECENCY = 0.15
    _W_RELEVANCE = 0.15
    _W_PRIMARY = 0.15
    _W_SPECIFICITY = 0.15
    _W_AGREEMENT = 0.10

    def evaluate_source(
        self,
        source: Source,
        question: str = "",
        all_sources: Optional[List[Source]] = None,
    ) -> CredibilityEvaluation:
        """
        Evaluate and return full credibility score breakdown for a single source.
        """
        signals: List[str] = []

        # 1. Authority Score (30%)
        auth_score, auth_signal = self._evaluate_authority(source)
        signals.append(auth_signal)

        # 2. Recency Score (15%)
        rec_score, rec_signal = self._evaluate_recency(source)
        signals.append(rec_signal)

        # 3. Relevance Score (15%)
        rel_score, rel_signal = self._evaluate_relevance(source, question)
        signals.append(rel_signal)

        # 4. Primary vs Secondary (15%)
        prim_score, prim_signal = self._evaluate_primary_source(source)
        signals.append(prim_signal)

        # 5. Specificity & Data Density (15%)
        spec_score, spec_signal = self._evaluate_specificity(source)
        signals.append(spec_signal)

        # 6. Cross-Source Agreement (10%)
        agr_score, agr_signal = self._evaluate_cross_source_agreement(source, all_sources)
        if agr_signal:
            signals.append(agr_signal)

        # Composite Weighted Score
        composite = (
            self._W_AUTHORITY * auth_score
            + self._W_RECENCY * rec_score
            + self._W_RELEVANCE * rel_score
            + self._W_PRIMARY * prim_score
            + self._W_SPECIFICITY * spec_score
            + self._W_AGREEMENT * agr_score
        )
        final_score = round(min(max(composite, 0.05), 1.0), 4)
        tier = self.classify_tier(final_score)

        return CredibilityEvaluation(
            overall_score=final_score,
            tier=tier,
            authority_score=round(auth_score, 4),
            recency_score=round(rec_score, 4),
            relevance_score=round(rel_score, 4),
            primary_source_score=round(prim_score, 4),
            specificity_score=round(spec_score, 4),
            agreement_score=round(agr_score, 4),
            signals=[s for s in signals if s],
        )

    def evaluate_batch(
        self,
        sources: List[Source],
        question: str = "",
    ) -> List[Source]:
        """
        Evaluate a batch of sources, computing cross-source agreement across the batch
        and updating each source's credibility_score and metadata breakdown.
        """
        if not sources:
            return []

        for s in sources:
            evaluation = self.evaluate_source(s, question=question, all_sources=sources)
            s.credibility_score = evaluation.overall_score
            if not isinstance(s.metadata, dict):
                s.metadata = {}
            s.metadata["credibility_tier"] = evaluation.tier
            s.metadata["credibility_breakdown"] = evaluation.model_dump()

        return sources

    @staticmethod
    def classify_tier(score: float) -> str:
        """Classify numerical credibility score into standard tier."""
        if score >= 0.78:
            return "very_high"
        elif score >= 0.65:
            return "high"
        elif score >= 0.50:
            return "medium_high"
        elif score >= 0.38:
            return "medium"
        return "low"

    def _evaluate_authority(self, source: Source) -> tuple[float, str]:
        """Pillar 1: Authority based on domain classification and source type."""
        domain = (source.domain or "").lower().strip()
        st = (source.source_type or "").lower().strip()

        # Check domain patterns first
        for g_dom in _GOVERNMENT_DOMAINS:
            if g_dom in domain or st == SourceType.GOVERNMENT:
                return 0.98, "Government authority (.gov / official institution)"

        for a_dom in _ACADEMIC_DOMAINS:
            if a_dom in domain or st == SourceType.ACADEMIC:
                return 0.96, "Academic research institution (peer-reviewed / scientific)"

        if st == SourceType.FINANCIAL or "sec.gov" in domain:
            return 0.88, "Financial filing / audited market authority"

        for n_dom in _TIER1_NEWS_DOMAINS:
            if n_dom in domain:
                return 0.88, "Tier-1 international news publication"

        if st == SourceType.NEWS:
            return 0.80, "News publication"

        for i_dom in _INDUSTRY_DOMAINS:
            if i_dom in domain:
                return 0.82, "Recognized industry research publication"

        if st == SourceType.COMPANY:
            return 0.78, "Official corporate source"

        for b_dom in _BLOG_DOMAINS:
            if b_dom in domain or st == SourceType.BLOG:
                return 0.55, "Independent blog / self-published article"

        for f_dom in _FORUM_SOCIAL_DOMAINS:
            if f_dom in domain or st in (SourceType.FORUM, SourceType.SOCIAL):
                return 0.10, "Forum / social media user-generated content"

        return 0.65, "Standard web domain"

    def _evaluate_recency(self, source: Source) -> tuple[float, str]:
        """Pillar 2: Recency based on publication date."""
        st = (source.source_type or "").lower().strip()
        current_year = datetime.now().year
        raw_date = source.published_at or source.publication_date or source.published_date or ""
        
        match = re.search(r"\b(20\d{2})\b", str(raw_date))
        if match:
            pub_year = int(match.group(1))
            age = current_year - pub_year
            if age <= 0:  # Current year or future forecast
                score = 1.0
            elif age == 1:
                score = 0.90
            elif age == 2:
                score = 0.80
            elif age <= 4:
                score = 0.65
            else:
                score = 0.40
            
            # Cap recency for forum/social since unverified user posts shouldn't gain undue trust from recency
            if st in (SourceType.FORUM, SourceType.SOCIAL):
                score = min(score, 0.50)
            return score, f"Publication date ({pub_year})"

        return 0.50 if st in (SourceType.FORUM, SourceType.SOCIAL) else 0.60, "Undated publication"

    def _evaluate_relevance(self, source: Source, question: str) -> tuple[float, str]:
        """Pillar 3: Relevance between question and source."""
        if not question:
            return max(source.relevance_score, 0.80), "Default relevance"

        # Token overlap with 2+ char tokens (supporting terms like EV, AI, ML, 5G)
        q_tokens = [
            t.lower() for t in re.findall(r"[a-z0-9]+", question)
            if len(t) >= 2 and t.lower() not in _STOP_WORDS
        ]
        if not q_tokens:
            return 0.80, "Neutral relevance"

        text_to_check = f"{source.title} {source.snippet} {source.content[:1500]}".lower()
        hits = sum(1 for t in q_tokens if t in text_to_check)
        ratio = hits / len(q_tokens)
        
        score = min(max(ratio, 0.4), 1.0)
        return score, f"Topic token overlap ({int(ratio * 100)}%)"

    def _evaluate_primary_source(self, source: Source) -> tuple[float, str]:
        """Pillar 4: Primary vs Secondary evidence assessment."""
        text = f"{source.title} {source.content}".lower()
        st = (source.source_type or "").lower().strip()
        
        if st in (SourceType.GOVERNMENT, SourceType.ACADEMIC):
            return 0.95, "Primary source (official institutional / peer-reviewed)"

        if _PRIMARY_PATTERNS.search(text):
            return 0.90, "Primary indicators detected (filings, datasets, or official study)"

        if st in (SourceType.NEWS, SourceType.COMPANY, SourceType.FINANCIAL):
            return 0.75, "Secondary source (editorial / market reporting)"

        if st in (SourceType.BLOG, SourceType.OTHER, SourceType.WEB):
            return 0.50, "Secondary / tertiary commentary"

        if st in (SourceType.FORUM, SourceType.SOCIAL):
            return 0.10, "Tertiary / unverified user content"

        return 0.30, "Unverified user content"

    def _evaluate_specificity(self, source: Source) -> tuple[float, str]:
        """Pillar 5: Specificity and quantitative information density."""
        content = f"{source.title} {source.snippet} {source.content}"
        metrics = _METRIC_PATTERNS.findall(content)
        metric_count = len(metrics)

        if metric_count >= 3:
            return 0.95, f"High quantitative data density ({metric_count}+ statistics/metrics)"
        elif metric_count >= 2:
            return 0.85, f"Moderate quantitative metrics present ({metric_count} data points)"
        elif metric_count >= 1:
            return 0.70, f"Some specific figures detected ({metric_count} metric)"
        elif len(content.strip()) > 100:
            return 0.50, "Descriptive text with minimal quantitative figures"
        return 0.30, "Low information specificity"

    def _evaluate_cross_source_agreement(
        self,
        source: Source,
        all_sources: Optional[List[Source]],
    ) -> tuple[float, str]:
        """Pillar 6: Cross-source corroboration across the batch."""
        st = (source.source_type or "").lower().strip()
        is_low_auth = st in (SourceType.FORUM, SourceType.SOCIAL)

        if not all_sources or len(all_sources) <= 1:
            return 0.40 if is_low_auth else 0.75, ""  # Baseline if single source

        source_text = f"{source.title} {source.content[:500]}".lower()
        source_words = set(w for w in re.findall(r"[a-z0-9]+", source_text) if len(w) > 3 and w not in _STOP_WORDS)
        if not source_words:
            return 0.40 if is_low_auth else 0.75, ""

        corroborating_count = 0
        for other in all_sources:
            if other.source_id == source.source_id or other.url == source.url:
                continue
            other_text = f"{other.title} {other.content[:500]}".lower()
            other_words = set(w for w in re.findall(r"[a-z0-9]+", other_text) if len(w) > 3 and w not in _STOP_WORDS)
            common = source_words.intersection(other_words)
            if len(common) >= 2:
                corroborating_count += 1

        if corroborating_count >= 2:
            return 0.95, f"Corroborated by {corroborating_count} peer sources in batch"
        elif corroborating_count == 1:
            return 0.85, "Corroborated by 1 peer source"
        return 0.35 if is_low_auth else 0.60, "Single-source claim (no cross-source peer overlap)"


source_credibility_scorer = SourceCredibilityScorer()
credibility_scorer = source_credibility_scorer
