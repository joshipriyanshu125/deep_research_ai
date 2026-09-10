"""
Day 11 — Task Management Tests
Covers: model validation, status transitions, repository (in-memory),
        service layer, and API endpoints via httpx AsyncClient.
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from app.database.models.task import (
    ResearchTaskRecord,
    TaskStatus,
    TaskType,
    TaskCreateRequest,
    TaskBulkCreateRequest,
)
from app.database.repositories.task_repo import TaskRepository
from app.services.task_service import TaskService
from app.main import app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def fresh_repo() -> TaskRepository:
    """Return a clean in-memory TaskRepository for isolation."""
    return TaskRepository()


@pytest.fixture
def fresh_service(fresh_repo) -> TaskService:
    """Return a TaskService wired to the in-memory fresh_repo."""
    svc = TaskService()
    # Monkey-patch the repo reference inside service for test isolation
    import app.services.task_service as svc_module
    original_repo = svc_module.task_repo
    svc_module.task_repo = fresh_repo
    yield svc
    svc_module.task_repo = original_repo


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# Model Tests
# ---------------------------------------------------------------------------

class TestResearchTaskRecord:
    def test_default_values(self):
        task = ResearchTaskRecord(research_id="r1", question="What is AI?")
        assert task.status == TaskStatus.PENDING
        assert task.type == TaskType.WEB_SEARCH
        assert task.priority == 1
        assert task.attempts == 0
        assert task.assigned_agent == "web_research_agent"
        assert task.id is not None

    def test_alias_id(self):
        """_id alias should be accepted and round-trip correctly."""
        task = ResearchTaskRecord(**{
            "_id": "custom-id",
            "research_id": "r1",
            "question": "test",
        })
        assert task.id == "custom-id"

    def test_valid_status_transitions(self):
        task = ResearchTaskRecord(research_id="r1", question="q")
        # pending → running ✓
        assert task.can_transition_to(TaskStatus.RUNNING) is True
        # pending → cancelled ✓
        assert task.can_transition_to(TaskStatus.CANCELLED) is True
        # pending → completed ✗
        assert task.can_transition_to(TaskStatus.COMPLETED) is False
        # pending → failed ✗
        assert task.can_transition_to(TaskStatus.FAILED) is False

    def test_running_transitions(self):
        task = ResearchTaskRecord(research_id="r1", question="q", status=TaskStatus.RUNNING)
        assert task.can_transition_to(TaskStatus.COMPLETED) is True
        assert task.can_transition_to(TaskStatus.FAILED) is True
        assert task.can_transition_to(TaskStatus.CANCELLED) is True
        assert task.can_transition_to(TaskStatus.PENDING) is False

    def test_terminal_states_block_transitions(self):
        for terminal in [TaskStatus.COMPLETED, TaskStatus.CANCELLED]:
            task = ResearchTaskRecord(research_id="r1", question="q", status=terminal)
            assert task.is_terminal() is True
            for any_status in TaskStatus.ALL:
                assert task.can_transition_to(any_status) is False

    def test_is_retryable(self):
        task = ResearchTaskRecord(
            research_id="r1", question="q",
            status=TaskStatus.FAILED, attempts=1, max_attempts=3
        )
        assert task.is_retryable() is True

    def test_not_retryable_when_max_attempts_reached(self):
        task = ResearchTaskRecord(
            research_id="r1", question="q",
            status=TaskStatus.FAILED, attempts=3, max_attempts=3
        )
        assert task.is_retryable() is False


# ---------------------------------------------------------------------------
# TaskStatus Class Tests
# ---------------------------------------------------------------------------

class TestTaskStatus:
    def test_all_statuses_present(self):
        expected = {"pending", "running", "completed", "failed", "retrying", "cancelled"}
        assert TaskStatus.ALL == expected

    def test_can_transition_returns_false_for_unknown(self):
        assert TaskStatus.can_transition("pending", "unknown_status") is False

    def test_is_terminal(self):
        assert TaskStatus.is_terminal(TaskStatus.COMPLETED) is True
        assert TaskStatus.is_terminal(TaskStatus.CANCELLED) is True
        assert TaskStatus.is_terminal(TaskStatus.PENDING) is False
        assert TaskStatus.is_terminal(TaskStatus.RUNNING) is False


# ---------------------------------------------------------------------------
# Repository Tests (in-memory)
# ---------------------------------------------------------------------------

class TestTaskRepository:
    @pytest.mark.asyncio
    async def test_create_and_get(self, fresh_repo):
        task = ResearchTaskRecord(research_id="r1", question="Q1")
        await fresh_repo.create_task(task)
        fetched = await fresh_repo.get_task(task.id)
        assert fetched is not None
        assert fetched.id == task.id
        assert fetched.question == "Q1"

    @pytest.mark.asyncio
    async def test_get_nonexistent_returns_none(self, fresh_repo):
        result = await fresh_repo.get_task("nonexistent-id")
        assert result is None

    @pytest.mark.asyncio
    async def test_list_tasks_by_research(self, fresh_repo):
        for i in range(3):
            await fresh_repo.create_task(
                ResearchTaskRecord(research_id="r1", question=f"Q{i}")
            )
        await fresh_repo.create_task(
            ResearchTaskRecord(research_id="r2", question="Other")
        )
        tasks = await fresh_repo.list_tasks_by_research("r1")
        assert len(tasks) == 3

    @pytest.mark.asyncio
    async def test_list_tasks_with_status_filter(self, fresh_repo):
        t1 = ResearchTaskRecord(research_id="r1", question="Q1", status=TaskStatus.PENDING)
        t2 = ResearchTaskRecord(research_id="r1", question="Q2", status=TaskStatus.COMPLETED)
        await fresh_repo.create_task(t1)
        await fresh_repo.create_task(t2)

        pending = await fresh_repo.list_tasks_by_research("r1", TaskStatus.PENDING)
        assert len(pending) == 1
        assert pending[0].status == TaskStatus.PENDING

    @pytest.mark.asyncio
    async def test_update_task_status(self, fresh_repo):
        task = ResearchTaskRecord(research_id="r1", question="Q")
        await fresh_repo.create_task(task)
        updated = await fresh_repo.update_task_status(
            task.id, TaskStatus.RUNNING
        )
        assert updated.status == TaskStatus.RUNNING
        assert updated.started_at is not None

    @pytest.mark.asyncio
    async def test_increment_attempts(self, fresh_repo):
        task = ResearchTaskRecord(research_id="r1", question="Q")
        await fresh_repo.create_task(task)
        updated = await fresh_repo.increment_attempts(task.id)
        assert updated.attempts == 1

    @pytest.mark.asyncio
    async def test_cancel_pending_tasks(self, fresh_repo):
        for _ in range(3):
            await fresh_repo.create_task(
                ResearchTaskRecord(research_id="r1", question="Q", status=TaskStatus.PENDING)
            )
        # One already completed — should not be cancelled
        await fresh_repo.create_task(
            ResearchTaskRecord(research_id="r1", question="done", status=TaskStatus.COMPLETED)
        )
        count = await fresh_repo.cancel_pending_tasks("r1")
        assert count == 3

    @pytest.mark.asyncio
    async def test_get_task_counts(self, fresh_repo):
        statuses = [TaskStatus.PENDING, TaskStatus.RUNNING, TaskStatus.COMPLETED, TaskStatus.FAILED]
        for s in statuses:
            await fresh_repo.create_task(
                ResearchTaskRecord(research_id="r1", question="Q", status=s)
            )
        counts = await fresh_repo.get_task_counts("r1")
        assert counts[TaskStatus.PENDING] == 1
        assert counts[TaskStatus.COMPLETED] == 1
        assert counts[TaskStatus.RUNNING] == 1

    @pytest.mark.asyncio
    async def test_delete_task(self, fresh_repo):
        task = ResearchTaskRecord(research_id="r1", question="Q")
        await fresh_repo.create_task(task)
        deleted = await fresh_repo.delete_task(task.id)
        assert deleted is True
        assert await fresh_repo.get_task(task.id) is None


# ---------------------------------------------------------------------------
# Service Layer Tests
# ---------------------------------------------------------------------------

class TestTaskService:
    @pytest.mark.asyncio
    async def test_create_task(self, fresh_service):
        req = TaskCreateRequest(
            research_id="r1",
            question="What are the risks?",
            type=TaskType.WEB_SEARCH,
        )
        task = await fresh_service.create_task(req)
        assert task.research_id == "r1"
        assert task.status == TaskStatus.PENDING
        assert task.type == TaskType.WEB_SEARCH

    @pytest.mark.asyncio
    async def test_create_task_invalid_type(self, fresh_service):
        from fastapi import HTTPException
        req = TaskCreateRequest(research_id="r1", question="Q", type="invalid_type")
        with pytest.raises(HTTPException) as exc:
            await fresh_service.create_task(req)
        assert exc.value.status_code == 422

    @pytest.mark.asyncio
    async def test_get_task_not_found(self, fresh_service):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            await fresh_service.get_task("ghost-id")
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_transition_status_valid(self, fresh_service):
        req = TaskCreateRequest(research_id="r1", question="Q")
        task = await fresh_service.create_task(req)
        updated = await fresh_service.transition_status(task.id, TaskStatus.RUNNING)
        assert updated.status == TaskStatus.RUNNING

    @pytest.mark.asyncio
    async def test_transition_status_invalid(self, fresh_service):
        from fastapi import HTTPException
        req = TaskCreateRequest(research_id="r1", question="Q")
        task = await fresh_service.create_task(req)
        # pending → completed is not allowed
        with pytest.raises(HTTPException) as exc:
            await fresh_service.transition_status(task.id, TaskStatus.COMPLETED)
        assert exc.value.status_code == 422

    @pytest.mark.asyncio
    async def test_cancel_task(self, fresh_service):
        req = TaskCreateRequest(research_id="r1", question="Q")
        task = await fresh_service.create_task(req)
        cancelled = await fresh_service.cancel_task(task.id)
        assert cancelled.status == TaskStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_cancel_terminal_task_raises(self, fresh_service):
        from fastapi import HTTPException
        req = TaskCreateRequest(research_id="r1", question="Q")
        task = await fresh_service.create_task(req)
        await fresh_service.cancel_task(task.id)  # cancel once
        # cancel again — already terminal
        with pytest.raises(HTTPException) as exc:
            await fresh_service.cancel_task(task.id)
        assert exc.value.status_code == 422

    @pytest.mark.asyncio
    async def test_retry_task(self, fresh_service):
        req = TaskCreateRequest(research_id="r1", question="Q", max_attempts=3)
        task = await fresh_service.create_task(req)
        # Move to running, then failed
        await fresh_service.transition_status(task.id, TaskStatus.RUNNING)
        await fresh_service.transition_status(task.id, TaskStatus.FAILED, error_message="timeout")
        retried = await fresh_service.retry_task(task.id)
        assert retried.status == TaskStatus.RETRYING
        assert retried.attempts == 1

    @pytest.mark.asyncio
    async def test_retry_exhausted_raises(self, fresh_service):
        from fastapi import HTTPException
        req = TaskCreateRequest(research_id="r1", question="Q", max_attempts=1)
        task = await fresh_service.create_task(req)
        await fresh_service.transition_status(task.id, TaskStatus.RUNNING)
        # Manually set attempts to max
        import app.services.task_service as svc_module
        t = await svc_module.task_repo.get_task(task.id)
        t.attempts = 1
        await svc_module.task_repo.update_task(t)
        await fresh_service.transition_status(task.id, TaskStatus.FAILED)

        with pytest.raises(HTTPException) as exc:
            await fresh_service.retry_task(task.id)
        assert exc.value.status_code == 422

    @pytest.mark.asyncio
    async def test_get_task_stats(self, fresh_service):
        for _ in range(2):
            req = TaskCreateRequest(research_id="stats-r1", question="Q")
            await fresh_service.create_task(req)

        stats = await fresh_service.get_task_stats("stats-r1")
        assert stats.research_id == "stats-r1"
        assert stats.total == 2
        assert stats.pending == 2
        assert stats.completion_rate == 0.0

    @pytest.mark.asyncio
    async def test_create_tasks_bulk(self, fresh_service):
        tasks_data = [
            TaskCreateRequest(research_id="r1", question=f"Q{i}", type=TaskType.WEB_SEARCH)
            for i in range(4)
        ]
        created = await fresh_service.create_tasks_bulk("r1", tasks_data)
        assert len(created) == 4
        assert all(t.research_id == "r1" for t in created)


# ---------------------------------------------------------------------------
# API Endpoint Tests
# ---------------------------------------------------------------------------

class TestTaskAPI:
    @pytest.mark.asyncio
    async def test_create_task_endpoint(self, client):
        payload = {
            "research_id": "api-r1",
            "question": "What is the market size?",
            "type": "web_search",
            "priority": 1,
            "assigned_agent": "web_research_agent",
        }
        resp = await client.post("/api/v1/tasks/", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["research_id"] == "api-r1"
        assert data["status"] == "pending"
        assert data["type"] == "web_search"

    @pytest.mark.asyncio
    async def test_get_task_endpoint(self, client):
        create_resp = await client.post("/api/v1/tasks/", json={
            "research_id": "api-r2",
            "question": "Q",
            "type": "web_search",
        })
        task_id = create_resp.json()["_id"]
        resp = await client.get(f"/api/v1/tasks/{task_id}")
        assert resp.status_code == 200
        assert resp.json()["_id"] == task_id

    @pytest.mark.asyncio
    async def test_get_task_not_found(self, client):
        resp = await client.get("/api/v1/tasks/does-not-exist")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_list_tasks_endpoint(self, client):
        for i in range(3):
            await client.post("/api/v1/tasks/", json={
                "research_id": "api-r3",
                "question": f"Q{i}",
                "type": "web_search",
            })
        resp = await client.get("/api/v1/tasks/research/api-r3")
        assert resp.status_code == 200
        assert len(resp.json()) >= 3

    @pytest.mark.asyncio
    async def test_update_status_endpoint(self, client):
        create_resp = await client.post("/api/v1/tasks/", json={
            "research_id": "api-r4",
            "question": "Q",
            "type": "web_search",
        })
        task_id = create_resp.json()["_id"]
        resp = await client.patch(
            f"/api/v1/tasks/{task_id}/status",
            json={"status": "running"}
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "running"

    @pytest.mark.asyncio
    async def test_invalid_transition_endpoint(self, client):
        create_resp = await client.post("/api/v1/tasks/", json={
            "research_id": "api-r5",
            "question": "Q",
            "type": "web_search",
        })
        task_id = create_resp.json()["_id"]
        # pending → completed is invalid
        resp = await client.patch(
            f"/api/v1/tasks/{task_id}/status",
            json={"status": "completed"}
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_cancel_endpoint(self, client):
        create_resp = await client.post("/api/v1/tasks/", json={
            "research_id": "api-r6",
            "question": "Q",
            "type": "web_search",
        })
        task_id = create_resp.json()["_id"]
        resp = await client.post(f"/api/v1/tasks/{task_id}/cancel")
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"

    @pytest.mark.asyncio
    async def test_bulk_create_endpoint(self, client):
        payload = {
            "research_id": "api-r7",
            "tasks": [
                {"research_id": "api-r7", "question": f"Q{i}", "type": "web_search"}
                for i in range(5)
            ]
        }
        resp = await client.post("/api/v1/tasks/bulk", json=payload)
        assert resp.status_code == 201
        assert len(resp.json()) == 5

    @pytest.mark.asyncio
    async def test_stats_endpoint(self, client):
        for _ in range(3):
            await client.post("/api/v1/tasks/", json={
                "research_id": "api-stats",
                "question": "Q",
                "type": "web_search",
            })
        resp = await client.get("/api/v1/tasks/research/api-stats/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["research_id"] == "api-stats"
        assert data["total"] >= 3
        assert "pending" in data
        assert "completion_rate" in data
