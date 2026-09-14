"""
Tests for Day 73–75 — Research Run Comparison
"""

import pytest
from unittest.mock import AsyncMock, patch

from app.database.models.research import ResearchJob, ResearchStatus
from app.database.models.report import ResearchReport
from app.database.models.comparison import ResearchComparison, ResearchComparisonRequest
from app.database.repositories.research_repo import research_repo
from app.database.repositories.report_repo import report_repo
from app.services.comparison_service import comparison_service


@pytest.fixture(autouse=True)
def clear_stores():
    research_repo._jobs.clear()
    report_repo._reports.clear()
    yield
    research_repo._jobs.clear()
    report_repo._reports.clear()


@pytest.mark.asyncio
async def test_research_comparison_diff_extraction():
    # 1. Create Run A & Report A
    job_a = ResearchJob(
        id="run_a_101",
        query="EV market outlook 2026",
        user_id="user_researcher",
        status=ResearchStatus.COMPLETED,
    )
    await research_repo.create_job(job_a)

    report_a = ResearchReport(
        id="report_a_101",
        research_id="run_a_101",
        title="EV Market Report 2026 - Run A",
        executive_summary="Summary of initial EV report.",
        markdown_content="# EV Market Report 2026 - Run A",
        key_findings=[
            "Tesla leading North America EV delivery target.",
            "Battery supply chain bottlenecks persist.",
        ],
        risks=["High lithium raw material costs", "Grid capacity constraints"],
        opportunities=["Expand charging network incentives"],
        market_analysis="The global EV market valuation reached $400 billion in 2025.",
    )
    await report_repo.create(report_a)

    # 2. Create Run B & Report B (with changes)
    job_b = ResearchJob(
        id="run_b_102",
        query="EV market outlook 2026",
        user_id="user_researcher",
        status=ResearchStatus.COMPLETED,
    )
    await research_repo.create_job(job_b)

    report_b = ResearchReport(
        id="report_b_102",
        research_id="run_b_102",
        title="EV Market Report 2026 - Run B",
        executive_summary="Summary of updated EV report.",
        markdown_content="# EV Market Report 2026 - Run B",
        key_findings=[
            "Tesla leading North America EV delivery target.",
            "Rivian company announced new commercial fleet partnership.",
            "EU passed new EU Battery Directive regulation for recycling compliance.",
        ],
        risks=["High lithium raw material costs", "Cybersecurity risk for smart EV chargers"],
        opportunities=["Expand charging network incentives", "V2G energy storage monetization opportunity"],
        market_analysis="The global EV market valuation projected at $550 billion by 2028 with 22% CAGR.",
    )
    await report_repo.create(report_b)

    # 3. Compare runs
    comparison = await comparison_service.compare("run_a_101", "run_b_102")

    assert comparison.run_a_id == "run_a_101"
    assert comparison.run_b_id == "run_b_102"

    # Check extracted categories
    assert any("Rivian" in c for c in comparison.new_companies)
    assert any("EU Battery Directive" in r or "regulation" in r for r in comparison.new_regulations)
    assert len(comparison.changed_market_estimates) > 0
    assert any("Cybersecurity" in r or "risk" in r for r in comparison.new_risks)
    assert any("V2G" in o or "opportunity" in o for o in comparison.new_opportunities)
    assert any("bottlenecks" in claim for claim in comparison.removed_claims)
