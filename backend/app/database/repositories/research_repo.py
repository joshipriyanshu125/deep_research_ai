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
        from app.database.repositories.source_repo import source_repo
        return await source_repo.create_source(source)

    async def get_sources_by_research(
        self,
        research_id: str,
        domain: Optional[str] = None,
        source_type: Optional[str] = None,
        min_relevance: Optional[float] = None,
    ) -> List[Source]:
        from app.database.repositories.source_repo import source_repo
        return await source_repo.get_sources_by_research(
            research_id=research_id,
            domain=domain,
            source_type=source_type,
            min_relevance=min_relevance,
        )

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
