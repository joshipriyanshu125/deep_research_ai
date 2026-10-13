import asyncio
from datetime import datetime, timezone
from app.database.models.research import ResearchJob, ResearchStatus
from app.database.repositories.research_repo import research_repo
from app.research.orchestrator import research_orchestrator
from app.services.notification_service import notification_service
from app.utils.logger import logger


class ResearchWorker:
    def __init__(self):
        self.queue = asyncio.Queue()
        self.is_running = False
        self._active_jobs = set()
        self._running_tasks = {}
        self._cancelled_jobs = set()

    async def enqueue_job(self, job: ResearchJob):
        if job.status == ResearchStatus.CANCELLED or job.id in self._cancelled_jobs:
            return
        if job.id not in self._active_jobs:
            self._active_jobs.add(job.id)
            await self.queue.put(job)
            logger.info(f"Enqueued research job {job.id} to worker queue.")

    async def cancel_job(self, job_id: str):
        """Cancel one queued or running job without stopping the worker loop."""
        job = await research_repo.get_job(job_id)
        if not job:
            return None

        if job.status in {ResearchStatus.COMPLETED, ResearchStatus.FAILED}:
            return job
        if job.status == ResearchStatus.CANCELLED:
            return job

        self._cancelled_jobs.add(job_id)
        running_task = self._running_tasks.get(job_id)
        if running_task and not running_task.done():
            running_task.cancel()

        job.status = ResearchStatus.CANCELLED
        job.progress_percentage = 0
        job.current_step = "Research cancelled by user."
        job.error_message = None
        job.checkpoint_phase = "cancelled"
        job.completed_at = datetime.now(timezone.utc)
        job.logs.append({
            "timestamp": datetime.now(timezone.utc),
            "stage": "cancelled",
            "state": ResearchStatus.CANCELLED,
            "message": "Research job was cancelled by user.",
        })
        await research_repo.update_job(job)

        # Wait for the pipeline task to unwind so a late save cannot race a
        # newly started run. The worker's main loop remains alive.
        if running_task and running_task is not asyncio.current_task():
            await asyncio.gather(running_task, return_exceptions=True)
        return job

    async def _process_job(self, job: ResearchJob):
        async for _ in research_orchestrator.run_pipeline_stream(job):
            pass
        if job.status != ResearchStatus.CANCELLED:
            await notification_service.notify_research_complete(job.user_id, job.id, job.query)

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
                if job.status == ResearchStatus.CANCELLED or job.id in self._cancelled_jobs:
                    self._active_jobs.discard(job.id)
                    self.queue.task_done()
                    continue

                processing_task = asyncio.create_task(self._process_job(job))
                self._running_tasks[job.id] = processing_task
                try:
                    await processing_task
                except asyncio.CancelledError:
                    # A cancelled child task is expected. If the worker loop
                    # itself is shutting down, preserve that cancellation.
                    if asyncio.current_task().cancelling():
                        raise
                    logger.info(f"Research job {job.id} cancelled.")
                finally:
                    self._running_tasks.pop(job.id, None)
                    self._active_jobs.discard(job.id)
                    self.queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker encountered error processing job: {e}")
                self.queue.task_done()


research_worker = ResearchWorker()
