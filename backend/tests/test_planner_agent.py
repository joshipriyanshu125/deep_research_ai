import pytest
from app.agents.planner import PlannerAgent, planner_agent
from app.database.models.research import ResearchPlan, ResearchTask
from app.research.planner import research_planner


@pytest.mark.asyncio
async def test_planner_agent_indian_ev_market_plan():
    agent = PlannerAgent()
    query = "Analyze Indian EV market and identify investment opportunities."
    plan: ResearchPlan = await agent.create_plan(query, depth=2, breadth=5)

    assert isinstance(plan, ResearchPlan)
    assert plan.research_goal is not None
    assert len(plan.research_goal) > 0
    assert len(plan.tasks) >= 3

    # Check task structure
    for task in plan.tasks:
        assert isinstance(task, ResearchTask)
        assert task.id.startswith("task_")
        assert task.question is not None
        assert len(task.question) > 0
        assert task.category in ["web", "academic", "market"]
        assert task.query is not None

    # Check that key questions are addressed in the planned tasks
    all_questions = " ".join([t.question.lower() for t in plan.tasks])
    assert "market" in all_questions or "size" in all_questions or "growth" in all_questions or "companies" in all_questions


@pytest.mark.asyncio
async def test_planner_agent_plan_research_tasks_list():
    tasks = await planner_agent.plan_research_tasks("Quantum Computing Architectures", depth=1, breadth=3)
    assert isinstance(tasks, list)
    assert len(tasks) >= 1
    assert all(isinstance(t, ResearchTask) for t in tasks)
    assert all(t.query for t in tasks)


@pytest.mark.asyncio
async def test_research_planner_wrapper():
    plan = await research_planner.create_research_plan("Autonomous Multi-Agent AI", depth=2, breadth=3)
    assert isinstance(plan, ResearchPlan)
    assert plan.research_goal is not None
    assert len(plan.tasks) > 0

    tasks = await research_planner.create_plan("Autonomous Multi-Agent AI", depth=2, breadth=3)
    assert isinstance(tasks, list)
    assert len(tasks) > 0
