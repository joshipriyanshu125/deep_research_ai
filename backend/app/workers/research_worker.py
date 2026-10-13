import asyncio
from app.database.models.research import ResearchJob, ResearchStatus
from app.database.repositories.research_repo import research_repo
from app.workers.research_runner import run_research_job
from app.services.notification_service import notification_service
from app.utils.logger import logger


class ResearchWorker:
    # Job states that a worker can own. A process restart orphans them, so
    # they must be re-queued on startup instead of staying stalled forever.
    RECOVERABLE_STATUSES = {
        ResearchStatus.PENDING,
        ResearchStatus.PLANNING,
        ResearchStatus.SEARCHING,
        ResearchStatus.EXTRACTING,
        ResearchStatus.ANALYZING,
        ResearchStatus.SYNTHESIZING,
    }

    def __init__(self):
        self.queue = asyncio.Queue()
        self.is_running = False
        self._active_jobs = set()
        self._running_tasks = {}

    async def enqueue_job(self, job: ResearchJob):
        if job.status == ResearchStatus.CANCELLED:
            return
        if job.id not in self._active_jobs:
            self._active_jobs.add(job.id)
            await self.queue.put(job)
            logger.info(f"Enqueued research job {job.id} to worker queue.")

    async def cancel_job(self, job_id: str):
        """Cancel one queued or running job without stopping the worker loop."""
        job = await research_repo.cancel_job(job_id)
        if not job:
            return None
        if job.status != ResearchStatus.CANCELLED:
            return job
        running_task = self._running_tasks.get(job_id)
        if running_task and not running_task.done():
            running_task.cancel()

        # Wait for the pipeline task to unwind so a late save cannot race a
        # newly started run. The worker's main loop remains alive.
        if running_task and running_task is not asyncio.current_task():
            await asyncio.gather(running_task, return_exceptions=True)
        return job

    async def _process_job(self, job: ResearchJob):
        result = await run_research_job(job)
        if result and result.status == ResearchStatus.COMPLETED:
            await notification_service.notify_research_complete(job.user_id, job.id, job.query)

    async def recover_interrupted_jobs(self) -> int:
        """Re-queue pending jobs and restart jobs orphaned by a restart.

        Only PENDING jobs used to be recovered, which left a run that died
        mid-pipeline (planning/searching/extracting/…) stuck at its last
        status forever — the polling UI then appeared stalled. Every
        non-terminal job is now reset to PENDING and enqueued again.
        """
        try:
            from app.database.mongodb import db_manager
            if not (db_manager.is_connected and db_manager.db is not None):
                return 0

            recovered = 0
            cursor = db_manager.db.research_jobs.find(
                {"status": {"$in": sorted(self.RECOVERABLE_STATUSES)}}
            )
            async for doc in cursor:
                job = ResearchJob(**doc)
                if job.id in self._active_jobs:
                    continue
                if job.status != ResearchStatus.PENDING:
                    job.status = ResearchStatus.PENDING
                    job.progress_percentage = 0
                    job.error_message = None
                    job.completed_at = None
                    job.checkpoint_phase = "pending"
                    job.current_step = "Recovered after a backend restart; re-queued for execution."
                    try:
                        await research_repo.update_job(job)
                    except asyncio.CancelledError:
                        # The job reached a terminal state while we read it.
                        continue
                await self.enqueue_job(job)
                recovered += 1

            if recovered:
                logger.info(f"Recovered {recovered} interrupted research job(s) on startup.")
            return recovered
        except Exception as e:
            logger.warning(f"Could not recover interrupted jobs on startup: {e}")
            return 0

    async def start_worker(self):
        self.is_running = True
        logger.info("Research background worker started.")

        # Recover pending and interrupted jobs from MongoDB on startup
        await self.recover_interrupted_jobs()

        while self.is_running:
            try:
                job: ResearchJob = await self.queue.get()
                logger.info(f"Worker picked up research job {job.id}")
                latest = await research_repo.get_job(job.id)
                if not latest or latest.status in {ResearchStatus.CANCELLED, ResearchStatus.COMPLETED}:
                    self._active_jobs.discard(job.id)
                    self.queue.task_done()
                    continue

                processing_task = asyncio.create_task(self._process_job(latest))
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


research_worker = ResearchWorker()
