from typing import List
from app.agents.planner import planner_agent
from app.database.models.research import ResearchTask, ResearchPlan


class ResearchPlanner:
    async def create_plan(self, query: str, depth: int = 2, breadth: int = 3) -> List[ResearchTask]:
        return await planner_agent.plan_research_tasks(query, depth=depth, breadth=breadth)

    async def create_research_plan(self, query: str, depth: int = 2, breadth: int = 3) -> ResearchPlan:
        return await planner_agent.create_plan(query, depth=depth, breadth=breadth)


research_planner = ResearchPlanner()
