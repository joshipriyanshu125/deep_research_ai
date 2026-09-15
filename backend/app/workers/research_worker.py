import asyncio
from app.database.models.research import ResearchJob, ResearchStatus
from app.research.orchestrator import research_orchestrator
from app.services.notification_service import notification_service
from app.utils.logger import logger


class ResearchWorker:
    def __init__(self):
        self.queue = asyncio.Queue()
        self.is_running = False
        self._active_jobs = set()

    async def enqueue_job(self, job: ResearchJob):
        if job.id not in self._active_jobs:
            self._active_jobs.add(job.id)
            await self.queue.put(job)
            logger.info(f"Enqueued research job {job.id} to worker queue.")

    async def start_worker(self):
        self.is_running = True
        logger.info("Research background worker started.")

        # Recover any pending jobs from MongoDB on startup
        try:
            from app.database.mongodb import db_manager
            if db_manager.is_connected and db_manager.db is not None:
                cursor = db_manager.db.research_jobs.find({"status": ResearchStatus.PENDING})
                async for doc in cursor:
                    job = ResearchJob(**doc)
                    await self.enqueue_job(job)
                    logger.info(f"Recovered pending research job {job.id} on startup.")
        except Exception as e:
            logger.warning(f"Could not recover pending jobs on startup: {e}")

        while self.is_running:
            try:
                job: ResearchJob = await self.queue.get()
                logger.info(f"Worker picked up research job {job.id}")
                try:
                    async for _ in research_orchestrator.run_pipeline_stream(job):
                        pass
                    await notification_service.notify_research_complete(job.user_id, job.id, job.query)
                finally:
                    self._active_jobs.discard(job.id)
                    self.queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker encountered error processing job: {e}")
                self.queue.task_done()


research_worker = ResearchWorker()
