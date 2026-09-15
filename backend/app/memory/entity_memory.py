"""
Day 85–87 — Advanced Agent Memory
Provides persistent storage and reasoning for:
  - Entity Knowledge (Companies, Technologies, Markets, Policies, etc.)
  - Hierarchical Entity Structure: Entity → Company → Industry → Country → Evidence
  - Previous Conclusions & Hypotheses tracking
"""

from enum import Enum
from datetime import datetime
from typing import Optional, List, Dict, Any, Set
from pydantic import BaseModel, Field
from app.utils.helpers import generate_uuid, get_utc_now
from app.database.mongodb import db_manager


class EntityType(str, Enum):
    COMPANY = "company"
    INDUSTRY = "industry"
    MARKET = "market"
    COUNTRY = "country"
    PRODUCT = "product"
    TECHNOLOGY = "technology"
    POLICY = "policy"
    PERSON = "person"
    EVIDENCE = "evidence"
    GENERAL = "general"


class EntityKnowledge(BaseModel):
    id: str = Field(default_factory=generate_uuid)
    name: str
    entity_type: EntityType = EntityType.GENERAL
    aliases: List[str] = Field(default_factory=list)
    description: Optional[str] = None
    company: Optional[str] = None
    industry: Optional[str] = None
    country: Optional[str] = None
    attributes: Dict[str, Any] = Field(default_factory=dict)
    evidence_ids: List[str] = Field(default_factory=list)
    research_ids: List[str] = Field(default_factory=list)
    confidence: float = 1.0
    created_at: datetime = Field(default_factory=get_utc_now)
    updated_at: datetime = Field(default_factory=get_utc_now)


class HierarchicalEntity(BaseModel):
    """
    Structured hierarchy: Entity → Company → Industry → Country → Evidence
    """
    entity_id: str
    name: str
    entity_type: EntityType
    company: Optional[str] = None
    industry: Optional[str] = None
    country: Optional[str] = None
    evidence_items: List[Dict[str, Any]] = Field(default_factory=list)
    confidence_score: float = 1.0
    attributes: Dict[str, Any] = Field(default_factory=dict)

    def to_lineage_path(self) -> str:
        parts = [self.name]
        if self.company and self.company != self.name:
            parts.append(f"Company: {self.company}")
        if self.industry:
            parts.append(f"Industry: {self.industry}")
        if self.country:
            parts.append(f"Country: {self.country}")
        return " → ".join(parts)


class PreviousConclusion(BaseModel):
    id: str = Field(default_factory=generate_uuid)
    topic: str
    conclusion_text: str
    key_findings: List[str] = Field(default_factory=list)
    supporting_evidence: List[Dict[str, Any]] = Field(default_factory=list)
    confidence: float = 0.9
    consensus_status: str = "established"  # established, emerging, disputed
    research_id: Optional[str] = None
    user_id: Optional[str] = "anonymous"
    tags: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=get_utc_now)


class EntityMemoryManager:
    """
    Manages structured entity knowledge, previous conclusions,
    and hierarchical domain mappings across research jobs.
    """

    def __init__(self):
        self._entities: Dict[str, EntityKnowledge] = {}
        self._conclusions: Dict[str, PreviousConclusion] = {}

    # -------------------------------------------------------------
    # Entity Knowledge Operations
    # -------------------------------------------------------------
    async def upsert_entity(
        self,
        name: str,
        entity_type: EntityType = EntityType.GENERAL,
        description: Optional[str] = None,
        company: Optional[str] = None,
        industry: Optional[str] = None,
        country: Optional[str] = None,
        aliases: Optional[List[str]] = None,
        attributes: Optional[Dict[str, Any]] = None,
        evidence_id: Optional[str] = None,
        research_id: Optional[str] = None,
        confidence: float = 1.0
    ) -> EntityKnowledge:
        norm_key = name.strip().lower()

        # Check existing
        existing = None
        for ent in self._entities.values():
            if ent.name.lower() == norm_key or (aliases and any(a.lower() == norm_key for a in ent.aliases)):
                existing = ent
                break

        if existing:
            if description and not existing.description:
                existing.description = description
            if company:
                existing.company = company
            if industry:
                existing.industry = industry
            if country:
                existing.country = country
            if aliases:
                existing.aliases = list(set(existing.aliases + aliases))
            if attributes:
                existing.attributes.update(attributes)
            if evidence_id and evidence_id not in existing.evidence_ids:
                existing.evidence_ids.append(evidence_id)
            if research_id and research_id not in existing.research_ids:
                existing.research_ids.append(research_id)
            existing.confidence = min(1.0, max(existing.confidence, confidence))
            existing.updated_at = get_utc_now()
            return existing

        new_entity = EntityKnowledge(
            name=name.strip(),
            entity_type=entity_type,
            aliases=aliases or [],
            description=description,
            company=company,
            industry=industry,
            country=country,
            attributes=attributes or {},
            evidence_ids=[evidence_id] if evidence_id else [],
            research_ids=[research_id] if research_id else [],
            confidence=confidence
        )
        self._entities[new_entity.id] = new_entity
        return new_entity

    async def get_entity(self, entity_id_or_name: str) -> Optional[EntityKnowledge]:
        norm = entity_id_or_name.strip().lower()
        if entity_id_or_name in self._entities:
            return self._entities[entity_id_or_name]
        for ent in self._entities.values():
            if ent.name.lower() == norm or any(a.lower() == norm for a in ent.aliases):
                return ent
        return None

    async def search_entities(
        self,
        query: Optional[str] = None,
        entity_type: Optional[EntityType] = None,
        industry: Optional[str] = None,
        country: Optional[str] = None,
        limit: int = 50
    ) -> List[EntityKnowledge]:
        results = list(self._entities.values())
        if entity_type:
            results = [e for e in results if e.entity_type == entity_type]
        if industry:
            results = [e for e in results if e.industry and industry.lower() in e.industry.lower()]
        if country:
            results = [e for e in results if e.country and country.lower() in e.country.lower()]
        if query:
            q = query.lower().strip()
            matched = []
            for e in results:
                e_name = e.name.lower()
                if q in e_name or e_name in q:
                    matched.append(e)
                elif any(q in a.lower() or a.lower() in q for a in e.aliases):
                    matched.append(e)
                elif e.description and (q in e.description.lower() or e.description.lower() in q):
                    matched.append(e)
                elif e.company and (q in e.company.lower() or e.company.lower() in q):
                    matched.append(e)
                elif any(term in q for term in e_name.split() if len(term) > 2):
                    matched.append(e)
            results = matched
        return results[:limit]

    def build_hierarchy(self, entity: EntityKnowledge, evidence_list: Optional[List[Dict[str, Any]]] = None) -> HierarchicalEntity:
        """
        Constructs a hierarchical view: Entity → Company → Industry → Country → Evidence
        """
        return HierarchicalEntity(
            entity_id=entity.id,
            name=entity.name,
            entity_type=entity.entity_type,
            company=entity.company or (entity.name if entity.entity_type == EntityType.COMPANY else None),
            industry=entity.industry,
            country=entity.country,
            evidence_items=evidence_list or [],
            confidence_score=entity.confidence,
            attributes=entity.attributes
        )

    # -------------------------------------------------------------
    # Previous Conclusions & Hypotheses Operations
    # -------------------------------------------------------------
    async def record_conclusion(
        self,
        topic: str,
        conclusion_text: str,
        key_findings: Optional[List[str]] = None,
        supporting_evidence: Optional[List[Dict[str, Any]]] = None,
        confidence: float = 0.9,
        consensus_status: str = "established",
        research_id: Optional[str] = None,
        user_id: Optional[str] = "anonymous",
        tags: Optional[List[str]] = None
    ) -> PreviousConclusion:
        conclusion = PreviousConclusion(
            topic=topic,
            conclusion_text=conclusion_text,
            key_findings=key_findings or [],
            supporting_evidence=supporting_evidence or [],
            confidence=confidence,
            consensus_status=consensus_status,
            research_id=research_id,
            user_id=user_id,
            tags=tags or []
        )
        self._conclusions[conclusion.id] = conclusion
        return conclusion

    async def get_conclusions_by_topic(self, topic: str, limit: int = 10) -> List[PreviousConclusion]:
        """
        Search conclusions by topic using bidirectional token matching.
        Matches if:
        - Full query appears in conclusion topic / text / tags, OR
        - Any significant word (>2 chars) from query appears in conclusion topic/tags, OR
        - Conclusion topic words appear in query
        """
        q = topic.lower().strip()
        # Extract meaningful tokens (>2 chars) from the query
        query_tokens = [t for t in q.split() if len(t) > 2]

        matched = []
        for c in self._conclusions.values():
            c_topic = c.topic.lower()
            c_text = c.conclusion_text.lower()
            c_tags = [t.lower() for t in c.tags]

            # Full phrase match
            if q in c_topic or q in c_text:
                matched.append(c)
                continue

            # Tag match
            if any(q in tag or tag in q for tag in c_tags):
                matched.append(c)
                continue

            # Bidirectional token match: any word from query appears in topic or vice versa
            if any(tok in c_topic for tok in query_tokens):
                matched.append(c)
                continue

            # Topic tokens appear in the query
            topic_tokens = [t for t in c_topic.split() if len(t) > 2]
            if any(tok in q for tok in topic_tokens):
                matched.append(c)
                continue

        matched.sort(key=lambda c: c.created_at, reverse=True)
        return matched[:limit]

    async def list_conclusions(self, limit: int = 50) -> List[PreviousConclusion]:
        res = list(self._conclusions.values())
        res.sort(key=lambda c: c.created_at, reverse=True)
        return res[:limit]

    def clear(self):
        self._entities.clear()
        self._conclusions.clear()


entity_memory = EntityMemoryManager()
