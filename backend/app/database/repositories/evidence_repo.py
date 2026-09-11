"""
Day 18 — Evidence Repository
Repository managing the `evidence` collection in MongoDB with in-memory fallback,
multi-criteria querying, batch insertions, and filtering.
"""

from typing import Optional, List, Dict, Any
from app.database.mongodb import db_manager
from app.database.models.evidence import Evidence


class EvidenceRepository:
    """
    CRUD repository for atomic research evidence, managing storage in the `evidence` collection.
    """

    def __init__(self):
        self._evidence: Dict[str, Evidence] = {}

    async def create_evidence(self, evidence: Evidence) -> Evidence:
        """Insert single evidence record."""
        if db_manager.is_connected:
            await db_manager.db.evidence.insert_one(evidence.model_dump())
        else:
            self._evidence[evidence.id] = evidence
        return evidence

    async def create_evidence_batch(self, evidence_list: List[Evidence]) -> List[Evidence]:
        """Insert multiple evidence records efficiently."""
        if not evidence_list:
            return []
        if db_manager.is_connected:
            docs = [e.model_dump() for e in evidence_list]
            await db_manager.db.evidence.insert_many(docs)
        else:
            for e in evidence_list:
                self._evidence[e.id] = e
        return evidence_list

    async def get_evidence(self, evidence_id: str) -> Optional[Evidence]:
        """Fetch single evidence item by id."""
        if db_manager.is_connected:
            doc = await db_manager.db.evidence.find_one({"id": evidence_id})
            return Evidence(**doc) if doc else None
        return self._evidence.get(evidence_id)

    async def get_evidence_by_research(
        self,
        research_id: str,
        source_id: Optional[str] = None,
        verification_status: Optional[str] = None,
        min_confidence: Optional[float] = None,
        evidence_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[Evidence]:
        """Query evidence items for a research job with multi-criteria filters."""
        if db_manager.is_connected:
            query: Dict[str, Any] = {"research_id": research_id}
            if source_id:
                query["source_id"] = source_id
            if verification_status:
                query["verification_status"] = verification_status
            if evidence_type:
                query["evidence_type"] = evidence_type
            if min_confidence is not None:
                query["confidence"] = {"$gte": min_confidence}

            cursor = db_manager.db.evidence.find(query).limit(limit)
            return [Evidence(**doc) async for doc in cursor]

        results = [e for e in self._evidence.values() if e.research_id == research_id]
        if source_id:
            results = [e for e in results if e.source_id == source_id]
        if verification_status:
            results = [e for e in results if e.verification_status == verification_status]
        if evidence_type:
            results = [e for e in results if e.evidence_type == evidence_type]
        if min_confidence is not None:
            results = [e for e in results if e.confidence >= min_confidence]
        return results[:limit]

    async def get_evidence_by_source(self, source_id: str) -> List[Evidence]:
        """Fetch all evidence extracted from a specific source."""
        if db_manager.is_connected:
            cursor = db_manager.db.evidence.find({"source_id": source_id})
            return [Evidence(**doc) async for doc in cursor]
        return [e for e in self._evidence.values() if e.source_id == source_id]

    async def delete_evidence(self, evidence_id: str) -> bool:
        """Delete single evidence record by id."""
        if db_manager.is_connected:
            result = await db_manager.db.evidence.delete_one({"id": evidence_id})
            return result.deleted_count > 0
        if evidence_id in self._evidence:
            del self._evidence[evidence_id]
            return True
        return False

    async def delete_by_research(self, research_id: str) -> int:
        """Delete all evidence records linked to a research job."""
        if db_manager.is_connected:
            result = await db_manager.db.evidence.delete_many({"research_id": research_id})
            return result.deleted_count
        keys_to_del = [k for k, v in self._evidence.items() if v.research_id == research_id]
        for k in keys_to_del:
            del self._evidence[k]
        return len(keys_to_del)


# Global singleton instance
evidence_repo = EvidenceRepository()
