"""
Day 20 — Parallel Research Test Suite
Comprehensive testing for:
  Planner -> Parallel (Web, Papers, Market) -> Synthesis
"""

import time
import asyncio
import pytest
from unittest.mock import AsyncMock, patch
from app.database.models.research import ResearchTask
from app.database.models.source import Source, SourceType
from app.research.executor import ParallelResearchExecutor, research_executor
from app.agents.research_agent import ResearchAgent, research_agent


class TestParallelResearchExecutor:
    @pytest.mark.asyncio
    async def test_parallel_execution_multi_track(self):
        executor = ParallelResearchExecutor(default_max_concurrency=6)

        tasks = [
            ResearchTask(id="t1", query="India EV subsidy policy", category="web"),
            ResearchTask(id="t2", query="Solid-state battery cathode degradation", category="academic"),
            ResearchTask(id="t3", query="Tata Motors EV market share quarterly", category="market"),
        ]

        async def mock_process(task: ResearchTask, res_id: str):
            task.status = "completed"
            task.duration_ms = 10.0
            return [
                Source(
                    source_id=f"src_{task.id}",
                    url=f"https://source-{task.id}.com",
                    title=f"Source for {task.query}",
                    source_type=SourceType.ACADEMIC if task.category == "academic" else SourceType.NEWS,
                )
            ]

        with patch.object(research_agent, "process_task", side_effect=mock_process):
            sources = await executor.execute_tasks(tasks, research_id="res-parallel-1")
            assert len(sources) == 3
            assert all(t.status == "completed" for t in tasks)
            assert executor.last_execution_stats["completed_tasks"] == 3
            assert executor.last_execution_stats["failed_tasks"] == 0

    @pytest.mark.asyncio
    async def test_concurrency_throttling(self):
        executor = ParallelResearchExecutor(default_max_concurrency=2)
        tasks = [ResearchTask(id=f"t_{i}", query=f"Query {i}", category="web") for i in range(6)]

        active_concurrent = 0
        max_seen_concurrent = 0

        async def mock_process(task: ResearchTask, res_id: str):
            nonlocal active_concurrent, max_seen_concurrent
            active_concurrent += 1
            max_seen_concurrent = max(max_seen_concurrent, active_concurrent)
            await asyncio.sleep(0.02)
            active_concurrent -= 1
            task.status = "completed"
            return [Source(source_id=f"s_{task.id}", url=f"https://url-{task.id}.com", title=f"T_{task.id}")]

        with patch.object(research_agent, "process_task", side_effect=mock_process):
            sources = await executor.execute_tasks(tasks, research_id="res-concurrency", max_concurrency=2)
            assert len(sources) == 6
            assert max_seen_concurrent <= 2

    @pytest.mark.asyncio
    async def test_error_isolation_and_partial_failure(self):
        executor = ParallelResearchExecutor()
        t_ok1 = ResearchTask(id="t_ok1", query="Web query 1", category="web")
        t_fail = ResearchTask(id="t_fail", query="Academic query that crashes", category="academic")
        t_ok2 = ResearchTask(id="t_ok2", query="Market query 2", category="market")

        async def mock_process(task: ResearchTask, res_id: str):
            if task.id == "t_fail":
                raise RuntimeError("Network timeout connecting to paper database")
            task.status = "completed"
            return [Source(source_id=f"src_{task.id}", url=f"https://{task.id}.com", title=task.query)]

        with patch.object(research_agent, "process_task", side_effect=mock_process):
            sources = await executor.execute_tasks([t_ok1, t_fail, t_ok2], research_id="res-fail-iso")
            # The 2 successful tasks should yield sources
            assert len(sources) == 2
            assert t_ok1.status == "completed"
            assert t_ok2.status == "completed"
            assert t_fail.status == "failed"
            assert "timeout" in t_fail.error_message.lower()
            assert executor.last_execution_stats["failed_tasks"] == 1
            assert executor.last_execution_stats["completed_tasks"] == 2

    @pytest.mark.asyncio
    async def test_parallel_speedup_over_serial(self):
        executor = ParallelResearchExecutor(default_max_concurrency=4)
        tasks = [ResearchTask(id=f"t_{i}", query=f"Query {i}", category="web") for i in range(4)]

        delay = 0.05  # 50ms per task

        async def mock_process(task: ResearchTask, res_id: str):
            start = time.perf_counter()
            await asyncio.sleep(delay)
            task.status = "completed"
            task.duration_ms = round((time.perf_counter() - start) * 1000, 2)
            return [Source(source_id=f"s_{task.id}", url=f"https://site{task.id}.com", title=f"Title {task.id}")]

        with patch.object(research_agent, "process_task", side_effect=mock_process):
            wall_start = time.perf_counter()
            sources = await executor.execute_tasks(tasks, research_id="res-speedup")
            wall_duration = time.perf_counter() - wall_start

            assert len(sources) == 4
            # 4 tasks * 50ms = 200ms serial, parallel should take roughly ~60-90ms
            assert wall_duration < (delay * 3.5)
            assert executor.last_execution_stats["parallel_speedup_factor"] >= 1.5

    @pytest.mark.asyncio
    async def test_cross_track_source_deduplication(self):
        executor = ParallelResearchExecutor()
        t_web = ResearchTask(id="tw", query="EV news", category="web")
        t_market = ResearchTask(id="tm", query="EV market stats", category="market")

        # Both tracks return the same canonical URL
        shared_url = "https://reuters.com/business/ev-2026"

        async def mock_process(task: ResearchTask, res_id: str):
            task.status = "completed"
            return [
                Source(source_id=f"src_{task.id}_1", url=shared_url, title="Shared Article"),
                Source(source_id=f"src_{task.id}_2", url=f"https://unique-{task.id}.com", title="Unique"),
            ]

        with patch.object(research_agent, "process_task", side_effect=mock_process):
            sources = await executor.execute_tasks([t_web, t_market], research_id="res-dedup")
            urls = [s.url for s in sources]
            # Shared URL should appear only once
            assert urls.count(shared_url) == 1
            assert len(sources) == 3

    @pytest.mark.asyncio
    async def test_execute_tasks_streaming_events(self):
        executor = ParallelResearchExecutor()
        tasks = [
            ResearchTask(id="st1", query="Web Stream 1", category="web"),
            ResearchTask(id="st2", query="Academic Stream 2", category="academic"),
        ]

        async def mock_process(task: ResearchTask, res_id: str):
            task.status = "completed"
            task.duration_ms = 15.0
            return [Source(source_id="s1", url="https://u1.com", title="Title")]

        with patch.object(research_agent, "process_task", side_effect=mock_process):
            events = []
            async for ev in executor.execute_tasks_stream(tasks, research_id="res-stream"):
                events.append(ev)

            assert len(events) == 3
            assert events[0]["event"] == "parallel_execution_started"
            assert events[1]["event"] == "task_finished"
            assert events[2]["event"] == "task_finished"

    @pytest.mark.asyncio
    async def test_execute_parallel_tracks_grouping(self):
        executor = ParallelResearchExecutor()
        web_tasks = [ResearchTask(id="w1", query="Web query", category="web")]
        acad_tasks = [ResearchTask(id="a1", query="Academic query", category="academic")]
        market_tasks = [ResearchTask(id="m1", query="Market query", category="market")]

        async def mock_process(task: ResearchTask, res_id: str):
            task.status = "completed"
            if task.category == "academic":
                st = SourceType.ACADEMIC
            elif task.category == "market":
                st = SourceType.COMPANY
            else:
                st = SourceType.WEB
            return [Source(source_id=f"src_{task.id}", url=f"https://{task.id}.com", title=task.query, source_type=st)]

        with patch.object(research_agent, "process_task", side_effect=mock_process):
            grouped = await executor.execute_parallel_tracks(
                web_tasks=web_tasks,
                academic_tasks=acad_tasks,
                market_tasks=market_tasks,
                research_id="res-tracks",
            )
            assert "web" in grouped
            assert "academic" in grouped
            assert "market" in grouped
            assert len(grouped["academic"]) == 1
            assert len(grouped["market"]) == 1
            assert len(grouped["web"]) == 1


class TestResearchAgentTelemetry:
    @pytest.mark.asyncio
    async def test_task_duration_and_timestamps(self):
        agent = ResearchAgent()
        task = ResearchTask(id="telemetry_task", query="Solid-state battery research", category="academic")

        with patch("app.agents.research_agent.paper_agent.execute") as mock_paper:
            mock_paper.return_value = [
                Source(
                    source_id="src-p1",
                    url="https://arxiv.org/abs/2601.001",
                    title="Solid-State Paper",
                    source_type=SourceType.ACADEMIC,
                )
            ]

            sources = await agent.process_task(task, research_id="res-telemetry")
            assert len(sources) == 1
            assert task.status == "completed"
            assert task.started_at is not None
            assert task.completed_at is not None
            assert task.duration_ms is not None
            assert task.duration_ms >= 0.0
            assert "https://arxiv.org/abs/2601.001" in task.source_urls
