"""
Day 26 — Long-Term Memory (Cross-Research Knowledge Base)

Preserves key takeaways, claims, synthesis reports, and topic associations
across completed research runs. Allows Research B to query and reuse findings from Research A.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field
import numpy as np

from app.utils.helpers import get_utc_now, generate_uuid
from app.llm.embeddings import embedding_service
from app.rag.reranker import tokenize


class ResearchKnowledgeRecord(BaseModel):
    id: str = Field(default_factory=generate_uuid)
    research_id: str
    query: str
    topic: str
    summary: str
    key_claims: List[Dict[str, Any]] = Field(default_factory=list)
    top_sources: List[Dict[str, Any]] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=get_utc_now)
    embedding: Optional[List[float]] = None


class LongTermMemory:
    """
    Stores and retrieves cross-session research knowledge.
    Uses dense vector similarity + keyword matching over past research syntheses.
    """

    def __init__(self):
        self._records: Dict[str, ResearchKnowledgeRecord] = {}

    async def store_research_knowledge(
        self,
        research_id: str,
        query: str,
        summary: str,
        topic: Optional[str] = None,
        key_claims: Optional[List[Dict[str, Any]]] = None,
        top_sources: Optional[List[Dict[str, Any]]] = None,
        tags: Optional[List[str]] = None,
    ) -> ResearchKnowledgeRecord:
        """Store a completed research run's knowledge snapshot."""
        resolved_topic = topic or query
        record = ResearchKnowledgeRecord(
            research_id=research_id,
            query=query,
            topic=resolved_topic,
            summary=summary,
            key_claims=key_claims or [],
            top_sources=top_sources or [],
            tags=tags or [],
        )

        # Generate embedding for the knowledge representation
        text_to_embed = f"Topic: {resolved_topic}\nQuery: {query}\nSummary: {summary}"
        try:
            record.embedding = await embedding_service.get_embedding(text_to_embed)
        except Exception:
            record.embedding = None

        self._records[research_id] = record
        return record

    async def recall_related_knowledge(
        self,
        query: str,
        top_k: int = 3,
        min_similarity: float = 0.35,
    ) -> List[Dict[str, Any]]:
        """
        Search previous research knowledge relevant to the new query.
        Returns prior research records with similarity score and key takeaways.
        """
        if not self._records or not query:
            return []

        # 1. Compute query embedding
        try:
            q_vec = np.array(await embedding_service.get_embedding(query), dtype=np.float32)
            has_embed = True
        except Exception:
            has_embed = False

        q_tokens = set(tokenize(query))

        scored_records: List[tuple] = []
        for record in self._records.values():
            score = 0.0

            # Dense semantic similarity
            if has_embed and record.embedding:
                rec_vec = np.array(record.embedding, dtype=np.float32)
                sim = float(np.dot(q_vec, rec_vec) / (np.linalg.norm(q_vec) * np.linalg.norm(rec_vec) + 1e-9))
                score += 0.70 * max(sim, 0.0)

            # Lexical overlap on topic & summary
            rec_text = f"{record.topic} {record.query} {record.summary}"
            rec_tokens = set(tokenize(rec_text))
            if q_tokens and rec_tokens:
                overlap = len(q_tokens & rec_tokens) / len(q_tokens)
                score += 0.30 * overlap

            if score >= min_similarity:
                scored_records.append((record, score))

        scored_records.sort(key=lambda x: x[1], reverse=True)

        results = []
        for rec, sc in scored_records[:top_k]:
            results.append({
                "research_id": rec.research_id,
                "query": rec.query,
                "topic": rec.topic,
                "summary": rec.summary,
                "key_claims": rec.key_claims,
                "top_sources": rec.top_sources,
                "tags": rec.tags,
                "relevance_score": round(sc, 4),
                "created_at": rec.created_at.isoformat(),
            })

        return results

    def get_record(self, research_id: str) -> Optional[ResearchKnowledgeRecord]:
        return self._records.get(research_id)

    def count(self) -> int:
        return len(self._records)

    def clear(self) -> None:
        self._records.clear()


long_term_memory = LongTermMemory()
