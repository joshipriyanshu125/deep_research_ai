import asyncio
from app.database.models.research import ResearchJob, ResearchStatus
from app.research.orchestrator import research_orchestrator
from app.services.notification_service import notification_service
from app.utils.logger import logger


class ResearchWorker:
    def __init__(self):
        self.queue = asyncio.Queue()
        self.is_running = False

    async def enqueue_job(self, job: ResearchJob):
        await self.queue.put(job)
        logger.info(f"Enqueued research job {job.id} to worker queue.")

    async def start_worker(self):
        self.is_running = True
        logger.info("Research background worker started.")
        while self.is_running:
            try:
                job: ResearchJob = await self.queue.get()
                logger.info(f"Worker picked up research job {job.id}")
                async for _ in research_orchestrator.run_pipeline_stream(job):
                    pass
                await notification_service.notify_research_complete(job.user_id, job.id, job.query)
                self.queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker encountered error processing job: {e}")


research_worker = ResearchWorker()
