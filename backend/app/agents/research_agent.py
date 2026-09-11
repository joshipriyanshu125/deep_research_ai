import time
import asyncio
from datetime import datetime, timezone
from typing import List
from app.database.models.source import Source
from app.database.models.research import ResearchTask
from app.agents.web_agent import web_agent
from app.agents.paper_agent import paper_agent
from app.utils.logger import logger
from app.utils.helpers import get_utc_now


class ResearchAgent:
    """
    Autonomous task worker that executes research sub-tasks across
    specialized channels (Web, Academic, Market) with execution metrics and error isolation.
    """

    async def process_task(self, task: ResearchTask, research_id: str) -> List[Source]:
        task.status = "in_progress"
        task.started_at = get_utc_now()
        start_t = time.perf_counter()
        logger.info(f"Processing research sub-task [{task.category}]: {task.query}")
        
        try:
            if task.category == "academic":
                sources = await paper_agent.execute(task.query, research_id)
            elif task.category == "market":
                sources = await web_agent.execute(task.query, research_id, is_market=True, category="market")
            else:
                sources = await web_agent.execute(task.query, research_id, is_market=False, category="web")

            task.status = "completed"
            task.results_count = len(sources)
            task.completed_at = get_utc_now()
            task.duration_ms = round((time.perf_counter() - start_t) * 1000, 2)
            task.source_urls = [s.url for s in sources if s.url]
            return sources
        except Exception as e:
            logger.error(f"Task failed [{task.category}] '{task.query}': {e}")
            task.status = "failed"
            task.error_message = str(e)
            task.completed_at = get_utc_now()
            task.duration_ms = round((time.perf_counter() - start_t) * 1000, 2)
            return []


research_agent = ResearchAgent()

