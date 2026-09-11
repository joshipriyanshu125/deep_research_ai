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
from app.agents.research_agent import research_agent
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
                    sources = await research_agent.process_task(t, research_id)
                    if on_task_complete:
                        try:
                            cb_res = on_task_complete(t, sources)
                            if asyncio.iscoroutine(cb_res):
                                await cb_res
                        except Exception as cb_err:
                            logger.warning(f"Error in on_task_complete callback: {cb_err}")
                    return sources
                except Exception as task_err:
                    logger.error(f"Unhandled error in task execution '{t.query}': {task_err}")
                    t.status = "failed"
                    t.error_message = str(task_err)
                    return []

        # Execute all tasks in parallel
        task_coros = [_run_bounded_task(t) for t in tasks]
        results = await asyncio.gather(*task_coros, return_exceptions=True)

        # Cross-track source aggregation & deduplication
        all_sources: List[Source] = []
        seen_urls: Set[str] = set()
        seen_hashes: Set[str] = set()

        for res in results:
            if isinstance(res, list):
                for s in res:
                    url_key = (s.url or "").strip().rstrip("/")
                    hash_key = getattr(s, "content_hash", "")
                    if url_key and url_key in seen_urls:
                        continue
                    if hash_key and hash_key in seen_hashes:
                        continue
                    if url_key:
                        seen_urls.add(url_key)
                    if hash_key:
                        seen_hashes.add(hash_key)
                    all_sources.append(s)
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

