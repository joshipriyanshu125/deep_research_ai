from typing import Optional, List, Dict
from app.database.mongodb import db_manager
from app.database.models.research import ResearchJob, ResearchStatus
from app.database.models.source import Source
from app.database.models.evidence import Evidence


class ResearchRepository:
    def __init__(self):
        self._jobs: Dict[str, ResearchJob] = {}
        self._sources: Dict[str, Source] = {}
        self._evidence: Dict[str, Evidence] = {}

    async def create_job(self, job: ResearchJob) -> ResearchJob:
        if db_manager.is_connected:
            await db_manager.db.research_jobs.insert_one(job.model_dump())
        else:
            self._jobs[job.id] = job
        return job

    async def update_job(self, job: ResearchJob) -> ResearchJob:
        if db_manager.is_connected:
            await db_manager.db.research_jobs.replace_one({"id": job.id}, job.model_dump())
        else:
            self._jobs[job.id] = job
        return job

    async def get_job(self, job_id: str) -> Optional[ResearchJob]:
        if db_manager.is_connected:
            doc = await db_manager.db.research_jobs.find_one({"id": job_id})
            return ResearchJob(**doc) if doc else None
        return self._jobs.get(job_id)

    async def list_jobs(self, user_id: Optional[str] = None, limit: int = 50) -> List[ResearchJob]:
        if db_manager.is_connected:
            query = {"user_id": user_id} if user_id else {}
            cursor = db_manager.db.research_jobs.find(query).sort("created_at", -1).limit(limit)
            return [ResearchJob(**doc) async for doc in cursor]
        
        jobs = list(self._jobs.values())
        if user_id:
            jobs = [j for j in jobs if j.user_id == user_id]
        jobs.sort(key=lambda x: x.created_at, reverse=True)
        return jobs[:limit]

    async def add_source(self, source: Source) -> Source:
        if db_manager.is_connected:
            await db_manager.db.sources.insert_one(source.model_dump())
        else:
            self._sources[source.id] = source
        return source

    async def get_sources_by_research(
        self,
        research_id: str,
        domain: Optional[str] = None,
        source_type: Optional[str] = None,
        min_relevance: Optional[float] = None,
    ) -> List[Source]:
        if db_manager.is_connected:
            query: Dict[str, Any] = {"research_id": research_id}
            if domain:
                query["domain"] = domain.lower().strip()
            if source_type:
                query["source_type"] = source_type
            if min_relevance is not None:
                query["relevance_score"] = {"$gte": min_relevance}
            cursor = db_manager.db.sources.find(query)
            return [Source(**doc) async for doc in cursor]
        
        results = [s for s in self._sources.values() if s.research_id == research_id]
        if domain:
            results = [s for s in results if s.domain.lower() == domain.lower().strip()]
        if source_type:
            results = [s for s in results if s.source_type == source_type]
        if min_relevance is not None:
            results = [s for s in results if s.relevance_score >= min_relevance]
        return results

    async def add_evidence(self, evidence: Evidence) -> Evidence:
        if db_manager.is_connected:
            await db_manager.db.evidence.insert_one(evidence.model_dump())
        else:
            self._evidence[evidence.id] = evidence
        return evidence

    async def get_evidence_by_research(self, research_id: str) -> List[Evidence]:
        if db_manager.is_connected:
            cursor = db_manager.db.evidence.find({"research_id": research_id})
            return [Evidence(**doc) async for doc in cursor]
        return [e for e in self._evidence.values() if e.research_id == research_id]


research_repo = ResearchRepository()
