from typing import List
from app.agents.planner import planner_agent
from app.database.models.research import ResearchTask


class ResearchPlanner:
    async def create_plan(self, query: str, depth: int = 2, breadth: int = 3) -> List[ResearchTask]:
        return await planner_agent.plan_research_tasks(query, depth=depth, breadth=breadth)


research_planner = ResearchPlanner()
