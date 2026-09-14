from typing import Optional, List, Dict, Any
from app.database.models.report import ResearchReport
from app.database.models.scheduled_research import ScheduledChangeReport, ScheduledResearch
from app.llm.service import get_llm_service
from app.utils.logger import logger


class ScheduledResearchAgent:
    """
    Day 70–72 — Scheduled Research Comparison Agent
    Compares newly completed research report with previous research report
    to generate delta "What Changed" report for periodic tracking.
    """

    def __init__(self):
        self.llm = get_llm_service()

    async def compare_and_generate_change_report(
        self,
        schedule: ScheduledResearch,
        current_report: ResearchReport,
        previous_report: Optional[ResearchReport] = None,
    ) -> ScheduledChangeReport:
        """
        Compare current report against previous report (or generate baseline)
        and construct ScheduledChangeReport.
        """
        if not previous_report:
            # First execution baseline
            summary = (
                f"Initial scheduled research run completed for query: '{schedule.query}'. "
                f"Established baseline analysis with {len(current_report.key_findings)} key findings "
                f"and {len(current_report.sources)} primary sources."
            )
            new_findings = current_report.key_findings[:5]
            market_shifts = current_report.trends[:3] if current_report.trends else [
                f"Baseline established for {schedule.query} tracking."
            ]
            metrics = {
                "current_sources": len(current_report.sources),
                "previous_sources": 0,
                "current_confidence": current_report.confidence,
                "previous_confidence": 0.0,
                "baseline_established": True,
            }
            return ScheduledChangeReport(
                scheduled_id=schedule.id,
                user_id=schedule.user_id,
                query=schedule.query,
                current_research_id=current_report.research_id,
                current_report_id=current_report.id,
                previous_research_id=None,
                previous_report_id=None,
                summary_of_changes=summary,
                new_findings=new_findings,
                market_shifts_or_updates=market_shifts,
                metrics_comparison=metrics,
            )

        # Delta comparison when previous report exists
        prev_findings_set = set(previous_report.key_findings)
        curr_findings = current_report.key_findings

        new_findings = [f for f in curr_findings if f not in prev_findings_set]
        if not new_findings:
            new_findings = curr_findings[:3]

        # LLM comparison if available
        prompt = (
            f"You are a Senior Market Intelligence Analyst.\n"
            f"Compare the following two research reports on the topic: '{schedule.query}' and detail WHAT CHANGED.\n\n"
            f"PREVIOUS REPORT SUMMARY:\n{previous_report.executive_summary}\n\n"
            f"PREVIOUS KEY FINDINGS:\n" + "\n".join([f"- {kf}" for kf in previous_report.key_findings]) + "\n\n"
            f"CURRENT REPORT SUMMARY:\n{current_report.executive_summary}\n\n"
            f"CURRENT KEY FINDINGS:\n" + "\n".join([f"- {kf}" for kf in current_report.key_findings]) + "\n\n"
            f"Provide a concise summary highlighting key market changes, new product launches, regulatory shifts, "
            f"or numerical updates between the two reports."
        )

        try:
            summary = await self.llm.execute_prompt(prompt)
        except Exception as e:
            logger.warning(f"[ScheduledResearchAgent] LLM comparison failed, fallback to heuristic: {e}")
            summary = (
                f"Updated research completed for query: '{schedule.query}'. "
                f"Identified {len(new_findings)} new/updated findings compared to the previous run on "
                f"{previous_report.created_at.strftime('%Y-%m-%d')}."
            )

        market_shifts = current_report.trends[:4]
        metrics = {
            "current_sources": len(current_report.sources),
            "previous_sources": len(previous_report.sources),
            "current_confidence": current_report.confidence,
            "previous_confidence": previous_report.confidence,
            "delta_findings_count": len(new_findings),
        }

        return ScheduledChangeReport(
            scheduled_id=schedule.id,
            user_id=schedule.user_id,
            query=schedule.query,
            current_research_id=current_report.research_id,
            current_report_id=current_report.id,
            previous_research_id=previous_report.research_id,
            previous_report_id=previous_report.id,
            summary_of_changes=summary,
            new_findings=new_findings,
            market_shifts_or_updates=market_shifts,
            metrics_comparison=metrics,
        )


scheduled_research_agent = ScheduledResearchAgent()
