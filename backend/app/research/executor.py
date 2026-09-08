import asyncio
from typing import List
from app.database.models.research import ResearchTask
from app.database.models.source import Source
from app.agents.research_agent import research_agent
from app.utils.logger import logger


class ResearchExecutor:
    async def execute_tasks(self, tasks: List[ResearchTask], research_id: str) -> List[Source]:
        # Execute sub-tasks concurrently with bounded concurrency
        coros = [research_agent.process_task(t, research_id) for t in tasks]
        results = await asyncio.gather(*coros, return_exceptions=True)
        
        all_sources = []
        for res in results:
            if isinstance(res, list):
                all_sources.extend(res)
            elif isinstance(res, Exception):
                logger.error(f"Executor encountered task exception: {res}")
                
        return all_sources


research_executor = ResearchExecutor()
