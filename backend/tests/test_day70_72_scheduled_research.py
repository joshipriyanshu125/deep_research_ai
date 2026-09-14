"""
Tests for Days 70–72 — Scheduled Research System
"""

import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch

from app.database.models.scheduled_research import (
    ScheduledResearch,
    ScheduledResearchCreate,
    ScheduledResearchUpdate,
    ScheduledChangeReport,
    ScheduledResearchFrequency,
)
from app.database.models.report import ResearchReport
from app.database.models.research import ResearchJob, ResearchStatus
from app.database.repositories.scheduled_research_repo import scheduled_research_repo
from app.database.repositories.report_repo import report_repo
from app.database.repositories.research_repo import research_repo
from app.agents.scheduled_research_agent import scheduled_research_agent
from app.services.scheduled_research_service import scheduled_research_service
from app.notifications.channels.in_app import in_app_channel, IN_APP_STORE


@pytest.fixture(autouse=True)
def clear_stores():
    scheduled_research_repo._schedules.clear()
    scheduled_research_repo._change_reports.clear()
    IN_APP_STORE.clear()
    yield
    scheduled_research_repo._schedules.clear()
    scheduled_research_repo._change_reports.clear()
    IN_APP_STORE.clear()


@pytest.mark.asyncio
async def test_scheduled_research_model_and_repo():
    # 1. Create schedule model
    schedule = ScheduledResearch(
        user_id="user_test_01",
        query="Research the Indian EV market every Monday and tell me what changed.",
        title="Indian EV Market Weekly Tracker",
        frequency="weekly",
        schedule_day="monday",
    )
    assert schedule.query.startswith("Research the Indian EV market")
    assert schedule.is_active is True

    # 2. Repository Insert & Get
    created = await scheduled_research_repo.create(schedule)
    fetched = await scheduled_research_repo.get(created.id)
    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.title == "Indian EV Market Weekly Tracker"

    # 3. List by user
    user_items = await scheduled_research_repo.list_by_user("user_test_01")
    assert len(user_items) == 1

    # 4. Update
    fetched.title = "Updated EV Tracker"
    await scheduled_research_repo.update(fetched)
    updated = await scheduled_research_repo.get(fetched.id)
    assert updated.title == "Updated EV Tracker"

    # 5. Delete
    deleted = await scheduled_research_repo.delete(fetched.id)
    assert deleted is True
    assert await scheduled_research_repo.get(fetched.id) is None


@pytest.mark.asyncio
async def test_scheduled_research_agent_baseline_and_delta():
    schedule = ScheduledResearch(
        user_id="user_agent_test",
        query="Indian EV market trends 2026",
    )

    current_report = ResearchReport(
        research_id="res_job_curr",
        title="Deep Research Report: Indian EV market trends 2026",
        executive_summary="EV market in India is expanding rapidly led by 2W and 3W adoption.",
        markdown_content="# Indian EV Market Report 2026",
        key_findings=[
            "Tata Motors holds over 65% market share in electric passenger vehicles.",
            "Government extended FAME-III subsidy targets.",
            "Battery swapping stations grew 40% year-over-year.",
        ],
        trends=["Localization of battery cells", "Public charging infrastructure expansion"],
        sources=[],
    )

    # 1. Baseline report test (no previous report)
    baseline_change = await scheduled_research_agent.compare_and_generate_change_report(
        schedule=schedule,
        current_report=current_report,
        previous_report=None,
    )
    assert baseline_change.scheduled_id == schedule.id
    assert baseline_change.previous_report_id is None
    assert "baseline" in baseline_change.summary_of_changes.lower() or "initial" in baseline_change.summary_of_changes.lower()
    assert len(baseline_change.new_findings) > 0

    # 2. Delta comparison test (with previous report)
    previous_report = ResearchReport(
        research_id="res_job_prev",
        title="Deep Research Report: Indian EV market trends 2026",
        executive_summary="Baseline EV market in India.",
        markdown_content="# Previous Indian EV Market Report",
        key_findings=[
            "Tata Motors holds over 65% market share in electric passenger vehicles.",
        ],
        trends=["Localization of battery cells"],
        sources=[],
    )

    delta_change = await scheduled_research_agent.compare_and_generate_change_report(
        schedule=schedule,
        current_report=current_report,
        previous_report=previous_report,
    )
    assert delta_change.previous_report_id == previous_report.id
    assert len(delta_change.new_findings) > 0
    assert "Battery swapping stations grew 40% year-over-year." in delta_change.new_findings


@pytest.mark.asyncio
async def test_scheduled_research_service_execution_flow():
    # Create schedule via service
    req = ScheduledResearchCreate(
        query="Research the Indian EV market every Monday and tell me what changed.",
        title="Indian EV Market Monday Report",
        frequency="weekly",
        schedule_day="monday",
    )
    scheduled = await scheduled_research_service.create_schedule(req, user_id="ev_user_99")
    assert scheduled.id is not None
    assert scheduled.next_run_at is not None

    # Execute scheduled task manually
    change_report = await scheduled_research_service.execute_scheduled_task(scheduled.id)
    assert change_report.scheduled_id == scheduled.id
    assert change_report.user_id == "ev_user_99"
    assert change_report.summary_of_changes != ""

    # Verify notification was dispatched
    in_app_items = await in_app_channel.list_user_notifications("ev_user_99")
    assert len(in_app_items) == 1
    assert "Scheduled Research Update" in in_app_items[0]["title"]

    # Verify schedule state update
    updated_schedule = await scheduled_research_service.get_schedule(scheduled.id)
    assert updated_schedule.last_run_at is not None
    assert len(updated_schedule.history) == 1
    assert updated_schedule.history[0]["change_report_id"] == change_report.id


@pytest.mark.asyncio
async def test_due_schedules_detection():
    now = datetime.now(timezone.utc)
    past = now - timedelta(hours=2)

    # Schedule due in the past
    due_schedule = ScheduledResearch(
        user_id="user_due",
        query="Indian EV market analysis",
        is_active=True,
        next_run_at=past,
    )
    await scheduled_research_repo.create(due_schedule)

    # Schedule due in the future
    future_schedule = ScheduledResearch(
        user_id="user_future",
        query="US EV market analysis",
        is_active=True,
        next_run_at=now + timedelta(days=5),
    )
    await scheduled_research_repo.create(future_schedule)

    due_list = await scheduled_research_repo.list_active_due(now=now)
    assert len(due_list) == 1
    assert due_list[0].id == due_schedule.id
