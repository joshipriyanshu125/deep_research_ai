"""Offline regressions for restarting a stalled deep-research pipeline.

A research run that dies mid-pipeline (backend restart, crash, nodemon reload)
used to keep its in-flight status forever, so the polling UI appeared stalled.
"""

from types import SimpleNamespace

import pytest

from app.database.mongodb import db_manager
from app.database.models.research import ResearchJob, ResearchStatus
from app.database.models.source import Source, normalize_url
from app.research.orchestrator import research_orchestrator
from app.workers.research_worker import research_worker


class _Cursor:
    def __init__(self, docs):
        self._docs = list(docs)

    def __aiter__(self):
        self._iter = iter(self._docs)
        return self

    async def __anext__(self):
        try:
            return next(self._iter)
        except StopIteration:
            raise StopAsyncIteration


class _JobsCollection:
    def __init__(self, docs, matched=1):
        self.docs = docs
        self.matched = matched
        self.last_find_query = None
        self.replace_calls = []

    def find(self, query):
        self.last_find_query = query
        return _Cursor(self.docs)

    async def replace_one(self, flt, update):
        self.replace_calls.append((flt, update))
        return SimpleNamespace(matched_count=self.matched)


def _fake_db(monkeypatch, docs, matched=1):
    collection = _JobsCollection(docs, matched=matched)
    monkeypatch.setattr(db_manager, "is_connected", True)
    monkeypatch.setattr(db_manager, "db", SimpleNamespace(research_jobs=collection))
    return collection


@pytest.mark.asyncio
async def test_interrupted_jobs_are_reset_to_pending_and_requeued(monkeypatch):
    interrupted = ResearchJob(
        id="interrupted-search", user_id="anonymous", query="stalled run",
        status=ResearchStatus.SEARCHING,
    )
    queued = ResearchJob(id="lost-queue", user_id="anonymous", query="lost run")
    collection = _fake_db(monkeypatch, [interrupted.model_dump(), queued.model_dump()])

    enqueued = []

    async def record_enqueue(job):
        enqueued.append(job.id)

    monkeypatch.setattr(research_worker, "enqueue_job", record_enqueue)

    recovered = await research_worker.recover_interrupted_jobs()

    assert recovered == 2
    assert enqueued == ["interrupted-search", "lost-queue"]

    # Pending, in-flight, and legacy statuses are all searched for.
    statuses = set(collection.last_find_query["status"]["$in"])
    assert statuses == set(research_worker.RECOVERABLE_STATUSES)

    # Only the in-flight job is rewritten; the already-queued job is not.
    assert len(collection.replace_calls) == 1
    flt, replacement = collection.replace_calls[0]
    assert flt["id"] == "interrupted-search"
    assert replacement["status"] == ResearchStatus.PENDING
    assert replacement["progress_percentage"] == 0


@pytest.mark.asyncio
async def test_recovered_job_is_skipped_when_it_reached_a_terminal_state(monkeypatch):
    """A run that completed while we were reading it must not be resurrected."""
    doc = ResearchJob(
        id="finished-just-now", user_id="anonymous", query="finished run",
        status=ResearchStatus.SYNTHESIZING,
    )
    collection = _fake_db(monkeypatch, [doc.model_dump()], matched=0)

    enqueued = []

    async def record_enqueue(job):
        enqueued.append(job.id)

    monkeypatch.setattr(research_worker, "enqueue_job", record_enqueue)

    recovered = await research_worker.recover_interrupted_jobs()

    assert recovered == 0
    assert enqueued == []
    assert len(collection.replace_calls) == 1


@pytest.mark.asyncio
async def test_recovery_is_a_noop_without_a_database(monkeypatch):
    monkeypatch.setattr(db_manager, "is_connected", False)
    monkeypatch.setattr(db_manager, "db", None)

    assert await research_worker.recover_interrupted_jobs() == 0


def _source(source_id: str, url: str, title: str = "resumed source") -> Source:
    return Source(id=source_id, research_id="resumed-run", url=url, title=title, content="body")


def test_resumed_run_does_not_duplicate_urls_from_the_interrupted_pass():
    """Sources persisted before the restart are already in existing_sources;
    re-finding them during the resumed search must not duplicate them."""
    persisted = _source("src-old", "https://example.com/report")
    refound = _source("src-new", "https://example.com/report/")
    fresh = _source("src-fresh", "https://other.org/article")

    merged = research_orchestrator._merge_unique_sources([persisted], [refound, fresh])

    urls = [normalize_url(s.url or "") for s in merged]
    assert len(merged) == 2
    assert len(set(urls)) == 2
    # First-wins: the already-persisted source survives, keeping its id.
    assert [s.id for s in merged if normalize_url(s.url or "") == normalize_url("https://example.com/report")] == ["src-old"]


def test_merge_keeps_sources_without_urls_distinct_by_id():
    no_url_a = _source("src-a", "", title="untitled a")
    no_url_b = _source("src-b", "", title="untitled b")

    merged = research_orchestrator._merge_unique_sources([no_url_a], [no_url_b])

    assert [s.id for s in merged] == ["src-a", "src-b"]
