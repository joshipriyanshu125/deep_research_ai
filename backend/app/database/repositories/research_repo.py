from typing import Optional, List, Dict
import asyncio
from pymongo import ReturnDocument
from app.utils.helpers import get_utc_now
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
            self._jobs[job.id] = job.model_copy(deep=True)
        return job

    async def update_job(self, job: ResearchJob) -> ResearchJob:
        if db_manager.is_connected:
            result = await db_manager.db.research_jobs.replace_one(
                {"id": job.id, "status": {"$nin": [ResearchStatus.CANCELLED, ResearchStatus.COMPLETED]}},
                job.model_dump(),
            )
            if not result.matched_count:
                raise asyncio.CancelledError("Research is no longer writable")
        else:
            current = self._jobs.get(job.id)
            if current and current.status in {ResearchStatus.CANCELLED, ResearchStatus.COMPLETED}:
                raise asyncio.CancelledError("Research is no longer writable")
            self._jobs[job.id] = job.model_copy(deep=True)
        return job

    async def delete_job(self, job_id: str) -> bool:
        if db_manager.is_connected:
            res = await db_manager.db.research_jobs.delete_one({"id": job_id})
            # Clean up child artifacts
            try:
                await db_manager.db.reports.delete_many({"research_id": job_id})
                await db_manager.db.research_tasks.delete_many({"research_id": job_id})
                await db_manager.db.research_sources.delete_many({"research_id": job_id})
                await db_manager.db.evidence.delete_many({"research_id": job_id})
            except Exception:
                pass
            return res.deleted_count > 0
        deleted = job_id in self._jobs
        self._jobs.pop(job_id, None)
        return deleted

    async def cancel_job(self, job_id: str) -> Optional[ResearchJob]:
        """Stop wins atomically over any subsequent worker checkpoint write."""
        now = get_utc_now()
        updates = {
            "status": ResearchStatus.CANCELLED,
            "current_step": "Research stopped by user.",
            "checkpoint_phase": "cancelled",
            "completed_at": now,
            "error_message": None,
        }
        terminal = [ResearchStatus.CANCELLED, ResearchStatus.COMPLETED, ResearchStatus.FAILED]
        if db_manager.is_connected:
            doc = await db_manager.db.research_jobs.find_one_and_update(
                {"id": job_id, "status": {"$nin": terminal}},
                {"$set": updates}, return_document=ReturnDocument.AFTER,
            )
            return ResearchJob(**doc) if doc else await self.get_job(job_id)
        job = self._jobs.get(job_id)
        if job and job.status not in terminal:
            job = job.model_copy(update=updates, deep=True)
            for task in job.tasks:
                if task.status not in {"completed", "failed"}:
                    task.status = "cancelled"
            self._jobs[job_id] = job
        return job.model_copy(deep=True) if job else None

    async def get_job(self, job_id: str) -> Optional[ResearchJob]:
        if db_manager.is_connected:
            doc = await db_manager.db.research_jobs.find_one({"id": job_id})
            return ResearchJob(**doc) if doc else None
        job = self._jobs.get(job_id)
        return job.model_copy(deep=True) if job else None

    async def list_jobs(self, user_id: Optional[str] = None, limit: int = 50) -> List[ResearchJob]:
        if db_manager.is_connected:
            query = {"user_id": user_id} if user_id else {}
            cursor = db_manager.db.research_jobs.find(query).sort("created_at", -1).limit(limit)
            return [ResearchJob(**doc) async for doc in cursor]
        
        jobs = list(self._jobs.values())
        if user_id:
            jobs = [j for j in jobs if j.user_id == user_id]
        jobs.sort(key=lambda x: x.created_at, reverse=True)
        return [job.model_copy(deep=True) for job in jobs[:limit]]

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
        from app.database.repositories.evidence_repo import evidence_repo
        return await evidence_repo.create_evidence(evidence)

    async def get_evidence_by_research(
        self,
        research_id: str,
        source_id: Optional[str] = None,
        verification_status: Optional[str] = None,
        min_confidence: Optional[float] = None,
    ) -> List[Evidence]:
        from app.database.repositories.evidence_repo import evidence_repo
        return await evidence_repo.get_evidence_by_research(
            research_id=research_id,
            source_id=source_id,
            verification_status=verification_status,
            min_confidence=min_confidence,
        )

    async def update_evidence(self, evidence: Evidence) -> Evidence:
        from app.database.repositories.evidence_repo import evidence_repo
        return await evidence_repo.update_evidence(evidence)


research_repo = ResearchRepository()

