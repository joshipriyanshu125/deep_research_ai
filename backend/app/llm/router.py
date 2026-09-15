import re
import time
from enum import Enum
from typing import Optional, List, Dict, Any, Tuple
from pydantic import BaseModel, Field
from datetime import datetime, timedelta, timezone

from app.config.settings import settings
from app.utils.logger import logger
from app.utils.helpers import get_utc_now


class TaskComplexity(str, Enum):
    SIMPLE_EXTRACTION = "simple_extraction"
    COMPLEX_PLANNING = "complex_planning"
    LARGE_SYNTHESIS = "large_synthesis"
    FACT_CHECKING = "fact_checking"
    CODE_ANALYSIS = "code_analysis"
    GENERAL = "general"


class ModelTier(str, Enum):
    CHEAP = "cheap"
    REASONING = "reasoning"
    POWERFUL = "powerful"
    STANDARD = "standard"


class RoutingStrategy(str, Enum):
    BALANCED = "balanced"
    COST_MINIMIZED = "cost_minimized"
    LOWEST_LATENCY = "lowest_latency"
    MAX_QUALITY = "max_quality"
    REASONING_FOCUSED = "reasoning_focused"


class ModelProfile(BaseModel):
    model_id: str
    provider_type: str = "openai"  # openai, openrouter, gemini, anthropic, mock
    tier: ModelTier = ModelTier.STANDARD
    input_cost_per_1m: float = 1.0  # USD per 1M input tokens
    output_cost_per_1m: float = 3.0  # USD per 1M output tokens
    avg_latency_ms: float = 1200.0
    context_window: int = 128000
    supports_json: bool = True
    supports_reasoning: bool = False
    availability_score: float = 1.0  # 0.0 to 1.0
    consecutive_failures: int = 0
    circuit_open_until: Optional[datetime] = None

    def is_available(self) -> bool:
        if self.circuit_open_until:
            if get_utc_now() < self.circuit_open_until:
                return False
            # Circuit cool-down elapsed -> half-open
        return self.availability_score > 0.2


class RoutingDecision(BaseModel):
    selected_model: str
    provider_type: str
    tier: ModelTier
    complexity: TaskComplexity
    strategy: RoutingStrategy
    estimated_cost_usd: float
    expected_latency_ms: float
    fallback_chain: List[str] = Field(default_factory=list)
    routing_reason: str


class ModelRouter:
    """
    Multi-model intelligent router.
    Routes tasks to the optimal model based on task complexity, cost, latency, and availability.
    """

    def __init__(self):
        self._models: Dict[str, ModelProfile] = {}
        self._initialize_default_registry()

    def _initialize_default_registry(self):
        # 1. Cheap / Fast Models (Extraction, Classification, Fast Summary)
        self.register_model(ModelProfile(
            model_id="gpt-4o-mini",
            provider_type="openai",
            tier=ModelTier.CHEAP,
            input_cost_per_1m=0.15,
            output_cost_per_1m=0.60,
            avg_latency_ms=450.0,
            context_window=128000,
            supports_json=True
        ))
        self.register_model(ModelProfile(
            model_id="gemini-1.5-flash",
            provider_type="gemini",
            tier=ModelTier.CHEAP,
            input_cost_per_1m=0.075,
            output_cost_per_1m=0.30,
            avg_latency_ms=380.0,
            context_window=1000000,
            supports_json=True
        ))
        self.register_model(ModelProfile(
            model_id="claude-3-haiku",
            provider_type="anthropic",
            tier=ModelTier.CHEAP,
            input_cost_per_1m=0.25,
            output_cost_per_1m=1.25,
            avg_latency_ms=400.0,
            context_window=200000,
            supports_json=True
        ))

        # 2. Reasoning Models (Complex Planning, Verification, Multi-step Logic)
        self.register_model(ModelProfile(
            model_id="o3-mini",
            provider_type="openai",
            tier=ModelTier.REASONING,
            input_cost_per_1m=1.10,
            output_cost_per_1m=4.40,
            avg_latency_ms=2500.0,
            context_window=200000,
            supports_json=True,
            supports_reasoning=True
        ))
        self.register_model(ModelProfile(
            model_id="deepseek-r1",
            provider_type="openrouter",
            tier=ModelTier.REASONING,
            input_cost_per_1m=0.55,
            output_cost_per_1m=2.19,
            avg_latency_ms=2800.0,
            context_window=128000,
            supports_json=True,
            supports_reasoning=True
        ))
        self.register_model(ModelProfile(
            model_id="o1",
            provider_type="openai",
            tier=ModelTier.REASONING,
            input_cost_per_1m=15.0,
            output_cost_per_1m=60.0,
            avg_latency_ms=4500.0,
            context_window=200000,
            supports_json=True,
            supports_reasoning=True
        ))

        # 3. Powerful / High Synthesis Models (Comprehensive Reports, Deep Synthesis)
        self.register_model(ModelProfile(
            model_id="gpt-4o",
            provider_type="openai",
            tier=ModelTier.POWERFUL,
            input_cost_per_1m=2.50,
            output_cost_per_1m=10.00,
            avg_latency_ms=1200.0,
            context_window=128000,
            supports_json=True
        ))
        self.register_model(ModelProfile(
            model_id="claude-3-5-sonnet",
            provider_type="anthropic",
            tier=ModelTier.POWERFUL,
            input_cost_per_1m=3.00,
            output_cost_per_1m=15.00,
            avg_latency_ms=1400.0,
            context_window=200000,
            supports_json=True
        ))
        self.register_model(ModelProfile(
            model_id="gemini-1.5-pro",
            provider_type="gemini",
            tier=ModelTier.POWERFUL,
            input_cost_per_1m=1.25,
            output_cost_per_1m=5.00,
            avg_latency_ms=1300.0,
            context_window=2000000,
            supports_json=True
        ))

        # 4. Mock / Fallback Model
        self.register_model(ModelProfile(
            model_id="mock-llm",
            provider_type="mock",
            tier=ModelTier.CHEAP,
            input_cost_per_1m=0.0,
            output_cost_per_1m=0.0,
            avg_latency_ms=50.0,
            context_window=128000,
            supports_json=True,
            supports_reasoning=True
        ))

    def register_model(self, profile: ModelProfile):
        self._models[profile.model_id] = profile

    def get_model_profile(self, model_id: str) -> Optional[ModelProfile]:
        return self._models.get(model_id)

    def list_models(self) -> List[ModelProfile]:
        return list(self._models.values())

    # -------------------------------------------------------------
    # Task Complexity & Intent Classification
    # -------------------------------------------------------------
    def analyze_complexity(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        task_hint: Optional[str] = None
    ) -> TaskComplexity:
        """
        Heuristically and semantically classifies task complexity:
        - simple_extraction: entity parsing, regex, json key extraction, tables, short prompt
        - complex_planning: query decomposition, research outline, dependencies, multi-hop reasoning
        - large_synthesis: full research report, deep synthesis, executive summary, comprehensive review
        - fact_checking: claim verification, contradiction detection
        - code_analysis: code generation, debugging, syntax
        """
        if task_hint:
            hint = task_hint.lower().replace("-", "_").replace(" ", "_")
            if "extract" in hint or "parse" in hint or "filter" in hint or "clean" in hint:
                return TaskComplexity.SIMPLE_EXTRACTION
            if "plan" in hint or "decompose" in hint or "strategy" in hint:
                return TaskComplexity.COMPLEX_PLANNING
            if "synth" in hint or "report" in hint or "comprehensive" in hint or "write" in hint:
                return TaskComplexity.LARGE_SYNTHESIS
            if "fact" in hint or "verify" in hint or "contradict" in hint or "credib" in hint:
                return TaskComplexity.FACT_CHECKING
            if "code" in hint or "debug" in hint:
                return TaskComplexity.CODE_ANALYSIS

        combined_text = f"{system_prompt or ''}\n{prompt}".lower()

        # 1. Fact checking
        if any(k in combined_text for k in ["verify claim", "contradiction", "fact check", "source credibility"]):
            return TaskComplexity.FACT_CHECKING

        # 2. Complex Planning & Decomposition
        planning_keywords = [
            "decompose", "sub-questions", "subtasks", "research plan", "break down into tasks",
            "search strategy", "dependency graph", "multi-hop"
        ]
        if any(k in combined_text for k in planning_keywords):
            return TaskComplexity.COMPLEX_PLANNING

        # 3. Large Synthesis
        synthesis_keywords = [
            "synthesize", "comprehensive research report", "executive summary", "in-depth report",
            "academic paper", "full analysis", "draft section", "literature review"
        ]
        if any(k in combined_text for k in synthesis_keywords) or len(prompt) > 4000:
            return TaskComplexity.LARGE_SYNTHESIS

        # 4. Simple Extraction
        extraction_keywords = [
            "extract entities", "extract facts", "json object", "parse the following",
            "identify key terms", "table extraction", "convert to json", "classify"
        ]
        if any(k in combined_text for k in extraction_keywords) or len(prompt) < 400:
            return TaskComplexity.SIMPLE_EXTRACTION

        # Default to general
        return TaskComplexity.GENERAL

    # -------------------------------------------------------------
    # Intelligent Routing Engine
    # -------------------------------------------------------------
    def route(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        task_hint: Optional[str] = None,
        strategy: RoutingStrategy = RoutingStrategy.BALANCED,
        preferred_provider: Optional[str] = None,
        max_budget_usd: Optional[float] = None,
        max_latency_ms: Optional[float] = None
    ) -> RoutingDecision:
        complexity = self.analyze_complexity(prompt, system_prompt, task_hint)

        # Target tier mapping based on complexity and strategy
        if strategy == RoutingStrategy.MAX_QUALITY:
            tier_preference = [ModelTier.POWERFUL, ModelTier.REASONING, ModelTier.STANDARD, ModelTier.CHEAP]
        elif strategy == RoutingStrategy.COST_MINIMIZED:
            tier_preference = [ModelTier.CHEAP, ModelTier.STANDARD, ModelTier.POWERFUL, ModelTier.REASONING]
        elif strategy == RoutingStrategy.REASONING_FOCUSED:
            tier_preference = [ModelTier.REASONING, ModelTier.POWERFUL, ModelTier.STANDARD, ModelTier.CHEAP]
        elif complexity == TaskComplexity.SIMPLE_EXTRACTION:
            tier_preference = [ModelTier.CHEAP, ModelTier.STANDARD, ModelTier.POWERFUL]
        elif complexity in [TaskComplexity.COMPLEX_PLANNING, TaskComplexity.FACT_CHECKING]:
            tier_preference = [ModelTier.REASONING, ModelTier.POWERFUL, ModelTier.STANDARD, ModelTier.CHEAP]
        elif complexity == TaskComplexity.LARGE_SYNTHESIS:
            tier_preference = [ModelTier.POWERFUL, ModelTier.REASONING, ModelTier.STANDARD, ModelTier.CHEAP]
        else:
            tier_preference = [ModelTier.STANDARD, ModelTier.CHEAP, ModelTier.POWERFUL, ModelTier.REASONING]

        # Filter available models
        candidates = [m for m in self._models.values() if m.is_available()]
        if not candidates:
            candidates = list(self._models.values())  # fallback to all

        # Approximate token count
        est_input_tokens = max(10, len(prompt.split()) * 2)
        est_output_tokens = 1000 if complexity == TaskComplexity.LARGE_SYNTHESIS else 300

        # Score candidates
        scored_candidates: List[Tuple[float, ModelProfile]] = []
        for model in candidates:
            score = 100.0

            # Tier suitability score
            if model.tier in tier_preference:
                tier_idx = tier_preference.index(model.tier)
                score -= tier_idx * 25.0
            else:
                score -= 50.0

            # Calculate estimated cost
            cost = (
                (est_input_tokens / 1_000_000.0) * model.input_cost_per_1m +
                (est_output_tokens / 1_000_000.0) * model.output_cost_per_1m
            )

            # Strategy Adjustments
            if strategy == RoutingStrategy.COST_MINIMIZED:
                # Heavily penalize higher cost models
                score -= (cost * 5000.0)
                if model.tier == ModelTier.CHEAP:
                    score += 40.0
            elif strategy == RoutingStrategy.LOWEST_LATENCY:
                # Penalize latency
                score -= (model.avg_latency_ms / 50.0)
            elif strategy == RoutingStrategy.MAX_QUALITY:
                if model.tier in [ModelTier.POWERFUL, ModelTier.REASONING]:
                    score += 35.0
            elif strategy == RoutingStrategy.REASONING_FOCUSED:
                if model.supports_reasoning or model.tier == ModelTier.REASONING:
                    score += 50.0

            # Provider preference bonus
            if preferred_provider and model.provider_type.lower() == preferred_provider.lower():
                score += 20.0

            # Constraints
            if max_budget_usd is not None and cost > max_budget_usd:
                score -= 100.0
            if max_latency_ms is not None and model.avg_latency_ms > max_latency_ms:
                score -= 100.0

            # Availability weighting
            score *= model.availability_score

            scored_candidates.append((score, model))

        scored_candidates.sort(key=lambda x: x[0], reverse=True)

        best_model = scored_candidates[0][1]
        fallback_models = [m[1].model_id for m in scored_candidates[1:4]]

        best_cost = (
            (est_input_tokens / 1_000_000.0) * best_model.input_cost_per_1m +
            (est_output_tokens / 1_000_000.0) * best_model.output_cost_per_1m
        )

        reason = (
            f"Routed {complexity.value} task to '{best_model.model_id}' ({best_model.tier.value} tier) "
            f"via {strategy.value} strategy with {best_model.provider_type} provider."
        )

        return RoutingDecision(
            selected_model=best_model.model_id,
            provider_type=best_model.provider_type,
            tier=best_model.tier,
            complexity=complexity,
            strategy=strategy,
            estimated_cost_usd=round(best_cost, 6),
            expected_latency_ms=best_model.avg_latency_ms,
            fallback_chain=fallback_models,
            routing_reason=reason
        )

    # -------------------------------------------------------------
    # Health Tracking & Fallback Management
    # -------------------------------------------------------------
    def record_success(self, model_id: str, latency_ms: Optional[float] = None):
        profile = self._models.get(model_id)
        if profile:
            profile.consecutive_failures = 0
            profile.circuit_open_until = None
            profile.availability_score = min(1.0, profile.availability_score + 0.1)
            if latency_ms:
                profile.avg_latency_ms = (profile.avg_latency_ms * 0.8) + (latency_ms * 0.2)

    def record_failure(self, model_id: str, error: Optional[str] = None):
        profile = self._models.get(model_id)
        if profile:
            profile.consecutive_failures += 1
            profile.availability_score = max(0.0, profile.availability_score - 0.3)
            logger.warning(
                f"Model {model_id} failure count={profile.consecutive_failures}, "
                f"avail_score={profile.availability_score:.2f}, error={error}"
            )
            # Trip circuit breaker on 3 consecutive failures
            if profile.consecutive_failures >= 3:
                profile.circuit_open_until = get_utc_now() + timedelta(minutes=5)
                logger.error(f"Circuit breaker OPEN for model {model_id} for 5 minutes.")

    def reset_health(self):
        for profile in self._models.values():
            profile.consecutive_failures = 0
            profile.circuit_open_until = None
            profile.availability_score = 1.0


model_router = ModelRouter()
