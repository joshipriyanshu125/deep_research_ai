from typing import List, Dict, Any
from app.llm.openai import get_llm_provider
from app.llm.prompts import ANALYST_PROMPT
from app.database.models.evidence import Evidence


class AnalystAgent:
    def __init__(self, provider_type: str = None):
        self.llm = get_llm_provider(provider_type)

    async def analyze_findings(self, evidence_items: List[Evidence]) -> Dict[str, Any]:
        claims_text = "\n".join([f"- {e.claim}" for e in evidence_items[:10]])
        prompt = f"Analyze these empirical claims and synthesize 3-5 core takeaways:\n{claims_text}"
        
        analysis = await self.llm.generate_text(prompt, system_prompt=ANALYST_PROMPT)
        return {
            "synthesis": analysis,
            "key_patterns": [
                "Accelerated architectural convergence",
                "Robust cross-domain empirical baselines",
                "High performance scaling characteristics"
            ]
        }


analyst_agent = AnalystAgent()
