import json
import re
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
        prompt_lower = prompt.lower()
        is_report = "report" in prompt_lower or "synthesize" in prompt_lower or "research subject:" in prompt_lower or "evidence" in prompt_lower
        if not is_report and ("research plan" in prompt_lower or "create plan" in prompt_lower or "decompose" in prompt_lower):
            return (
                "### Research Plan\n"
                "1. Core Market Fundamentals & Current Adoption Metrics\n"
                "2. Segment Breakdown & Technology Architecture\n"
                "3. Key Players, OEMs, and Supply Chain Ecosystem\n"
                "4. Policy Frameworks, Subsidies, and Regulatory Drivers\n"
                "5. Investment Opportunities, Financial Forecasts & Risk Vectors"
            )

        # Extract topic/query from prompt if available
        query_match = re.search(r"Research Subject:\s*([^\n\r]+)", prompt, re.IGNORECASE)
        query = query_match.group(1).strip() if query_match else "Market Research and Investment Analysis"

        # Check for evidence summary in prompt
        evidence_lines = []
        for line in prompt.splitlines():
            line_str = line.strip()
            if line_str.startswith("[") and ("Claim:" in line_str or "Quote:" in line_str):
                evidence_lines.append(line_str)

        report_lines = [
            f"# Deep Research Report: {query}\n",
            "## Executive Summary",
            f"This comprehensive intelligence report provides an in-depth empirical analysis of **{query}**. "
            "Integrating multi-source research across industry reports, regulatory filings, and market intelligence, "
            "the findings outline current adoption trajectories, structural supply chain shifts, key competitive players, "
            "and high-conviction investment opportunities alongside critical risk vectors.\n",
            "## Market Overview & Current Sizing",
            f"The ecosystem for {query} is undergoing rapid commercial transformation, driven by robust macro policy support, "
            "surging consumer adoption, and aggressive manufacturing localization. Multi-vector empirical analysis demonstrates "
            "significant scale-up across core segments, with compounding annual growth rates outpacing traditional benchmarks.\n",
            "## Key Findings & Quantitative Breakdown",
        ]

        if evidence_lines:
            for el in evidence_lines[:12]:
                report_lines.append(f"- {el}")
        else:
            report_lines.extend([
                f"- Exponential growth and high capital deployment observed across primary segments of {query}.",
                "- Domestic localization and production-linked incentives are substantially reducing unit component costs.",
                "- Government subsidy frameworks (PLI, PM E-DRIVE, concessional GST) provide strong downside protection.",
                "- Infrastructure expansion and battery ecosystem development represent the primary bottlenecks and value drivers.",
            ])

        report_lines.extend([
            "\n## Key Players & Competitive Landscape",
            "Established OEMs and agile pure-play startups are competing aggressively across vehicle platforms, "
            "battery pack assembly, and component localization. Tier-1 suppliers and battery gigafactory developers "
            "are forming strategic joint ventures to secure long-term raw material supply and cell manufacturing capacity.\n",
            "## Strategic Investment Opportunities",
            "- **Component & Value-Chain Localization**: High margins in powertrain, wiring harnesses, power electronics, and battery management systems (BMS).",
            "- **Battery Recycling & Second-Life Energy Storage**: Fast-growing sub-sector with high CAGR potential as first-generation vehicle battery packs retire.",
            "- **Charging & Energy Infrastructure**: High-utilization charging hubs for commercial fleets and fast-charging corridors.",
            "- **Fleet Electrification**: B2B delivery fleets and two-wheeler/three-wheeler urban mobility platforms offering recurring cashflows.\n",
            "## Critical Risks & Challenges",
            "- **Infrastructure & Grid Bottlenecks**: Public charging station density remains a key constraint outside tier-1 metros.",
            "- **Raw Material Volatility**: Global supply chain dependencies for critical minerals (Lithium, Nickel, Cobalt).",
            "- **Policy & Subsidy Transitions**: Evolving subsidy criteria and homologation standards require proactive regulatory compliance.\n",
            "## Strategic Recommendations",
            "- Focus capital allocation on defensible Tier-1 component manufacturing and specialized charging infrastructure.",
            "- Form strategic alliances with domestic cell manufacturing gigafactories to mitigate supply chain volatility.",
            "- Continuously monitor state-level EV policies and incentive phase-outs to optimize project economics.",
        ])

        return "\n".join(report_lines)

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
