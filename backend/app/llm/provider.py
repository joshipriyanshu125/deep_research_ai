import json
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from app.config.settings import settings
from app.utils.logger import logger


class BaseLLMProvider(ABC):
    @abstractmethod
    async def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4000
    ) -> str:
        pass

    @abstractmethod
    async def generate_structured_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None
    ) -> str:
        pass


class MockLLMProvider(BaseLLMProvider):
    async def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4000
    ) -> str:
        # High quality simulated AI responses when keys are absent
        if "outline" in prompt.lower() or "plan" in prompt.lower():
            return (
                "### Research Plan\n"
                "1. Core Fundamentals & Historical Evolution\n"
                "2. State-of-the-Art Benchmarks & Quantitative Metrics\n"
                "3. Emerging Architectural Paradigms & Industry Adoption\n"
                "4. Critical Limitations, Safety Vectors, & Risk Analysis\n"
                "5. Strategic Outlook and Future Horizon"
            )
        return (
            "Comprehensive empirical research demonstrates exponential progress across frontier AI architectures, "
            "highlighting verifiable improvements in multi-step reasoning, test-time compute scaling, and autonomous "
            "tool integration. Rigorous benchmarking confirms high fidelity across domain tasks."
        )

    async def generate_structured_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None
    ) -> str:
        prompt_lower = prompt.lower()
        if "indian ev" in prompt_lower or "ev market" in prompt_lower:
            return json.dumps({
                "research_goal": "Analyze Indian EV market and identify investment opportunities",
                "tasks": [
                    {
                        "id": "task_1",
                        "question": "What is the current size of India's EV market?",
                        "query": "Current market size, total vehicle volume, and penetration of Indian EV market",
                        "category": "market"
                    },
                    {
                        "id": "task_2",
                        "question": "What is the expected market growth?",
                        "query": "Expected market growth CAGR forecasts for Indian EV ecosystem 2025-2030",
                        "category": "market"
                    },
                    {
                        "id": "task_3",
                        "question": "Who are the major EV companies?",
                        "query": "Key EV OEMs, battery manufacturers, and startup ecosystem leaders in India",
                        "category": "web"
                    },
                    {
                        "id": "task_4",
                        "question": "What government policies affect EV adoption?",
                        "query": "FAME II, EMPS, PLI battery schemes, state subsidies, and policy incentives for EVs in India",
                        "category": "academic"
                    },
                    {
                        "id": "task_5",
                        "question": "What are the major investment risks?",
                        "query": "Investment risks, charging infrastructure bottlenecks, battery supply chain constraints in India EV",
                        "category": "market"
                    }
                ]
            })

        if "decompose" in prompt_lower or "sub-tasks" in prompt_lower or "plan research" in prompt_lower or "sub-questions" in prompt_lower:
            return json.dumps({
                "research_goal": "Comprehensive research investigation and empirical decomposition",
                "tasks": [
                    {
                        "id": "task_1",
                        "question": "What are the core fundamentals, history, and architectural principles?",
                        "query": "Foundational architecture, mathematical principles, and theoretical literature",
                        "category": "academic"
                    },
                    {
                        "id": "task_2",
                        "question": "What are the latest empirical benchmark results and technical evaluations?",
                        "query": "State-of-the-art benchmark results, practical evaluations, and technical documentation",
                        "category": "web"
                    },
                    {
                        "id": "task_3",
                        "question": "What is the commercial landscape, market adoption, and strategic horizon?",
                        "query": "Commercial applications, enterprise market data, adoption statistics, and industry outlook",
                        "category": "market"
                    }
                ]
            })
        return '{"status": "success", "confidence": 0.95}'
