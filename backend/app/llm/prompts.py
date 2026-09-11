"""
Centralized Prompt Management & Registry.

Defines all prompts across the application in a unified, version-controlled structure.
Every prompt configuration specifies:
- Prompt Version
- Model / Model Alias
- Temperature
- Max Tokens
- System Prompt Template
- User Prompt Template
- Metadata / Description

This eliminates scattered prompts throughout the codebase and provides clear debugging telemetry.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union
from app.config.settings import settings


@dataclass
class PromptConfig:
    """Configuration and template container for a centralized LLM prompt."""

    name: str
    version: str
    system_prompt: str
    user_template: str
    model: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 4000
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def format_user_prompt(self, **kwargs) -> str:
        """Format the user template with provided keyword arguments."""
        if not kwargs:
            return self.user_template
        return self.user_template.format(**kwargs)

    def format_system_prompt(self, **kwargs) -> str:
        """Format the system prompt if dynamic variables are present."""
        if not kwargs:
            return self.system_prompt
        return self.system_prompt.format(**kwargs)

    def get_execution_params(self, **overrides) -> Dict[str, Any]:
        """Return parameters dictionary for LLM execution."""
        return {
            "system_prompt": overrides.get("system_prompt", self.system_prompt),
            "temperature": overrides.get("temperature", self.temperature),
            "max_tokens": overrides.get("max_tokens", self.max_tokens),
            "model": overrides.get("model", self.model or settings.DEFAULT_MODEL),
        }

    def to_dict(self) -> Dict[str, Any]:
        """Serialize configuration to dictionary."""
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "model": self.model or settings.DEFAULT_MODEL,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "system_prompt": self.system_prompt,
            "user_template": self.user_template,
            "metadata": self.metadata,
        }


# ===================================================================== #
#  Centralized Prompts Definition
# ===================================================================== #

# 1. Planner Prompt
planner_prompt = PromptConfig(
    name="planner_prompt",
    version="1.1.0",
    description="Decomposes research topics into structured research goals and sub-questions.",
    model=None,
    temperature=0.2,
    max_tokens=2000,
    system_prompt="""You are a Principal Research Director and Systems Thinker.
Your role is to analyze research objectives and decompose complex research questions into structured, atomic investigation tracks.
Categorize tasks into 'web' (current web news/articles), 'academic' (peer-reviewed scientific literature), and 'market' (industry stats/commercial data).

Respond strictly in valid JSON format using the following schema:
{
  "research_goal": "Concise summary of research objective",
  "tasks": [
    {
      "id": "task_1",
      "question": "Specific investigative question",
      "query": "Targeted search query",
      "category": "web" | "academic" | "market"
    }
  ]
}""",
    user_template="""Decompose and plan research for query: '{query}'.
Depth level: {depth}. Number of sub-tasks: {breadth}.
Return structured JSON containing 'research_goal' and an array of 'tasks' with id, question, query, and category ('web', 'academic', or 'market').""",
    metadata={"agent": "PlannerAgent", "task": "decomposition"},
)
PLANNER_PROMPT = planner_prompt


# 2. Research Prompt
research_prompt = PromptConfig(
    name="research_prompt",
    version="1.0.0",
    description="Guides autonomous research exploration and deep domain data gathering.",
    model=None,
    temperature=0.5,
    max_tokens=3000,
    system_prompt="""You are an Autonomous Research Investigator.
Execute targeted investigations to identify primary evidence, empirical data points, and foundational literature.
Extract objective claims with explicit source grounding and zero speculative fabrication.""",
    user_template="""Conduct targeted deep research on: '{query}'.
Investigation category: {category}.
Extract key findings, empirical figures, author insights, and core claims.""",
    metadata={"agent": "ResearchAgent", "task": "investigation"},
)
RESEARCH_PROMPT = research_prompt


# 3. Source Evaluation Prompt
source_evaluation_prompt = PromptConfig(
    name="source_evaluation_prompt",
    version="1.0.0",
    description="Evaluates credibility, authority, methodology, and relevance of gathered sources.",
    model=None,
    temperature=0.2,
    max_tokens=1500,
    system_prompt="""You are an Academic Source Verification and Credibility Evaluator.
Evaluate the credibility, publication recency, methodology soundness, and bias of provided sources.
Return a JSON object containing 'score' (0.0 - 1.0), 'authority' ('high' | 'medium' | 'low'), and 'rationale'.""",
    user_template="""Evaluate the following source for research query: '{query}':
Title: {title}
URL: {url}
Snippet/Content: {content}

Return JSON with keys: score (float), authority (string), rationale (string).""",
    metadata={"agent": "EvaluationAgent", "task": "source_scoring"},
)
SOURCE_EVALUATION_PROMPT = source_evaluation_prompt


# 4. Summarization Prompt
summarization_prompt = PromptConfig(
    name="summarization_prompt",
    version="1.0.0",
    description="Distills complex information into high-fidelity summaries maintaining all key facts.",
    model=None,
    temperature=0.3,
    max_tokens=2000,
    system_prompt="""You are an expert summarisation assistant.
Preserve all key facts, numerical figures, and technical nuance without adding unsubstantiated claims.""",
    user_template="""{instruction} Summarize the following text{length_hint}:

{text}""",
    metadata={"service": "LLMService", "task": "summarization"},
)
SUMMARIZATION_PROMPT = summarization_prompt


# 5. Fact Check Prompt
fact_check_prompt = PromptConfig(
    name="fact_check_prompt",
    version="1.0.0",
    description="Audits claims and extracts against source context to eliminate hallucinations.",
    model=None,
    temperature=0.1,
    max_tokens=1500,
    system_prompt="""You are a Strict Fact Verification and Epistemic Audit Agent.
Analyze the following extracted claims and source texts.
Identify any factual inconsistencies, unsupported claims, or outdated statistics.
Return a confidence score between 0.0 and 1.0 along with verified evidence statements.""",
    user_template="""Verify the following extracted evidence against source context:
Evidence Claim: {claim}
Source Context: {context}

Return JSON with keys: 'status' ('verified' | 'questionable' | 'refuted'), 'confidence' (0.0 to 1.0), and 'reasoning'.""",
    metadata={"agent": "FactCheckerAgent", "task": "fact_checking"},
)
FACT_CHECK_PROMPT = fact_check_prompt


# 6. Citation Prompt
citation_prompt = PromptConfig(
    name="citation_prompt",
    version="1.0.0",
    description="Maps claims to exact bibliographic citations and formats bracketed references.",
    model=None,
    temperature=0.2,
    max_tokens=2000,
    system_prompt="""You are an Academic Citation & Evidence Alignment Engine.
Align narrative claims to exact reference numbers [1], [2] matching the source pool.
Ensure each factual assertion has direct, unambiguous attribution.""",
    user_template="""Align text claims with the provided sources:
Text:
{text}

Sources:
{sources_text}

Return JSON with verified bracketed citations and bibliographic references.""",
    metadata={"agent": "CitationAgent", "task": "citation_alignment"},
)
CITATION_PROMPT = citation_prompt


# 7. Report Prompt (Synthesizer)
report_prompt = PromptConfig(
    name="report_prompt",
    version="1.0.0",
    description="Generates publication-grade, multi-section research reports in Markdown.",
    model=None,
    temperature=0.7,
    max_tokens=4000,
    system_prompt="""You are an Executive Research Author.
Synthesize deep, thorough, publication-grade research reports in Markdown.
Structure requirements:
1. # Title
2. ## Executive Summary
3. ## Comprehensive Findings & Deep-Dive Analysis
4. ## Comparative Metrics & Quantitative Breakdown
5. ## Limitations, Risks & Open Challenges
6. ## Strategic Recommendations & Future Horizon
7. ## Sources & Citations

Cite evidence strictly using bracketed indices e.g. [1], [2] referencing the source pool.""",
    user_template="""Research Subject: {query}

Verified Evidence Pool:
{evidence_summary}

Synthesize an exhaustive, publication-grade research report in Markdown.
Include executive summary, comprehensive technical analysis with inline citations [1], [2],
quantitative comparative breakdown, risks, and strategic horizon.""",
    metadata={"agent": "SynthesizerAgent", "task": "report_generation"},
)
REPORT_PROMPT = report_prompt


# 8. Analyst Prompt
analyst_prompt = PromptConfig(
    name="analyst_prompt",
    version="1.0.0",
    description="Extracts patterns, consensus, and divergences across research findings.",
    model=None,
    temperature=0.4,
    max_tokens=2500,
    system_prompt="""You are a Strategic Research Analyst.
Analyze the gathered evidence pool and identify key patterns, consensus findings, and divergent viewpoints.""",
    user_template="""Analyze these empirical claims and synthesize 3-5 core takeaways:
{claims_text}""",
    metadata={"agent": "AnalystAgent", "task": "analysis"},
)
ANALYST_PROMPT_CONFIG = analyst_prompt


# 9. Evidence Extraction Prompt (Day 18)
evidence_extraction_prompt = PromptConfig(
    name="evidence_extraction_prompt",
    version="1.0.0",
    description="Extracts atomic evidence passages and formulates strictly grounded claims with confidence.",
    model=None,
    temperature=0.1,
    max_tokens=2500,
    system_prompt="""You are an Evidence Extraction Specialist.
Your task is to analyze candidate source passages and extract atomic, verifiable claims strictly grounded in the text.
Do NOT fabricate, extrapolate, or generalize beyond what is stated in the passage.

Follow the hierarchy:
Source -> Relevant Passage -> Evidence (exact quote) -> Grounded Claim

For each empirical fact, statistic, or core insight, extract:
- claim: Crisp, objective, standalone claim.
- evidence: Exact passage or verbatim quote supporting the claim.
- confidence: Score between 0.0 and 1.0 reflecting clarity and empirical certainty.
- metrics: Extracted quantitative metrics, dates, percentages, or figures.
- supporting_entities: Named entities, companies, or organizations.
- evidence_type: 'statistic' | 'empirical_finding' | 'quote' | 'policy_event' | 'market_metric'

Respond strictly in valid JSON format:
{
  "claims": [
    {
      "claim": "EV sales in India increased by 45% YoY in 2025.",
      "evidence": "According to industry data, EV sales in India increased by 45% YoY in 2025.",
      "confidence": 0.95,
      "metrics": ["45% YoY", "2025"],
      "supporting_entities": ["India"],
      "evidence_type": "statistic"
    }
  ]
}""",
    user_template="""Extract atomic evidence items from the following passage for research objective '{topic}':

Source Title: {title}
Source Domain: {domain}
Passage Content:
{passage}

Return JSON with key 'claims' containing array of extracted claim objects.""",
    metadata={"module": "EvidenceExtractor", "task": "evidence_extraction"},
)
EVIDENCE_EXTRACTION_PROMPT = evidence_extraction_prompt


# ===================================================================== #
#  Prompt Registry & Helper Functions
# ===================================================================== #

PROMPT_REGISTRY: Dict[str, PromptConfig] = {
    "planner_prompt": planner_prompt,
    "research_prompt": research_prompt,
    "source_evaluation_prompt": source_evaluation_prompt,
    "summarization_prompt": summarization_prompt,
    "fact_check_prompt": fact_check_prompt,
    "citation_prompt": citation_prompt,
    "report_prompt": report_prompt,
    "analyst_prompt": analyst_prompt,
    "evidence_extraction_prompt": evidence_extraction_prompt,
}


def get_prompt(name: str) -> PromptConfig:
    """Retrieve a centralized prompt configuration by name."""
    if name not in PROMPT_REGISTRY:
        raise KeyError(f"Prompt '{name}' not found in registry. Available: {list(PROMPT_REGISTRY.keys())}")
    return PROMPT_REGISTRY[name]


def register_prompt(config: PromptConfig) -> None:
    """Register a new or updated PromptConfig in the central registry."""
    PROMPT_REGISTRY[config.name] = config


def list_prompts() -> Dict[str, Dict[str, Any]]:
    """List metadata and parameters of all registered prompts."""
    return {name: config.to_dict() for name, config in PROMPT_REGISTRY.items()}


# ===================================================================== #
#  Backward Compatibility Aliases
# ===================================================================== #

PLANNER_SYSTEM_PROMPT = planner_prompt.system_prompt
FACT_CHECKER_SYSTEM_PROMPT = fact_check_prompt.system_prompt
SYNTHESIZER_SYSTEM_PROMPT = report_prompt.system_prompt
ANALYST_PROMPT = analyst_prompt.system_prompt
