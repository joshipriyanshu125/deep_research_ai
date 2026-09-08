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
        if "decompose" in prompt.lower() or "sub-questions" in prompt.lower():
            return """[
                {"query": "Foundational architecture and mathematical principles", "category": "academic"},
                {"query": "State of the art benchmark results and empirical evaluations", "category": "web"},
                {"query": "Commercial applications, enterprise market data, and adoption", "category": "market"}
            ]"""
        return '{"status": "success", "confidence": 0.95}'
