import asyncio
from typing import List
from app.database.models.source import Source
from app.database.models.research import ResearchTask
from app.agents.web_agent import web_agent
from app.agents.paper_agent import paper_agent
from app.utils.logger import logger


class ResearchAgent:
    async def process_task(self, task: ResearchTask, research_id: str) -> List[Source]:
        task.status = "in_progress"
        logger.info(f"Processing research sub-task [{task.category}]: {task.query}")
        
        try:
            if task.category == "academic":
                sources = await paper_agent.execute(task.query, research_id)
            elif task.category == "market":
                sources = await web_agent.execute(task.query, research_id, is_market=True)
            else:
                sources = await web_agent.execute(task.query, research_id, is_market=False)

            task.status = "completed"
            task.results_count = len(sources)
            return sources
        except Exception as e:
            logger.error(f"Task failed {task.query}: {e}")
            task.status = "failed"
            return []


research_agent = ResearchAgent()
