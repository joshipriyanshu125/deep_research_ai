import json
import re
from typing import List, Dict, Any, Optional
from app.llm.service import get_llm_service, llm_provenance
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

_CATEGORY_ALIASES = {
    "web": "web",
    "news": "web",
    "online": "web",
    "academic": "academic",
    "academia": "academic",
    "papers": "academic",
    "paper": "academic",
    "market": "market",
    "markets": "market",
    "financial": "market",
}
_PLANNER_STOP_WORDS = {
    "what", "who", "why", "how", "when", "where", "which", "does", "did",
    "can", "could", "should", "would", "will", "the", "and", "for", "with",
    "about", "into", "from", "that", "this", "current", "identify", "explain",
}
_MARKET_INTENT = re.compile(
    r"\b(market|investment|investor|revenue|sales|pricing|industry|adoption|"
    r"company|companies|commercial|supply\s+chain|economic|forecast)\b",
    re.IGNORECASE,
)
_ACADEMIC_INTENT = re.compile(
    r"\b(research|paper|study|literature|theor(y|etical)|algorithm|architecture|"
    r"benchmark|scientific|methodology|experiment|quantum|biology|physics|medical)\b",
    re.IGNORECASE,
)

_FALLBACK_TASK_TEMPLATES = {
    "web": (
        (
            "What current, source-backed facts describe {query}?",
            "{query} current authoritative overview evidence",
        ),
        (
            "What recent developments or primary-source updates matter for {query}?",
            "{query} latest developments primary sources",
        ),
    ),
    "academic": (
        (
            "What do published studies and technical literature conclude about {query}?",
            "{query} peer reviewed research findings",
        ),
        (
            "Which methods, benchmarks, or limitations are documented for {query}?",
            "{query} empirical study benchmark methodology limitations",
        ),
    ),
    "market": (
        (
            "What commercial applications, participants, or adoption evidence is documented for {query}?",
            "{query} commercial applications adoption industry evidence",
        ),
        (
            "What economic, pricing, or implementation risks are documented for {query}?",
            "{query} pricing economics implementation risks evidence",
        ),
    ),
}


def _normalise_categories(categories: Optional[List[str]]) -> List[str]:
    """Return stable, supported category names while preserving user order."""
    if not categories:
        return []
    result: List[str] = []
    for value in categories:
        normalised = _CATEGORY_ALIASES.get(str(value).strip().lower())
        if normalised and normalised not in result:
            result.append(normalised)
    return result


def _query_tokens(query: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", query.lower())
        if token not in _PLANNER_STOP_WORDS and (len(token) > 2 or token in {"ai", "ev", "ml"})
    }


class PlannerAgent:
    """
    Agentic planner that decomposes complex research topics into structured investigation plans.

    Day 47 additions:
      - ``classify_complexity(query)``   → returns 'simple' | 'moderate' | 'complex'
      - ``estimate_task_count(query, depth, breadth)`` → returns dynamic task count target (2–50)
    """

    def __init__(self, provider_type: Optional[str] = None):
        self.llm = get_llm_service(provider_type=provider_type)

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
        target = max(self.estimate_task_count(query, depth, breadth), len({t.category for t in tasks}))
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
        breadth: int = 3,
        categories: Optional[List[str]] = None,
    ) -> ResearchPlan:
        """Analyze research objective and produce a structured ResearchPlan with atomic tasks."""
        active_categories = self._resolve_categories(query, categories)
        try:
            raw_json = await self.llm.execute_prompt(
                planner_prompt,
                variables={
                    "query": query,
                    "depth": depth,
                    "breadth": breadth,
                    "categories": ", ".join(active_categories),
                },
                is_json=True,
            )
            parsed = json.loads(raw_json)

            research_goal = query
            tasks_data = []

            if isinstance(parsed, dict):
                candidate_goal = str(parsed.get("research_goal") or query).strip()
                research_goal = candidate_goal if self._mentions_query(candidate_goal, query) else query
                tasks_data = parsed.get("tasks", [])
            elif isinstance(parsed, list):
                tasks_data = parsed

            tasks: List[ResearchTask] = []
            for i, item in enumerate(tasks_data):
                if isinstance(item, dict):
                    question = str(item.get("question") or "").strip()
                    task_query = str(item.get("query") or question or query).strip()
                    category = _CATEGORY_ALIASES.get(
                        str(item.get("category") or "web").strip().lower(),
                        "",
                    )
                    # Reject a provider response that is about another
                    # familiar topic (for example a canned India EV plan).
                    if category not in active_categories or not self._mentions_query(
                        f"{question} {task_query}", query
                    ):
                        continue
                    task_id = str(item.get("id") or f"task_{len(tasks) + 1}")
                    depth_level = item.get("depth", 1)
                    try:
                        depth_level = max(1, int(depth_level))
                    except (TypeError, ValueError):
                        depth_level = 1

                    tasks.append(
                        ResearchTask(
                            id=task_id,
                            question=question or task_query,
                            query=task_query,
                            category=category,
                            depth=depth_level,
                        )
                    )

            if tasks:
                tasks = self._ensure_category_coverage(tasks, query, active_categories)
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
                    metadata={
                        "complexity": complexity,
                        "estimated_tasks": estimated,
                        "categories": active_categories,
                        "planner_provider": llm_provenance(self.llm),
                        "llm_used": llm_provenance(self.llm).get("llm_used", False),
                    },
                )

        except Exception as e:
            logger.warning(f"Planner Agent fallback triggered for query '{query}': {e}")

        fallback_tasks = self._build_fallback_tasks(query, breadth, active_categories)

        return ResearchPlan(
            research_goal=query,
            tasks=fallback_tasks,
            depth=depth,
            breadth=breadth,
            metadata={
                "complexity": self.classify_complexity(query),
                "estimated_tasks": self.estimate_task_count(query, depth, breadth),
                "categories": active_categories,
                "planner_provider": llm_provenance(self.llm),
                "llm_used": False,
            },
        )

    def _resolve_categories(self, query: str, categories: Optional[List[str]]) -> List[str]:
        requested = _normalise_categories(categories)
        if requested:
            return requested

        # Infer a narrow default plan.  Market is included only when the
        # objective contains market/commercial intent; technical questions do
        # not receive unrelated investment tracks.
        if _MARKET_INTENT.search(query):
            return ["web", "academic", "market"]
        if _ACADEMIC_INTENT.search(query):
            return ["web", "academic"]
        return ["web"]

    @staticmethod
    def _mentions_query(text: str, query: str) -> bool:
        tokens = _query_tokens(query)
        if not tokens:
            return bool(text.strip())
        text_tokens = set(re.findall(r"[a-z0-9]+", text.lower()))
        return bool(tokens.intersection(text_tokens))

    def _build_fallback_tasks(
        self,
        query: str,
        breadth: int,
        categories: List[str],
    ) -> List[ResearchTask]:
        count = max(len(categories), min(8, int(breadth or 1)))
        tasks: List[ResearchTask] = []
        for i in range(count):
            category = categories[i % len(categories)]
            templates = _FALLBACK_TASK_TEMPLATES[category]
            question_template, query_template = templates[(i // len(categories)) % len(templates)]
            tasks.append(
                ResearchTask(
                    id=f"task_{i + 1}",
                    question=question_template.format(query=query),
                    query=query_template.format(query=query),
                    category=category,
                    depth=1,
                )
            )
        return tasks

    def _ensure_category_coverage(
        self,
        tasks: List[ResearchTask],
        query: str,
        categories: List[str],
    ) -> List[ResearchTask]:
        present = {task.category for task in tasks}
        result = list(tasks)
        next_id = len(result) + 1
        for category in categories:
            if category in present:
                continue
            question_template, query_template = _FALLBACK_TASK_TEMPLATES[category][0]
            result.append(
                ResearchTask(
                    id=f"task_{next_id}",
                    question=question_template.format(query=query),
                    query=query_template.format(query=query),
                    category=category,
                    depth=1,
                )
            )
            next_id += 1
        return result

    async def plan_research_tasks(
        self,
        query: str,
        depth: int = 2,
        breadth: int = 3,
        categories: Optional[List[str]] = None,
    ) -> List[ResearchTask]:
        """Convenience method returning direct List[ResearchTask] for executor compatibility."""
        plan = await self.create_plan(
            query,
            depth=depth,
            breadth=breadth,
            categories=categories,
        )
        return plan.tasks


planner_agent = PlannerAgent()
