"""
Agents package providing planner, analyst, fact-checker, synthesizer, web agent, paper agent, and research agent.
"""

from app.agents.planner import PlannerAgent, planner_agent
from app.agents.analyst import AnalystAgent, analyst_agent
from app.agents.fact_checker import FactCheckerAgent, fact_checker_agent
from app.agents.synthesizer import SynthesizerAgent, synthesizer_agent
from app.agents.web_agent import WebAgent, web_agent
from app.agents.paper_agent import PaperAgent, paper_agent
from app.agents.research_agent import ResearchAgent, research_agent

__all__ = [
    "PlannerAgent",
    "planner_agent",
    "AnalystAgent",
    "analyst_agent",
    "FactCheckerAgent",
    "fact_checker_agent",
    "SynthesizerAgent",
    "synthesizer_agent",
    "WebAgent",
    "web_agent",
    "PaperAgent",
    "paper_agent",
    "ResearchAgent",
    "research_agent",
]
