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
        is_report = "report" in prompt_lower or "synthesize" in prompt_lower or "research subject:" in prompt_lower or "verified evidence pool" in prompt_lower

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
        if not query_match:
            query_match = re.search(r"research (?:topic|question|objective):\s*['\"]?([^'\n\r\"]+)", prompt, re.IGNORECASE)
        query = query_match.group(1).strip() if query_match else "Market Research and Investment Analysis"

        # Check for evidence summary in prompt
        evidence_lines = []
        for line in prompt.splitlines():
            line_str = line.strip()
            if line_str.startswith("[") and ("Claim:" in line_str or "Quote:" in line_str):
                # Clean and filter out placeholder claims
                if "market analysis and commercial roadmap" not in line_str.lower():
                    evidence_lines.append(line_str)

        is_ev_query = any(k in query.lower() for k in ["ev", "electric vehicle", "battery", "mobility", "automotive", "india"])

        report_lines = [
            f"# Deep Research Report: {query}\n",
            "## 1. Executive Summary",
            f"This comprehensive intelligence report provides an in-depth empirical analysis of **{query}**. "
            "Integrating multi-source research across authoritative industry reports, regulatory filings, and market intelligence, "
            "the findings outline current adoption trajectories, structural supply chain shifts, key competitive players, "
            "and high-conviction investment opportunities alongside critical risk vectors.\n",
            "## 2. Market Overview & Current Sizing",
            (
                f"The Indian electric vehicle (EV) and clean mobility ecosystem is accelerating through a pivotal expansion phase. "
                f"Multi-vector empirical data confirms surging penetration across electric two-wheelers (E2W), three-wheelers (E3W), and passenger vehicles. "
                f"Macro policy mechanisms including the PM E-DRIVE scheme, concessional 5% GST, and ACC Battery PLI are anchoring substantial domestic capital investments."
                if is_ev_query else
                f"The ecosystem for {query} is undergoing rapid commercial transformation, driven by robust macro policy support, "
                "surging consumer adoption, and aggressive manufacturing localization. Multi-vector empirical analysis demonstrates "
                "significant scale-up across core segments, with compounding annual growth rates outpacing traditional benchmarks.\n"
            ),
            "\n## 3. Key Findings & Quantitative Breakdown",
        ]

        if evidence_lines:
            for el in evidence_lines[:12]:
                report_lines.append(f"- {el}")
        elif is_ev_query:
            report_lines.extend([
                "- Electric passenger vehicle registrations recorded rapid YoY expansion, with momentum driven by new model launches and fleet electrification.",
                "- Domestic cell gigafactory developments from Tata Agratas, Ola, Exide, and Amara Raja are scaling to reduce import dependencies.",
                "- Government incentive frameworks (Auto PLI, PM E-DRIVE, concessional GST) provide strong policy tailwinds.",
                "- Public fast-charging deployment along commercial freight and highway corridors is accelerating.",
            ])
        else:
            report_lines.extend([
                f"- Exponential growth and high capital deployment observed across primary segments of {query}.",
                "- Domestic localization and production-linked incentives are substantially reducing unit component costs.",
                "- Government subsidy frameworks provide strong downside protection.",
                "- Infrastructure expansion and supply chain development represent the primary bottlenecks and value drivers.",
            ])

        report_lines.extend([
            "\n## 4. Key Players & Competitive Landscape",
            "Established OEMs and agile pure-play startups are competing aggressively across vehicle platforms, "
            "battery pack assembly, and component localization. Tier-1 suppliers and battery gigafactory developers "
            "are forming strategic joint ventures to secure long-term raw material supply and cell manufacturing capacity.\n",
            "## 5. Strategic Investment Opportunities",
            "- **Component & Value-Chain Localization**: High margins in powertrain, wiring harnesses, power electronics, and battery management systems (BMS).",
            "- **Battery Recycling & Second-Life Energy Storage**: Fast-growing sub-sector with high CAGR potential as first-generation vehicle battery packs retire.",
            "- **Charging & Energy Infrastructure**: High-utilization charging hubs for commercial fleets and fast-charging corridors.",
            "- **Fleet Electrification**: B2B delivery fleets and two-wheeler/three-wheeler urban mobility platforms offering recurring cashflows.\n",
            "## 6. Critical Risks & Challenges",
            "- **Infrastructure & Grid Bottlenecks**: Public charging station density remains a key constraint outside tier-1 metros.",
            "- **Raw Material Volatility**: Global supply chain dependencies for critical minerals (Lithium, Nickel, Cobalt).",
            "- **Policy & Subsidy Transitions**: Evolving subsidy criteria and homologation standards require proactive regulatory compliance.\n",
            "## 7. Strategic Recommendations",
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
        sys_lower = (system_prompt or "").lower()

        # 1. Synthesis / Report JSON output
        if "synthesis" in prompt_lower or "key_findings" in sys_lower or "market_analysis" in sys_lower:
            query_m = re.search(r"research topic:\s*'([^']+)'", prompt, re.IGNORECASE)
            if not query_m:
                query_m = re.search(r"Research Subject:\s*([^\n\r]+)", prompt, re.IGNORECASE)
            query = query_m.group(1).strip() if query_m else "Indian EV Market Analysis"

            # Harvest claims from prompt
            extracted_claims = []
            for line in prompt.splitlines():
                line_s = line.strip()
                if (line_s.startswith("- Claim:") or line_s.startswith("[")) and "market analysis and commercial roadmap" not in line_s.lower():
                    clean_c = re.sub(r"^-\s*Claim:\s*", "", line_s)
                    clean_c = re.sub(r"\s*\|\s*Source:.*$", "", clean_c)
                    if len(clean_c) > 20:
                        extracted_claims.append(clean_c)

            is_ev = any(k in query.lower() for k in ["ev", "electric vehicle", "battery", "mobility", "automotive", "india"])

            if extracted_claims:
                findings = extracted_claims[:6]
            elif is_ev:
                findings = [
                    "Electric vehicle adoption in India is accelerating rapidly across 2W, 3W, and commercial passenger segments.",
                    "PM E-DRIVE and ACC Battery PLI schemes with ₹44,000+ Cr budgetary outlays are driving aggressive domestic cell manufacturing.",
                    "Tier-1 component localization (traction motors, wiring harnesses, BMS) is delivering significant margin expansion for domestic suppliers.",
                    "Rapid charging network buildout and battery swapping are driving high-utilization commercial fleet conversions.",
                ]
            else:
                findings = [
                    f"Robust empirical growth and accelerating commercial adoption observed across {query}.",
                    "Strong alignment between government incentive architectures and private manufacturing capital investments.",
                    "Domestic supply chain localization actively scaling to reduce unit cost structures.",
                ]

            market_analysis = (
                "The Indian EV and clean mobility market is accelerating from early-stage adoption into multi-decade structural growth. "
                "Analysis highlights rapid scale-up across electric 2-wheelers, 3-wheelers, and commercial fleets, supported by concessional 5% GST, "
                "PM E-DRIVE subsidies, and multi-gigawatt domestic battery manufacturing commitments."
                if is_ev else
                f"The market for '{query}' is experiencing structural expansion across core segments, underpinned by strong regulatory frameworks and accelerating capital deployment."
            )

            return json.dumps({
                "key_findings": findings,
                "market_analysis": market_analysis,
                "trends": [
                    "Rapid transition towards domestic cell gigafactories and localized component sourcing.",
                    "Expansion of high-power public DC charging networks and battery swapping infrastructure.",
                    "Commercial fleet electrification leading fleet-level total cost of ownership (TCO) parity.",
                ],
                "opportunities": [
                    "Tier-1 component manufacturing (BMS, wiring harnesses, traction motors).",
                    "Battery pack assembly, energy storage systems (BESS), and lithium recycling.",
                    "Commercial B2B fleet electrification and smart fleet charging software.",
                ],
                "recommendations": [
                    "Direct capital allocation towards defensible Tier-1 component suppliers rather than pure vehicle assembly OEMs.",
                    "Form strategic joint ventures with domestic cell gigafactories to secure long-term battery cell supply.",
                    "Leverage PM E-DRIVE and state manufacturing incentives to optimize plant Capex.",
                ],
                "risks": [
                    "Charging infrastructure bottlenecks outside Tier-1 metropolitan centers.",
                    "Global supply chain dependencies for critical battery minerals (Lithium, Nickel, Cobalt).",
                    "Subsidy taper trajectories as sub-segments approach unsubsidized price parity.",
                ],
                "contradictions": [],
                "uncertainty": [
                    "Rate of domestic battery cell cost deflation over the next 24-36 months.",
                ],
                "executive_summary": f"Empirical intelligence synthesis on '{query}' confirms robust structural expansion, localized supply chain scaling, and defensible investment opportunities.",
                "confidence": 0.92,
                "confidence_level": "HIGH"
            })

        # 2. Planning JSON output
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
