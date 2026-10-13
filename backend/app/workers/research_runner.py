"""One bounded, cancellable runner shared by local and distributed workers."""
import asyncio

from app.config.settings import settings
from app.database.models.research import ResearchStatus
from app.database.repositories.research_repo import research_repo
from app.research.orchestrator import research_orchestrator
from app.utils.helpers import get_utc_now

CANCELLATION_POLL_SECONDS = 0.5


async def run_research_job(job):
    latest = await research_repo.get_job(job.id)
    if not latest or latest.status in {ResearchStatus.CANCELLED, ResearchStatus.COMPLETED}:
        return latest

    async def consume():
        async for _ in research_orchestrator.run_pipeline_stream(latest):
            pass

    pipeline = asyncio.create_task(consume())
    deadline = asyncio.get_running_loop().time() + settings.RESEARCH_TIMEOUT_SECONDS
    try:
        while not pipeline.done():
            await asyncio.wait({pipeline}, timeout=CANCELLATION_POLL_SECONDS)
            if pipeline.done():
                break
            current = await research_repo.get_job(job.id)
            if not current or current.status == ResearchStatus.CANCELLED:
                pipeline.cancel()
                await asyncio.gather(pipeline, return_exceptions=True)
                return current
            if asyncio.get_running_loop().time() >= deadline:
                pipeline.cancel()
                await asyncio.gather(pipeline, return_exceptions=True)
                current = await research_repo.get_job(job.id)
                if current and current.status not in {ResearchStatus.CANCELLED, ResearchStatus.COMPLETED}:
                    current.status = ResearchStatus.FAILED
                    current.error_message = "Research timed out. Try a narrower query or a smaller research depth."
                    current.current_step = current.error_message
                    current.completed_at = get_utc_now()
                    await research_repo.update_job(current)
                return current
        try:
            await pipeline
        except asyncio.CancelledError:
            # A checkpoint may detect a remotely cancelled run before this
            # loop's next poll. Do not cancel the whole worker in that case.
            if asyncio.current_task().cancelling():
                raise
        return await research_repo.get_job(job.id)
    finally:
        if not pipeline.done():
            pipeline.cancel()
        await asyncio.gather(pipeline, return_exceptions=True)
