"""
Day 96–100 — Production Deployment: Dedicated Distributed Worker

Distributed background worker process for running deep research jobs.
Can run in standalone worker containers or scaled horizontally (worker-1, worker-2, etc.).

Supports:
- Redis-based queue consumption (`research_jobs_queue`)
- MongoDB pending jobs polling with distributed locking
- Multi-agent pipeline execution via `research_orchestrator`
- Graceful shutdown on SIGTERM / SIGINT
- Real-time Prometheus metrics & health reporting
"""

from __future__ import annotations

import asyncio
import logging
import signal
import sys
import uuid
from typing import Optional

from app.config.settings import settings
from app.database.mongodb import connect_to_mongo, close_mongo_connection, get_database
from app.database.models.research import ResearchJob, ResearchStatus
from app.monitoring.metrics import metrics_collector
from app.research.orchestrator import research_orchestrator
from app.services.notification_service import notification_service
from app.services.redis_service import redis_service

logger = logging.getLogger("distributed_worker")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [Worker] %(message)s"
)

QUEUE_NAME = "research_jobs_queue"


class DistributedResearchWorker:
    """
    Production-ready distributed research agent worker.
    Scales horizontally across container clusters.
    """

    def __init__(self, worker_id: Optional[str] = None) -> None:
        self.worker_id = worker_id or f"worker-{uuid.uuid4().hex[:8]}"
        self.is_running = False
        self._shutdown_event = asyncio.Event()

    async def start(self) -> None:
        """Start worker loop and register signal handlers."""
        self.is_running = True
        logger.info(f"Starting Distributed Research Worker [{self.worker_id}]...")

        # Initialize resources
        await connect_to_mongo()
        await redis_service.connect()

        logger.info(f"Distributed Research Worker [{self.worker_id}] is ready and listening for tasks.")

        # Main processing loop
        while self.is_running:
            try:
                # 1. Try dequeueing from Redis / in-memory queue
                job_payload = await redis_service.dequeue(QUEUE_NAME, timeout=int(settings.WORKER_POLL_INTERVAL_SECONDS))
                
                if job_payload:
                    job_id = job_payload.get("job_id") or job_payload.get("id")
                    if job_id:
                        await self._process_job_by_id(job_id)
                else:
                    # 2. Fallback: check MongoDB for any unassigned pending jobs
                    await self._poll_pending_db_jobs()
                    await asyncio.sleep(settings.WORKER_POLL_INTERVAL_SECONDS)

            except asyncio.CancelledError:
                logger.info(f"Worker [{self.worker_id}] received cancellation request.")
                break
            except Exception as e:
                logger.error(f"Worker [{self.worker_id}] loop error: {e}", exc_info=True)
                metrics_collector.record_worker_failure()
                await asyncio.sleep(2.0)

        await self.cleanup()

    async def _poll_pending_db_jobs(self) -> None:
        """Poll MongoDB for pending jobs and attempt distributed lock."""
        db = get_database()
        if db is None:
            return

        try:
            # Find the oldest pending job
            doc = await db.research_jobs.find_one(
                {"status": ResearchStatus.PENDING},
                sort=[("created_at", 1)]
            )
            if doc:
                job_id = str(doc.get("id") or doc.get("_id"))
                await self._process_job_by_id(job_id)
        except Exception as e:
            logger.debug(f"DB poll error (harmless if testing): {e}")

    async def _process_job_by_id(self, job_id: str) -> None:
        """Process a specific research job with distributed lock."""
        lock_token = f"{self.worker_id}-{uuid.uuid4().hex[:6]}"
        lock_acquired = await redis_service.acquire_lock(
            lock_name=f"job:{job_id}",
            token=lock_token,
            expire_seconds=settings.WORKER_JOB_TIMEOUT_SECONDS
        )

        if not lock_acquired:
            logger.debug(f"Job {job_id} is already locked by another worker.")
            return

        try:
            db = get_database()
            if db is None:
                logger.error("MongoDB not connected during job execution.")
                return

            doc = await db.research_jobs.find_one({"id": job_id})
            if not doc:
                doc = await db.research_jobs.find_one({"_id": job_id})
            if not doc:
                logger.warning(f"Job {job_id} not found in database.")
                return

            if doc.get("status") not in (ResearchStatus.PENDING, "pending"):
                return

            # Construct ResearchJob model
            job = ResearchJob(**doc)
            logger.info(f"Worker [{self.worker_id}] executing Research Job: {job.id} ('{job.query[:40]}...')")

            # Execute pipeline
            start_time = asyncio.get_event_loop().time()
            async for _ in research_orchestrator.run_pipeline_stream(job):
                pass
            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000

            metrics_collector.record_research_completed(duration_ms)
            await notification_service.notify_research_complete(job.user_id, job.id, job.query)
            logger.info(f"Worker [{self.worker_id}] completed Job: {job.id} in {duration_ms:.1f}ms")

        except Exception as e:
            logger.error(f"Worker [{self.worker_id}] failed processing job {job_id}: {e}", exc_info=True)
            metrics_collector.record_worker_failure()
        finally:
            await redis_service.release_lock(f"job:{job_id}", lock_token)

    async def stop(self) -> None:
        """Signal graceful shutdown."""
        logger.info(f"Worker [{self.worker_id}] shutting down...")
        self.is_running = False
        self._shutdown_event.set()

    async def cleanup(self) -> None:
        """Clean up connections."""
        await redis_service.disconnect()
        await close_mongo_connection()
        logger.info(f"Worker [{self.worker_id}] cleanly stopped.")


# Standalone CLI entrypoint
async def main() -> None:
    worker = DistributedResearchWorker()
    loop = asyncio.get_running_loop()

    # Handle OS termination signals
    if sys.platform != "win32":
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, lambda: asyncio.create_task(worker.stop()))

    try:
        await worker.start()
    except (KeyboardInterrupt, SystemExit):
        await worker.stop()


if __name__ == "__main__":
    asyncio.run(main())
