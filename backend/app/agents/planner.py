import json
from typing import List, Dict, Any, Optional, Union
from app.llm.service import LLMService, get_llm_service
from app.llm.prompts import planner_prompt, PLANNER_SYSTEM_PROMPT
from app.database.models.research import ResearchTask, ResearchPlan
from app.utils.logger import logger


class PlannerAgent:
    """Agentic planner that decomposes complex research topics into structured investigation plans."""

    def __init__(self, provider_type: Optional[str] = None):
        self.llm = get_llm_service()

    async def create_plan(
        self,
        query: str,
        depth: int = 2,
        breadth: int = 3
    ) -> ResearchPlan:
        """Analyze research objective and produce a structured ResearchPlan with atomic tasks."""
        try:
            raw_json = await self.llm.execute_prompt(
                planner_prompt,
                variables={"query": query, "depth": depth, "breadth": breadth},
                is_json=True,
            )
            parsed = json.loads(raw_json)

            research_goal = query
            tasks_data = []

            if isinstance(parsed, dict):
                research_goal = parsed.get("research_goal", query)
                tasks_data = parsed.get("tasks", [])
            elif isinstance(parsed, list):
                tasks_data = parsed

            tasks: List[ResearchTask] = []
            for i, item in enumerate(tasks_data):
                if isinstance(item, dict):
                    task_id = item.get("id") or f"task_{i + 1}"
                    question = item.get("question")
                    task_query = item.get("query") or question or query
                    category = item.get("category", "web")
                    depth_level = item.get("depth", 1)

                    tasks.append(
                        ResearchTask(
                            id=task_id,
                            question=question,
                            query=task_query,
                            category=category,
                            depth=depth_level,
                        )
                    )

            if tasks:
                return ResearchPlan(
                    research_goal=research_goal,
                    tasks=tasks,
                    depth=depth,
                    breadth=breadth,
                )

        except Exception as e:
            logger.warning(f"Planner Agent fallback triggered for query '{query}': {e}")

        # Robust multi-track fallback decomposition
        fallback_tasks = [
            ResearchTask(
                id="task_1",
                question=f"What are the core fundamentals and current landscape of {query}?",
                query=f"Overview and technological fundamentals of {query}",
                category="web",
                depth=1,
            ),
            ResearchTask(
                id="task_2",
                question=f"What are the empirical benchmarks, academic studies, and theoretical papers on {query}?",
                query=f"Empirical benchmarks theoretical papers studies on {query}",
                category="academic",
                depth=1,
            ),
            ResearchTask(
                id="task_3",
                question=f"What is the market growth, key players, adoption figures, and investment risks for {query}?",
                query=f"Market landscape adoption figures major companies investment risks for {query}",
                category="market",
                depth=1,
            ),
        ]

        return ResearchPlan(
            research_goal=query,
            tasks=fallback_tasks[:max(1, breadth)],
            depth=depth,
            breadth=breadth,
        )

    async def plan_research_tasks(
        self,
        query: str,
        depth: int = 2,
        breadth: int = 3
    ) -> List[ResearchTask]:
        """Convenience method returning direct List[ResearchTask] for executor compatibility."""
        plan = await self.create_plan(query, depth=depth, breadth=breadth)
        return plan.tasks


planner_agent = PlannerAgent()
