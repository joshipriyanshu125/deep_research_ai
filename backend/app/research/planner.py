from typing import List, Optional
from app.agents.planner import planner_agent
from app.database.models.research import ResearchTask, ResearchPlan


class ResearchPlanner:
    async def create_plan(
        self,
        query: str,
        depth: int = 2,
        breadth: int = 3,
        categories: Optional[List[str]] = None,
    ) -> List[ResearchTask]:
        return await planner_agent.plan_research_tasks(
            query,
            depth=depth,
            breadth=breadth,
            categories=categories,
        )

    async def create_research_plan(
        self,
        query: str,
        depth: int = 2,
        breadth: int = 3,
        categories: Optional[List[str]] = None,
    ) -> ResearchPlan:
        return await planner_agent.create_plan(
            query,
            depth=depth,
            breadth=breadth,
            categories=categories,
        )


research_planner = ResearchPlanner()
