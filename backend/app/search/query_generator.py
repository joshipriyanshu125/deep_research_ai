"""
Day 12 — Query Generator
Expands a single research question into multiple targeted search queries
using LLM (when available) or a deterministic template-based fallback.
"""
import asyncio
import json
import re
from typing import List, Optional
from app.utils.logger import logger
from app.llm.prompts import PromptConfig


# ---------------------------------------------------------------------------
# Template-based fallback patterns
# ---------------------------------------------------------------------------

_QUERY_TEMPLATES = [
    "{topic} market size {year}",
    "{topic} growth forecast {next_year}",
    "{topic} leading companies players",
    "{topic} government policy regulation",
    "{topic} technology innovation trends",
    "{topic} investment risks challenges",
    "{topic} statistics data report",
    "{topic} latest news developments",
]

_GENERAL_TEMPLATES = [
    "{topic}",
    "{topic} authoritative explanation evidence",
    "{topic} primary sources findings",
    "{topic} latest developments {year}",
    "{topic} comparisons limitations",
    "{topic} published data references",
    "{topic} review analysis",
    "{topic} open questions",
]

_ACADEMIC_TEMPLATES = [
    "{topic} research study findings",
    "{topic} empirical analysis paper",
    "{topic} systematic review literature",
    "{topic} benchmark performance evaluation",
    "{topic} theoretical framework model",
    "{topic} experimental results dataset",
]

_MARKET_TEMPLATES = [
    "{topic} market share revenue",
    "{topic} industry analysis report",
    "{topic} competitive landscape overview",
    "{topic} investor funding acquisitions",
    "{topic} demand supply chain dynamics",
    "{topic} consumer adoption trends",
]


def _extract_topic(question: str) -> str:
    """Strip question and filler words to get the core topic phrase."""
    stop_words = {
        "what", "who", "why", "how", "when", "where",
        "which", "is", "are", "was", "were", "do", "does", "did",
        "can", "could", "should", "would", "will", "shall",
        "explain", "describe", "analyze", "compare", "give", "tell", "me",
        "the", "a", "an", "in", "of", "for", "about", "to", "with",
    }
    q = question.strip().rstrip("?").strip()
    words = q.split()
    while words and words[0].lower() in stop_words:
        words = words[1:]
    
    extracted = " ".join(words).strip()
    return extracted or question.strip()


def _deduplicate(queries: List[str]) -> List[str]:
    """Remove exact duplicates while preserving order."""
    seen: set = set()
    result = []
    for q in queries:
        norm = q.strip().lower()
        if norm and norm not in seen:
            seen.add(norm)
            result.append(q.strip())
    return result


class QueryGenerator:
    """
    Generates multiple targeted search queries from a research question.

    Pipeline:
      1. Try LLM to produce diverse, nuanced queries.
      2. Fall back to template expansion if LLM unavailable / fails.
      3. Always deduplicate before returning.
    """

    _LLM_SYSTEM_PROMPT = (
        "You are a research strategist. Given a research question and topic, "
        "generate diverse, specific, and targeted web search queries. "
        "Each query must preserve the requested subject and explore relevant "
        "facts, primary sources, comparisons, limitations, or recent findings. "
        "Only use commercial or investment angles when the question requests them. "
        "Return ONLY a valid JSON array of strings. No explanation, no markdown."
    )

    async def generate_queries(
        self,
        question: str,
        topic: Optional[str] = None,
        n: int = 6,
        category: str = "web",
    ) -> List[str]:
        """
        Generate `n` distinct search queries for the given research question.

        Args:
            question:  The research question (e.g. "What is the Indian EV market size?")
            topic:     Optional short topic label (e.g. "Indian EV market")
            n:         Number of queries to generate (default 6)
            category:  "web" | "academic" | "market" — chooses template set

        Returns:
            Deduplicated list of search query strings.
        """
        topic = topic or _extract_topic(question)
        n = max(1, min(int(n or 1), 12))
        queries: List[str] = []

        # --- 1. Try LLM ---
        try:
            queries = await self._llm_generate(question, topic, n)
        except Exception as e:
            logger.warning(f"QueryGenerator LLM failed ({e}), using template fallback.")

        # --- 2. Template fallback if LLM gave nothing ---
        if not queries:
            queries = self._template_generate(topic, n, category)

        # A provider can return a polished-looking list for a different
        # familiar subject.  Keep only queries that retain at least one
        # informative token from the requested topic/question.
        topic_tokens = {
            token for token in re.findall(r"[a-z0-9]+", topic.lower())
            if len(token) > 2 or token in {"ai", "ev", "ml"}
        }
        relevant_queries = [
            str(q).strip()
            for q in queries
            if str(q).strip()
            and (
                not topic_tokens
                or topic_tokens.intersection(re.findall(r"[a-z0-9]+", str(q).lower()))
            )
        ]
        if relevant_queries:
            canonical_topic = topic.strip()
            # When a provider returns only a partial list, normalize the
            # partial results before filling the remainder so the complete
            # bounded set has one auditable subject label.  Preserve a full
            # provider list verbatim for compatibility with provider-specific
            # query phrasing and exact-query consumers.
            if len(relevant_queries) < n:
                queries = [
                    q if canonical_topic.lower() in q.lower() else f"{canonical_topic} {q}"
                    for q in relevant_queries
                ]
            else:
                queries = relevant_queries
        else:
            queries = self._template_generate(topic, n, category)

        queries = _deduplicate(queries)
        if len(queries) < n:
            # Keep any valid provider queries, then fill the requested bounded
            # count with deterministic subject-preserving queries.
            for fallback_query in self._template_generate(topic, n, category):
                if fallback_query.strip().lower() not in {item.lower() for item in queries}:
                    queries.append(fallback_query)
                if len(queries) >= n:
                    break
        queries = queries[:n]
        logger.info(f"QueryGenerator produced {len(queries)} queries for: '{question[:60]}'")
        return queries

    # ------------------------------------------------------------------
    # LLM path
    # ------------------------------------------------------------------

    async def _llm_generate(self, question: str, topic: str, n: int) -> List[str]:
        # Lazy import to avoid circular deps
        from app.llm.service import get_llm_service
        llm = get_llm_service()

        prompt = (
            f"Research question: {question}\n"
            f"Core topic: {topic}\n"
            f"Generate exactly {n} distinct search queries covering different angles.\n"
            "Return a JSON array of strings only."
        )
        prompt_config = PromptConfig(
            name="query_generation",
            version="1.0.0",
            system_prompt=self._LLM_SYSTEM_PROMPT,
            user_template="{prompt}",
            temperature=0.2,
            max_tokens=1200,
        )
        raw = await llm.execute_prompt(
            prompt_config,
            variables={"prompt": prompt},
            is_json=True,
        )
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [str(q) for q in parsed if q]
        # Handle {"queries": [...]} wrapper
        if isinstance(parsed, dict):
            for key in ("queries", "results", "search_queries"):
                if key in parsed and isinstance(parsed[key], list):
                    return [str(q) for q in parsed[key] if q]
        return []

    # ------------------------------------------------------------------
    # Template fallback
    # ------------------------------------------------------------------

    def _template_generate(self, topic: str, n: int, category: str) -> List[str]:
        import datetime
        year = datetime.datetime.now().year
        next_year = year + 1

        if category == "academic":
            templates = _ACADEMIC_TEMPLATES
        elif category == "market":
            templates = _MARKET_TEMPLATES
        elif re.search(r"\b(market|investment|revenue|sales|industry|pricing)\b", topic, re.IGNORECASE):
            templates = _QUERY_TEMPLATES
        else:
            templates = _GENERAL_TEMPLATES

        queries = []
        for tmpl in templates[:n]:
            q = tmpl.format(topic=topic, year=year, next_year=next_year)
            queries.append(q)
        return queries


query_generator = QueryGenerator()
