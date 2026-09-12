"""
Day 20 — Autonomous Parallel Research Executor

Core Architecture:
                 Planner
                    ↓
        ┌───────────┼───────────┐
        ↓           ↓           ↓
      Web         Papers      Market
        ↓           ↓           ↓
        └───────────┼───────────┘
                    ↓
                Synthesis

Executes independent research exploration tasks simultaneously with bounded concurrency,
cross-track source deduplication, streaming lifecycle events, and speedup telemetry.
"""

import time
import asyncio
from typing import List, Dict, Any, Optional, Set, AsyncGenerator, Callable
from app.database.models.research import ResearchTask
from app.database.models.source import Source
from app.database.models.source import normalize_url, normalized_content_hash, content_similarity
from app.agents.research_agent import research_agent
from app.research.events import TASK_STARTED, TASK_COMPLETED, SEARCH_COMPLETED, SOURCE_FOUND, research_event_bus
from app.utils.logger import logger


class ParallelResearchExecutor:
    """
    Autonomous parallel research execution coordinator.
    Dispatches sub-tasks across Web, Academic/Papers, and Market channels concurrently.
    """

    def __init__(self, default_max_concurrency: int = 8):
        self.default_max_concurrency = default_max_concurrency
        self.last_execution_stats: Dict[str, Any] = {}

    async def execute_tasks(
        self,
        tasks: List[ResearchTask],
        research_id: str,
        max_concurrency: Optional[int] = None,
        on_task_complete: Optional[Callable[[ResearchTask, List[Source]], Any]] = None,
    ) -> List[Source]:
        """
        Execute research tasks concurrently across all categories (Web, Papers, Market).
        Deduplicates sources across parallel tracks and logs speedup metrics.
        """
        if not tasks:
            return []
        # Completed task records are durable checkpoints and need not be rerun
        # when a worker resumes a failed job.
        tasks = [task for task in tasks if task.status != "completed"]
        if not tasks:
            return []

        concurrency = max_concurrency or self.default_max_concurrency
        semaphore = asyncio.Semaphore(concurrency)
        start_wall_time = time.perf_counter()

        logger.info(
            f"ParallelResearchExecutor launching {len(tasks)} tasks "
            f"(Web: {sum(1 for t in tasks if t.category == 'web')}, "
            f"Papers: {sum(1 for t in tasks if t.category == 'academic')}, "
            f"Market: {sum(1 for t in tasks if t.category == 'market')}) "
            f"with concurrency limit = {concurrency}."
        )

        async def _run_bounded_task(t: ResearchTask) -> List[Source]:
            async with semaphore:
                try:
                    research_event_bus.emit(
                        TASK_STARTED,
                        job_id=research_id,
                        message=f"Starting task: {t.query}",
                        data={"task_id": t.id, "task": t.model_dump(mode="json")},
                    )
                    sources = await research_agent.process_task(t, research_id)
                    if on_task_complete:
                        try:
                            cb_res = on_task_complete(t, sources)
                            if asyncio.iscoroutine(cb_res):
                                await cb_res
                        except Exception as cb_err:
                            logger.warning(f"Error in on_task_complete callback: {cb_err}")
                    research_event_bus.emit(
                        TASK_COMPLETED,
                        job_id=research_id,
                        message=f"Task completed: {t.query}",
                        data={"task_id": t.id, "task": t.model_dump(mode="json"), "source_count": len(sources)},
                    )
                    return sources
                except Exception as task_err:
                    logger.error(f"Unhandled error in task execution '{t.query}': {task_err}")
                    t.status = "failed"
                    t.error_message = str(task_err)
                    research_event_bus.emit(
                        TASK_COMPLETED,
                        job_id=research_id,
                        message=f"Task failed: {t.query}",
                        data={"task_id": t.id, "task": t.model_dump(mode="json"), "error": str(task_err)},
                    )
                    return []

        # Execute all tasks in parallel
        task_coros = [_run_bounded_task(t) for t in tasks]
        results = await asyncio.gather(*task_coros, return_exceptions=True)

        # Cross-track source aggregation & deduplication
        all_sources: List[Source] = []
        seen_urls: Set[str] = set()
        seen_hashes: Set[str] = set()
        unique_sources: List[Source] = []

        for res in results:
            if isinstance(res, list):
                for s in res:
                    s.url = normalize_url(s.url)
                    if not s.content_hash:
                        s.content_hash = normalized_content_hash(s.content)
                    url_key = s.url
                    hash_key = getattr(s, "content_hash", "")
                    if url_key and url_key in seen_urls:
                        continue
                    if hash_key and hash_key in seen_hashes:
                        continue
                    if any(len(existing.content.strip()) >= 40 and len(s.content.strip()) >= 40 and content_similarity(existing.content, s.content) >= 0.92
                           for existing in unique_sources if existing.content and s.content):
                        continue
                    if url_key:
                        seen_urls.add(url_key)
                    if hash_key:
                        seen_hashes.add(hash_key)
                    all_sources.append(s)
                    unique_sources.append(s)
                    research_event_bus.emit(
                        SOURCE_FOUND,
                        job_id=research_id,
                        message=f"Found source: {s.title or s.url or 'new source'}",
                        data={"source": s.model_dump(mode="json") if hasattr(s, "model_dump") else s.__dict__},
                    )
            elif isinstance(res, Exception):
                logger.error(f"Task exception in parallel gather: {res}")

        # Compute speedup & execution telemetry
        total_wall_ms = round((time.perf_counter() - start_wall_time) * 1000, 2)
        sum_task_ms = sum(t.duration_ms or 0 for t in tasks)
        speedup = round(sum_task_ms / max(1.0, total_wall_ms), 2) if total_wall_ms > 0 else 1.0

        self.last_execution_stats = {
            "total_tasks": len(tasks),
            "completed_tasks": sum(1 for t in tasks if t.status == "completed"),
            "failed_tasks": sum(1 for t in tasks if t.status == "failed"),
            "total_sources_gathered": len(all_sources),
            "wall_time_ms": total_wall_ms,
            "sequential_time_estimate_ms": sum_task_ms,
            "parallel_speedup_factor": speedup,
            "categories": {
                "web": sum(1 for t in tasks if t.category == "web"),
                "academic": sum(1 for t in tasks if t.category == "academic"),
                "market": sum(1 for t in tasks if t.category == "market"),
            }
        }

        logger.info(
            f"Parallel execution completed in {total_wall_ms:.1f}ms "
            f"(sequential estimate: {sum_task_ms:.1f}ms, parallel speedup: {speedup}x). "
            f"Gathered {len(all_sources)} unique sources."
        )
        research_event_bus.emit(
            SEARCH_COMPLETED,
            job_id=research_id,
            message=f"Found {len(all_sources)} sources.",
            data={"source_count": len(all_sources), "execution_stats": self.last_execution_stats},
        )

        return all_sources

    async def execute_tasks_stream(
        self,
        tasks: List[ResearchTask],
        research_id: str,
        max_concurrency: Optional[int] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Execute tasks in parallel and yield streaming lifecycle events as tasks complete.
        """
        if not tasks:
            return

        concurrency = max_concurrency or self.default_max_concurrency
        semaphore = asyncio.Semaphore(concurrency)
        yield {
            "event": "parallel_execution_started",
            "data": {
                "total_tasks": len(tasks),
                "concurrency": concurrency,
                "categories": [t.category for t in tasks],
            }
        }

        async def _run_task(t: ResearchTask):
            async with semaphore:
                sources = await research_agent.process_task(t, research_id)
                return t, sources

        pending = [asyncio.create_task(_run_task(t)) for t in tasks]

        for future in asyncio.as_completed(pending):
            task_obj, sources = await future
            yield {
                "event": "task_finished",
                "data": {
                    "task_id": task_obj.id,
                    "query": task_obj.query,
                    "category": task_obj.category,
                    "status": task_obj.status,
                    "sources_count": len(sources),
                    "duration_ms": task_obj.duration_ms,
                }
            }

    async def execute_parallel_tracks(
        self,
        web_tasks: List[ResearchTask],
        academic_tasks: List[ResearchTask],
        market_tasks: List[ResearchTask],
        research_id: str,
    ) -> Dict[str, List[Source]]:
        """
        Execute distinct Web, Academic, and Market tracks simultaneously.
        """
        all_tasks = web_tasks + academic_tasks + market_tasks
        sources = await self.execute_tasks(all_tasks, research_id)

        by_track: Dict[str, List[Source]] = {
            "web": [s for s in sources if s.source_type not in ("academic", "company", "financial")],
            "academic": [s for s in sources if s.source_type == "academic"],
            "market": [s for s in sources if s.source_type in ("company", "financial", "news")],
        }
        return by_track


# Export alias and singleton
ResearchExecutor = ParallelResearchExecutor
research_executor = ParallelResearchExecutor()
