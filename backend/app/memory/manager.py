"""
Day 26 & Day 85–90 — Unified Research Memory Manager

Orchestrates:
  1. Short-Term Memory: Active research session state and working notes
  2. Long-Term Memory: Cross-session knowledge reuse & topic recall
  3. User Memory: Personalized preferences, histories, and constraints
  4. Source Memory: URL content caching, reuse tracking, and domain credibility
  5. Entity Memory: Entity knowledge, hierarchical domain mapping, and previous conclusions (Day 85–87)
  6. Knowledge Graph: Graph traversal, multi-hop reasoning, and relationship ecosystem (Day 88–90)

Workflow:
  Research A completes → Ingests findings into Long-Term, User, Source, Entity memory, and Knowledge Graph.
  Research B starts   → Recalls prior findings, cached sources, previous conclusions, and graph neighborhood paths.
"""

from typing import List, Dict, Any, Optional
from app.memory.short_term import ShortTermMemory
from app.memory.long_term import long_term_memory, LongTermMemory
from app.memory.user_memory import user_memory, UserMemory, UserProfile
from app.memory.source_memory import source_memory, SourceMemory
from app.memory.entity_memory import entity_memory, EntityMemoryManager, EntityType
from app.memory.knowledge_graph import knowledge_graph, KnowledgeGraph, RelationType
from app.utils.logger import logger


class ResearchMemoryManager:
    """
    Central coordinator for multi-tier autonomous research memory and knowledge graph.
    """

    def __init__(
        self,
        long_term: Optional[LongTermMemory] = None,
        user_mem: Optional[UserMemory] = None,
        source_mem: Optional[SourceMemory] = None,
        entity_mem: Optional[EntityMemoryManager] = None,
        graph: Optional[KnowledgeGraph] = None,
    ):
        self.long_term = long_term or long_term_memory
        self.user_mem = user_mem or user_memory
        self.source_mem = source_mem or source_memory
        self.entity_mem = entity_mem or entity_memory
        self.graph = graph or knowledge_graph
        self._active_sessions: Dict[str, ShortTermMemory] = {}

    # ------------------------------------------------------------------
    # Session Lifecycle
    # ------------------------------------------------------------------

    def start_session(self, research_id: str, query: str, user_id: str = "anonymous") -> ShortTermMemory:
        """
        Initialize short-term working memory for an active research job
        and register the query in the user's history.
        """
        session = ShortTermMemory(research_id=research_id, query=query, user_id=user_id)
        self._active_sessions[research_id] = session
        self.user_mem.record_query(user_id=user_id, query=query, research_id=research_id)
        logger.debug(f"ResearchMemoryManager: started session {research_id} for user {user_id}")
        return session

    def get_session(self, research_id: str) -> Optional[ShortTermMemory]:
        """Retrieve active short-term session memory."""
        return self._active_sessions.get(research_id)

    async def complete_session(
        self,
        research_id: str,
        summary: str,
        topic: Optional[str] = None,
        key_claims: Optional[List[Dict[str, Any]]] = None,
        top_sources: Optional[List[Dict[str, Any]]] = None,
        tags: Optional[List[str]] = None,
        entities: Optional[List[Dict[str, Any]]] = None,
        relationships: Optional[List[Dict[str, Any]]] = None,
        conclusions: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Finalize research session:
          1. Ingest findings and summary into Long-Term Memory
          2. Cache all sources in Source Memory
          3. Upsert discovered entities and store previous conclusions in Entity Memory (Day 85–87)
          4. Ingest domain relationships into Knowledge Graph (Day 88–90)
          5. Clear active short-term session
        """
        session = self._active_sessions.pop(research_id, None)
        query = session.query if session else (topic or "Research Study")
        user_id = session.user_id if session else "anonymous"

        # 1. Store in Long-Term Memory
        record = await self.long_term.store_research_knowledge(
            research_id=research_id,
            query=query,
            summary=summary,
            topic=topic or query,
            key_claims=key_claims,
            top_sources=top_sources,
            tags=tags,
        )

        # 2. Store sources in Source Memory
        if top_sources:
            for s in top_sources:
                url = s.get("url") or ""
                if url:
                    self.source_mem.record_source(
                        url=url,
                        title=s.get("title") or "Source",
                        domain=s.get("domain") or "",
                        clean_text=s.get("clean_text") or s.get("content") or "",
                        source_type=s.get("source_type") or "web",
                        credibility_score=float(s.get("credibility_score") or 0.5),
                        research_id=research_id,
                    )

        # 3. Store Entities & Conclusions in Entity Memory (Day 85–87)
        if entities:
            for ent in entities:
                await self.entity_mem.upsert_entity(
                    name=ent.get("name", ""),
                    entity_type=ent.get("entity_type", EntityType.GENERAL),
                    description=ent.get("description"),
                    company=ent.get("company"),
                    industry=ent.get("industry"),
                    country=ent.get("country"),
                    aliases=ent.get("aliases"),
                    attributes=ent.get("attributes"),
                    research_id=research_id
                )

        if conclusions:
            for conc in conclusions:
                await self.entity_mem.record_conclusion(
                    topic=topic or query,
                    conclusion_text=conc,
                    research_id=research_id,
                    user_id=user_id,
                    tags=tags
                )
        elif summary:
            await self.entity_mem.record_conclusion(
                topic=topic or query,
                conclusion_text=summary[:500],
                research_id=research_id,
                user_id=user_id,
                tags=tags
            )

        # 4. Ingest into Knowledge Graph (Day 88–90)
        self.graph.ingest_from_research(
            research_id=research_id,
            topic=topic or query,
            entities=entities,
            relationships=relationships
        )

        logger.debug(f"ResearchMemoryManager: completed session {research_id} saved across all memory tiers & knowledge graph")
        return {
            "status": "completed",
            "knowledge_id": record.id,
            "research_id": research_id,
            "topic": record.topic,
        }

    # ------------------------------------------------------------------
    # Knowledge & Graph Recall for New Research
    # ------------------------------------------------------------------

    async def recall_prior_context(
        self,
        query: str,
        user_id: Optional[str] = None,
        top_k: int = 3,
    ) -> Dict[str, Any]:
        """
        Recall multi-tier context for upcoming research:
          - Prior research findings & claims from Long-Term Memory
          - User profile & preferences from User Memory
          - Previous conclusions & matching entities from Entity Memory (Day 85–87)
          - Knowledge graph neighborhood insights (Day 88–90)
        """
        user_profile = self.user_mem.get_or_create_profile(user_id or "anonymous")
        prior_knowledge = await self.long_term.recall_related_knowledge(query=query, top_k=top_k)
        matching_entities = await self.entity_mem.search_entities(query=query, limit=5)
        conclusions = await self.entity_mem.get_conclusions_by_topic(topic=query, limit=5)

        # Knowledge graph neighborhood exploration
        graph_insights = []
        for ent in matching_entities:
            neighborhood = self.graph.get_neighborhood(ent.name, depth=2)
            if neighborhood["total_nodes"] > 1:
                graph_insights.append({
                    "entity": ent.name,
                    "connected_nodes_count": neighborhood["total_nodes"],
                    "connected_edges_count": neighborhood["total_edges"]
                })

        return {
            "query": query,
            "user_preferences": {
                "preferred_depth": user_profile.preferred_depth,
                "preferred_breadth": user_profile.preferred_breadth,
                "preferred_categories": user_profile.preferred_categories,
                "domain_whitelist": user_profile.domain_whitelist,
                "domain_blacklist": user_profile.domain_blacklist,
                "citation_style": user_profile.citation_style,
                "detail_level": user_profile.detail_level,
            },
            "prior_research_findings": prior_knowledge,
            "has_prior_knowledge": len(prior_knowledge) > 0,
            "entities": [e.model_dump(mode="json") for e in matching_entities],
            "previous_conclusions": [c.model_dump(mode="json") for c in conclusions],
            "graph_insights": graph_insights
        }

    def clear_all(self) -> None:
        """Reset all memory tiers (primarily for test isolation)."""
        self._active_sessions.clear()
        self.long_term.clear()
        self.user_mem.clear()
        self.source_mem.clear()
        self.entity_mem.clear()
        self.graph.clear()


memory_manager = ResearchMemoryManager()
