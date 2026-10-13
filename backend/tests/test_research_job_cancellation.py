"""Offline regressions for the top-level research Stop contract."""

import pytest

from app.database.mongodb import db_manager
from app.database.models.research import ResearchJob, ResearchStatus
from app.database.repositories.research_repo import research_repo


@pytest.mark.asyncio
async def test_cancelled_job_cannot_be_overwritten_by_a_late_checkpoint():
    job = ResearchJob(id="cancel-regression", user_id="anonymous", query="cancel me")
    old_connection = db_manager.is_connected
    old_db = db_manager.db
    db_manager.is_connected = False
    db_manager.db = None
    try:
        await research_repo.create_job(job)
        stale = await research_repo.get_job(job.id)
        cancelled = await research_repo.cancel_job(job.id)

        assert cancelled.status == ResearchStatus.CANCELLED
        assert cancelled.progress_percentage == 0

        stale.status = ResearchStatus.SEARCHING
        with pytest.raises(__import__("asyncio").CancelledError):
            await research_repo.update_job(stale)

        current = await research_repo.get_job(job.id)
        assert current.status == ResearchStatus.CANCELLED
    finally:
        research_repo._jobs.pop(job.id, None)
        db_manager.is_connected = old_connection
        db_manager.db = old_db
