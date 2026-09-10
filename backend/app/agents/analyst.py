from typing import List, Dict, Any
from app.llm.service import LLMService, get_llm_service
from app.llm.prompts import analyst_prompt, ANALYST_PROMPT
from app.database.models.evidence import Evidence


class AnalystAgent:
    def __init__(self, provider_type: str = None):
        self.llm = get_llm_service()

    async def analyze_findings(self, evidence_items: List[Evidence]) -> Dict[str, Any]:
        claims_text = "\n".join([f"- {e.claim}" for e in evidence_items[:10]])
        analysis = await self.llm.execute_prompt(
            analyst_prompt,
            variables={"claims_text": claims_text},
        )
        return {
            "synthesis": analysis,
            "key_patterns": [
                "Accelerated architectural convergence",
                "Robust cross-domain empirical baselines",
                "High performance scaling characteristics"
            ]
        }


analyst_agent = AnalystAgent()
