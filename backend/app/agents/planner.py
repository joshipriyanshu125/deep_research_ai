import json
import re
from typing import List, Dict, Any, Optional, Tuple, Union
from app.llm.service import LLMService, get_llm_service
from app.llm.prompts import planner_prompt, PLANNER_SYSTEM_PROMPT
from app.database.models.research import ResearchTask, ResearchPlan
from app.utils.logger import logger


# ---------------------------------------------------------------------------
# Day 47 — Query complexity classification helpers
# ---------------------------------------------------------------------------

# Signals that indicate a complex, multi-faceted research question
_COMPLEX_SIGNALS = [
    r"\banalyze\b", r"\banalyse\b", r"\bcompare\b", r"\bcontrast\b",
    r"\binvestment opportunit", r"\bmarket (analysis|landscape|trend)",
    r"\bcomprehensive\b", r"\bin-depth\b", r"\bcompetitive\b",
    r"\bforecast\b", r"\bprediction\b", r"\bglobal\b",
    r"\bstrateg(y|ic)\b", r"\bregulat(ion|ory)\b",
    r"\beco(nomics|system)\b", r"\bpolicy\b", r"\bgovernance\b",
    r"\bsupply chain\b", r"\bgeopolit", r"\bmultiple\b",
]
_SIMPLE_SIGNALS = [
    r"^what is\b", r"^who is\b", r"^define\b", r"^explain\b",
    r"^how does\b", r"^when did\b", r"^where is\b",
]
_COMPLEX_PATTERN = re.compile("|".join(_COMPLEX_SIGNALS), re.IGNORECASE)
_SIMPLE_PATTERN = re.compile("|".join(_SIMPLE_SIGNALS), re.IGNORECASE)


class PlannerAgent:
    """
    Agentic planner that decomposes complex research topics into structured investigation plans.

    Day 47 additions:
      - ``classify_complexity(query)``   → returns 'simple' | 'moderate' | 'complex'
      - ``estimate_task_count(query, depth, breadth)`` → returns dynamic task count target (2–50)
    """

    def __init__(self, provider_type: Optional[str] = None):
        self.llm = get_llm_service()

    # ------------------------------------------------------------------
    # Day 47 — Dynamic planning helpers
    # ------------------------------------------------------------------

    def classify_complexity(self, query: str) -> str:
        """
        Classify query complexity as 'simple', 'moderate', or 'complex'.

        Simple:   "What is Python?"  → 2–5 tasks
        Moderate: "Explain AI in healthcare"  → 6–15 tasks
        Complex:  "Analyze India's EV market and identify investment opportunities"  → 16–50 tasks
        """
        query_lower = query.strip()
        word_count = len(query_lower.split())

        # Quick simple check
        if _SIMPLE_PATTERN.search(query_lower) and word_count <= 6:
            return "simple"

        complex_hits = len(_COMPLEX_PATTERN.findall(query_lower))

        if complex_hits >= 3 or word_count >= 15:
            return "complex"
        if complex_hits >= 1 or word_count >= 8:
            return "moderate"
        return "simple"

    def estimate_task_count(self, query: str, depth: int = 2, breadth: int = 3) -> int:
        """
        Day 47 — Dynamically decide how many tasks the planner should target.

        Simple query  → target  2–4  tasks (no deep research needed)
        Moderate query → target  6–12 tasks
        Complex query  → target 16–50 tasks (scales with depth × breadth)

        Args:
            query:   The research query.
            depth:   Requested depth parameter (1–5).
            breadth: Requested breadth parameter (1–8).

        Returns:
            Target number of tasks.
        """
        complexity = self.classify_complexity(query)

        if complexity == "simple":
            # Ignore depth/breadth — keep it light
            count = max(2, min(4, breadth))
        elif complexity == "moderate":
            count = max(4, depth * breadth + breadth)
        else:  # complex
            count = max(8, depth * breadth * 2 + breadth)

        # Hard cap: never exceed 50
        return min(50, count)

    def _adjust_tasks_for_complexity(
        self, tasks: List[ResearchTask], query: str, depth: int, breadth: int
    ) -> List[ResearchTask]:
        """
        Trim or pad the task list to match the dynamic task count target.
        Trimming preserves category diversity; padding adds web tasks.
        """
        target = self.estimate_task_count(query, depth, breadth)
        if len(tasks) <= target:
            return tasks
        # Trim: keep a balanced set across categories
        by_cat: Dict[str, List[ResearchTask]] = {}
        for t in tasks:
            by_cat.setdefault(t.category, []).append(t)
        trimmed: List[ResearchTask] = []
        while len(trimmed) < target:
            added = False
            for cat_tasks in by_cat.values():
                if cat_tasks and len(trimmed) < target:
                    trimmed.append(cat_tasks.pop(0))
                    added = True
            if not added:
                break
        return trimmed[:target]

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
                # Day 47: adjust task list to match dynamic complexity target
                tasks = self._adjust_tasks_for_complexity(tasks, query, depth, breadth)
                complexity = self.classify_complexity(query)
                estimated = self.estimate_task_count(query, depth, breadth)
                logger.info(
                    f"[DynamicPlanner] complexity={complexity} | "
                    f"target_tasks={estimated} | actual_tasks={len(tasks)}"
                )
                return ResearchPlan(
                    research_goal=research_goal,
                    tasks=tasks,
                    depth=depth,
                    breadth=breadth,
                    metadata={"complexity": complexity, "estimated_tasks": estimated},
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
