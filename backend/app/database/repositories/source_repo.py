"""
Day 16 — Source Repository
Repository managing the `research_sources` collection in MongoDB
with in-memory fallback, fast content_hash duplicate check, and multi-criteria querying.
"""
from typing import Optional, List, Dict, Any
from app.database.mongodb import db_manager
from app.database.models.source import Source, SourceType


class SourceRepository:
    """
    CRUD repository for research sources, managing storage in the `research_sources` collection.
    """

    def __init__(self):
        self._sources: Dict[str, Source] = {}

    async def create_source(self, source: Source) -> Source:
        """Insert a source record into `research_sources`."""
        if db_manager.is_connected:
            await db_manager.db.research_sources.insert_one(source.model_dump())
        else:
            self._sources[source.source_id] = source
        return source

    async def get_source(self, source_id: str) -> Optional[Source]:
        """Fetch single source by source_id or id."""
        if db_manager.is_connected:
            doc = await db_manager.db.research_sources.find_one({
                "$or": [{"source_id": source_id}, {"id": source_id}]
            })
            return Source(**doc) if doc else None
        
        for s in self._sources.values():
            if s.source_id == source_id or s.id == source_id:
                return s
        return None

    async def get_sources_by_research(
        self,
        research_id: str,
        domain: Optional[str] = None,
        source_type: Optional[str] = None,
        language: Optional[str] = None,
        min_relevance: Optional[float] = None,
        min_credibility: Optional[float] = None,
    ) -> List[Source]:
        """Query sources for a research job with multi-criteria filters."""
        if db_manager.is_connected:
            query: Dict[str, Any] = {"research_id": research_id}
            if domain:
                query["domain"] = domain.lower().strip()
            if source_type:
                query["source_type"] = source_type.lower().strip()
            if language:
                query["language"] = language.lower().strip()
            if min_relevance is not None:
                query["relevance_score"] = {"$gte": min_relevance}
            if min_credibility is not None:
                query["credibility_score"] = {"$gte": min_credibility}

            cursor = db_manager.db.research_sources.find(query).sort("relevance_score", -1)
            return [Source(**doc) async for doc in cursor]

        # In-memory fallback
        results = [s for s in self._sources.values() if s.research_id == research_id]
        if domain:
            results = [s for s in results if s.domain.lower() == domain.lower().strip()]
        if source_type:
            results = [s for s in results if s.source_type.lower() == source_type.lower().strip()]
        if language:
            results = [s for s in results if s.language.lower() == language.lower().strip()]
        if min_relevance is not None:
            results = [s for s in results if s.relevance_score >= min_relevance]
        if min_credibility is not None:
            results = [s for s in results if s.credibility_score >= min_credibility]

        results.sort(key=lambda x: x.relevance_score, reverse=True)
        return results

    async def find_by_content_hash(self, research_id: str, content_hash: str) -> Optional[Source]:
        """Check if identical content has already been stored for this research session."""
        if db_manager.is_connected:
            doc = await db_manager.db.research_sources.find_one({
                "research_id": research_id,
                "content_hash": content_hash,
            })
            return Source(**doc) if doc else None

        for s in self._sources.values():
            if s.research_id == research_id and s.content_hash == content_hash:
                return s
        return None

    async def delete_source(self, source_id: str) -> bool:
        """Delete a source record by source_id."""
        if db_manager.is_connected:
            res = await db_manager.db.research_sources.delete_one({
                "$or": [{"source_id": source_id}, {"id": source_id}]
            })
            return res.deleted_count > 0

        found_key = None
        for k, s in self._sources.items():
            if s.source_id == source_id or s.id == source_id:
                found_key = k
                break
        if found_key:
            del self._sources[found_key]
            return True
        return False

    async def count_sources(self, research_id: Optional[str] = None) -> int:
        """Count total sources for a research job or overall."""
        if db_manager.is_connected:
            query = {"research_id": research_id} if research_id else {}
            return await db_manager.db.research_sources.count_documents(query)

        if research_id:
            return sum(1 for s in self._sources.values() if s.research_id == research_id)
        return len(self._sources)


source_repo = SourceRepository()
