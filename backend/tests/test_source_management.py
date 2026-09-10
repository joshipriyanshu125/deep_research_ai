import hashlib
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.database.models.source import (
    Source,
    SourceType,
    ResearchSource,
    compute_content_hash,
    extract_domain_from_url,
)
from app.database.repositories.source_repo import SourceRepository, source_repo
from app.database.mongodb import init_db_collections


client = TestClient(app)


class TestSourceModelAndTypes:
    def test_all_source_types_supported(self):
        expected_types = [
            "news", "government", "company", "academic",
            "financial", "blog", "forum", "social", "other"
        ]
        for st in expected_types:
            src = Source(
                research_id="res-1",
                url=f"https://example.com/{st}",
                title=f"{st} source",
                source_type=st,
            )
            assert src.source_type == st

    def test_content_hash_auto_generation(self):
        content = "India electric vehicle policy analysis and subsidies roadmap 2026."
        expected_hash = hashlib.sha256(content.strip().encode("utf-8")).hexdigest()

        src = Source(
            research_id="res-123",
            url="https://pib.gov.in/press/ev",
            title="EV Policy 2026",
            content=content,
            source_type=SourceType.GOVERNMENT,
        )

        assert src.content_hash == expected_hash
        assert src.content == content
        assert src.clean_text == content  # Synced alias
        assert src.domain == "pib.gov.in"
        assert src.language == "en"
        assert src.credibility_score == 0.8

    def test_field_synchronization_and_aliases(self):
        src = Source(
            source_id="custom-src-id-123",
            research_id="res-456",
            url="https://reuters.com/markets/ev",
            title="Reuters EV Market",
            clean_text="Clean text body of the article",
            publication_date="2026-03-01",
            retrieved_date=datetime(2026, 3, 1, 12, 0, 0),
            source_type=SourceType.NEWS,
            relevance_score=0.92,
        )

        assert src.source_id == "custom-src-id-123"
        assert src.id == "custom-src-id-123"
        assert src.content == "Clean text body of the article"
        assert src.published_at == "2026-03-01"
        assert src.retrieved_at == datetime(2026, 3, 1, 12, 0, 0)
        assert src.domain == "reuters.com"
        assert len(src.content_hash) == 64


class TestContentHashCalculation:
    def test_deterministic_sha256_hash(self):
        text = "Uniform text for hash verification."
        h1 = compute_content_hash(text)
        h2 = compute_content_hash(text)
        assert h1 == h2
        assert len(h1) == 64

    def test_different_content_produces_different_hash(self):
        h1 = compute_content_hash("Content version A")
        h2 = compute_content_hash("Content version B")
        assert h1 != h2


class TestCollectionInitialization:
    @pytest.mark.asyncio
    async def test_init_creates_research_sources_if_missing(self):
        mock_db = MagicMock()
        mock_db.list_collection_names = AsyncMock(return_value=["users", "research_jobs"])
        mock_db.create_collection = AsyncMock()
        mock_sources_col = MagicMock()
        mock_sources_col.create_index = AsyncMock()
        mock_tasks_col = MagicMock()
        mock_tasks_col.create_index = AsyncMock()

        mock_db.__getitem__.side_effect = lambda name: mock_sources_col if name == "research_sources" else mock_tasks_col

        await init_db_collections(mock_db)
        mock_db.create_collection.assert_any_call("research_sources")
        assert mock_sources_col.create_index.call_count >= 5

    @pytest.mark.asyncio
    async def test_init_skips_creation_if_already_present(self):
        mock_db = MagicMock()
        mock_db.list_collection_names = AsyncMock(return_value=["research_sources", "research_tasks"])
        mock_db.create_collection = AsyncMock()
        mock_col = MagicMock()
        mock_col.create_index = AsyncMock()
        mock_db.__getitem__.return_value = mock_col

        await init_db_collections(mock_db)
        # Should not call create_collection for research_sources since it already exists
        calls = [c[0][0] for c in mock_db.create_collection.call_args_list if c[0]]
        assert "research_sources" not in calls


class TestSourceRepositoryCRUD:
    @pytest.mark.asyncio
    async def test_create_get_and_count_source(self):
        repo = SourceRepository()
        src = Source(
            research_id="res-crud-1",
            url="https://worldbank.org/report/ev",
            title="World Bank EV Financing",
            content="Detailed financial report on EV infrastructure.",
            source_type=SourceType.FINANCIAL,
            language="en",
            relevance_score=0.95,
        )

        saved = await repo.create_source(src)
        assert saved.source_id == src.source_id

        fetched = await repo.get_source(src.source_id)
        assert fetched is not None
        assert fetched.title == "World Bank EV Financing"
        assert fetched.source_type == "financial"

        count = await repo.count_sources("res-crud-1")
        assert count == 1

    @pytest.mark.asyncio
    async def test_duplicate_detection_by_content_hash(self):
        repo = SourceRepository()
        body = "Identical research findings across two separate URL feeds."
        s1 = Source(
            research_id="res-dup-check",
            url="https://site1.com/a",
            title="Doc A",
            content=body,
        )
        await repo.create_source(s1)

        # Check hash lookup
        target_hash = s1.content_hash
        existing = await repo.find_by_content_hash("res-dup-check", target_hash)
        assert existing is not None
        assert existing.url == "https://site1.com/a"

        # Not found for different research_id
        other_res = await repo.find_by_content_hash("res-other", target_hash)
        assert other_res is None

    @pytest.mark.asyncio
    async def test_filtering_sources(self):
        repo = SourceRepository()
        res_id = "res-filtering-test"
        
        sources = [
            Source(research_id=res_id, url="https://gov.in/policy", title="Gov Policy", source_type=SourceType.GOVERNMENT, relevance_score=0.9, language="en"),
            Source(research_id=res_id, url="https://bloomberg.com/ev", title="EV Finance", source_type=SourceType.FINANCIAL, relevance_score=0.85, language="en"),
            Source(research_id=res_id, url="https://nature.com/paper", title="Battery Science", source_type=SourceType.ACADEMIC, relevance_score=0.98, language="en"),
            Source(research_id=res_id, url="https://reddit.com/r/ev", title="Forum Discussion", source_type=SourceType.FORUM, relevance_score=0.4, language="en"),
        ]
        for s in sources:
            await repo.create_source(s)

        # Filter by source_type
        academic_results = await repo.get_sources_by_research(res_id, source_type="academic")
        assert len(academic_results) == 1
        assert academic_results[0].title == "Battery Science"

        # Filter by min_relevance
        high_rel = await repo.get_sources_by_research(res_id, min_relevance=0.8)
        assert len(high_rel) == 3

        # Filter by domain
        bloomberg_res = await repo.get_sources_by_research(res_id, domain="bloomberg.com")
        assert len(bloomberg_res) == 1

    @pytest.mark.asyncio
    async def test_delete_source(self):
        repo = SourceRepository()
        src = Source(
            research_id="res-delete-test",
            url="https://temp.org/doc",
            title="Temporary Document",
            content="Temporary content",
        )
        await repo.create_source(src)
        assert await repo.get_source(src.source_id) is not None

        deleted = await repo.delete_source(src.source_id)
        assert deleted is True
        assert await repo.get_source(src.source_id) is None


class TestSourcesAPIEndpoints:
    @pytest.mark.asyncio
    async def test_api_create_and_get_source(self):
        payload = {
            "research_id": "api-res-123",
            "url": "https://iea.org/reports/ev-2026",
            "title": "Global EV Outlook 2026",
            "content": "IEA Global EV Outlook report content...",
            "source_type": "government",
            "language": "en",
            "relevance_score": 0.95,
            "credibility_score": 0.9,
        }

        # 1. POST /api/v1/sources/
        res_create = client.post("/api/v1/sources/", json=payload)
        assert res_create.status_code == 201
        data = res_create.json()
        assert data["title"] == "Global EV Outlook 2026"
        assert data["domain"] == "iea.org"
        assert data["source_type"] == "government"
        assert "content_hash" in data
        source_id = data["source_id"]

        # 2. GET /api/v1/sources/{source_id}
        res_get = client.get(f"/api/v1/sources/{source_id}")
        assert res_get.status_code == 200
        assert res_get.json()["source_id"] == source_id

        # 3. GET /api/v1/sources/research/{research_id} with filter
        res_list = client.get(f"/api/v1/sources/research/api-res-123?source_type=government")
        assert res_list.status_code == 200
        assert len(res_list.json()) >= 1

        # 4. DELETE /api/v1/sources/{source_id}
        res_del = client.get(f"/api/v1/sources/invalid-id-xyz")
        assert res_del.status_code == 404

        res_delete = client.delete(f"/api/v1/sources/{source_id}")
        assert res_delete.status_code == 200
