from typing import Optional, List, AsyncGenerator, Dict, Any
from fastapi import HTTPException
from app.database.models.research import ResearchJob, ResearchRequest, ResearchStatus
from app.database.repositories.research_repo import research_repo
from app.research.orchestrator import research_orchestrator
# Day 91–95 — Advanced Research Modes
from app.research.research_modes import get_mode_config


class ResearchService:
    async def create_research_job(self, request: ResearchRequest, user_id: str = "anonymous") -> ResearchJob:
        # Day 91–95: resolve mode config and use its defaults when the caller
        # did not explicitly provide depth / breadth / categories.
        mode_cfg = get_mode_config(request.research_mode)
        depth      = request.depth      if request.depth      is not None else mode_cfg.depth
        breadth    = request.breadth    if request.breadth    is not None else mode_cfg.breadth
        categories = request.categories if request.categories is not None else mode_cfg.categories

        job = ResearchJob(
            user_id=user_id,
            query=request.query,
            depth=depth,
            breadth=breadth,
            categories=categories,
            status=ResearchStatus.PENDING,
            research_mode=request.research_mode or "standard",
        )
        await research_repo.create_job(job)
        from app.workers.research_worker import research_worker
        await research_worker.enqueue_job(job)
        return job

    async def create_follow_up(self, parent: ResearchJob, query: str) -> ResearchJob:
        job = ResearchJob(
            user_id=parent.user_id, query=query, depth=parent.depth, breadth=parent.breadth,
            categories=parent.categories, parent_research_id=parent.id,
            research_mode=parent.research_mode,
            checkpoint_data={"previous_plan": [t.model_dump(mode="json") for t in parent.tasks],
                             "source_ids": parent.source_ids, "evidence_ids": parent.evidence_ids,
                             "report_id": parent.report_id})
        await research_repo.create_job(job)
        from app.workers.research_worker import research_worker
        await research_worker.enqueue_job(job)
        return job

    async def resume_research(self, job: ResearchJob) -> ResearchJob:
        if job.status != ResearchStatus.FAILED:
            raise HTTPException(status_code=422, detail="Only failed research jobs can be resumed")
        job.status = ResearchStatus.PENDING
        job.error_message = None
        job.completed_at = None
        await research_repo.update_job(job)
        from app.workers.research_worker import research_worker
        await research_worker.enqueue_job(job)
        return job

    async def get_job_status(self, job_id: str) -> ResearchJob:
        job = await research_repo.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Research job not found")
        return job

    async def list_user_jobs(self, user_id: str, limit: int = 50) -> List[ResearchJob]:
        return await research_repo.list_jobs(user_id=user_id, limit=limit)

    async def stream_research_progress(self, job_id: str) -> AsyncGenerator[Dict[str, Any], None]:
        job = await self.get_job_status(job_id)
        async for event in research_orchestrator.run_pipeline_stream(job):
            yield event


research_service = ResearchService()

