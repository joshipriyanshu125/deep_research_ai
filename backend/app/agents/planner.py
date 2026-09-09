import json
from typing import List
from app.llm.service import LLMService, get_llm_service
from app.llm.prompts import PLANNER_SYSTEM_PROMPT
from app.database.models.research import ResearchTask
from app.utils.logger import logger


class PlannerAgent:
    def __init__(self, provider_type: str = None):
        self.llm = get_llm_service()

    async def plan_research_tasks(self, query: str, depth: int = 2, breadth: int = 3) -> List[ResearchTask]:
        prompt = (
            f"Generate a research task decomposition for query: '{query}'.\n"
            f"Depth level: {depth}. Number of sub-tasks: {breadth}.\n"
            "Return JSON array with objects containing 'query' and 'category' ('web', 'academic', or 'market')."
        )
        
        try:
            raw_json = await self.llm.generate_json(prompt, system_prompt=PLANNER_SYSTEM_PROMPT)
            parsed = json.loads(raw_json)
            tasks = []
            for item in parsed:
                tasks.append(
                    ResearchTask(
                        query=item.get("query", query),
                        category=item.get("category", "web"),
                        depth=1
                    )
                )
            if tasks:
                return tasks
        except Exception as e:
            logger.warning(f"Planner Agent fallback: {e}")

        # Fallback multi-track planning
        return [
            ResearchTask(query=f"Overview and technological fundamentals of {query}", category="web", depth=1),
            ResearchTask(query=f"Empirical benchmarks, theoretical papers, and studies on {query}", category="academic", depth=1),
            ResearchTask(query=f"Market landscape, adoption figures, and enterprise outlook for {query}", category="market", depth=1)
        ]


planner_agent = PlannerAgent()
