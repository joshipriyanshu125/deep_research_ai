import pytest
from datetime import datetime
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.database.models.source import (
    Source,
    SourceType,
    ProcessedSearchResult,
    extract_domain_from_url,
)
from app.search.result_processor import (
    SearchResultProcessor,
    search_result_processor,
    normalize_publication_date,
)
from app.agents.web_agent import DeepWebResearchAgent
from app.database.repositories.research_repo import research_repo


client = TestClient(app)


class TestDomainExtraction:
    def test_standard_https_url(self):
        assert extract_domain_from_url("https://techcrunch.com/2026/02/ev-growth") == "techcrunch.com"

    def test_www_prefix_removed(self):
        assert extract_domain_from_url("https://www.reuters.com/business/energy") == "reuters.com"
        assert extract_domain_from_url("http://www.google.com") == "google.com"

    def test_subdomains_preserved(self):
        assert extract_domain_from_url("https://niti.gov.in/reports/ev-policy") == "niti.gov.in"
        assert extract_domain_from_url("https://scholar.google.com/citations") == "scholar.google.com"

    def test_port_removal(self):
        assert extract_domain_from_url("http://localhost:8000/api/v1/search") == "localhost"
        assert extract_domain_from_url("https://example.org:8443/test") == "example.org"

    def test_url_without_scheme(self):
        assert extract_domain_from_url("bloomberg.com/news/articles") == "bloomberg.com"

    def test_empty_and_invalid_urls(self):
        assert extract_domain_from_url("") == ""
        assert extract_domain_from_url(None) == ""


class TestDateNormalization:
    def test_iso_date_strings(self):
        assert normalize_publication_date("2026-02-15") == "2026-02-15"
        assert normalize_publication_date("2026/02/15") == "2026-02-15"

    def test_dmy_format(self):
        assert normalize_publication_date("15-02-2026") == "2026-02-15"
        assert normalize_publication_date("15/02/2026") == "2026-02-15"

    def test_datetime_object(self):
        dt = datetime(2026, 3, 20, 10, 30, 0)
        assert normalize_publication_date(dt) == "2026-03-20"

    def test_none_and_empty(self):
        assert normalize_publication_date(None) is None
        assert normalize_publication_date("") is None


class TestProcessedSearchResultModel:
    def test_required_fields_and_defaults(self):
        item = ProcessedSearchResult(
            url="https://techcrunch.com/2026/ev-news",
            title="EV Innovation 2026",
            snippet="Overview of battery tech...",
            query="India EV market",
            source_type=SourceType.NEWS,
            relevance_score=0.91,
        )

        assert item.url == "https://techcrunch.com/2026/ev-news"
        assert item.title == "EV Innovation 2026"
        assert item.domain == "techcrunch.com"  # Auto-extracted
        assert item.snippet == "Overview of battery tech..."
        assert item.query == "India EV market"
        assert item.source_type == "news"
        assert item.relevance_score == 0.91
        assert isinstance(item.retrieved_date, datetime)

    def test_model_dump_matching_spec_example(self):
        item = ProcessedSearchResult(
            url="https://reuters.com/business/ev",
            title="Electric Vehicles in India",
            domain="reuters.com",
            source_type="news",
            relevance_score=0.91,
            snippet="Market size reached record heights.",
            publication_date="2026-01-10",
        )
        data = item.model_dump(mode="json")
        assert data["url"] == "https://reuters.com/business/ev"
        assert data["title"] == "Electric Vehicles in India"
        assert data["domain"] == "reuters.com"
        assert data["source_type"] == "news"
        assert data["relevance_score"] == 0.91
        assert data["snippet"] == "Market size reached record heights."
        assert data["publication_date"] == "2026-01-10"
        assert "retrieved_date" in data


class TestSourceModelCompatibility:
    def test_source_model_has_search_processing_fields(self):
        src = Source(
            research_id="res-123",
            url="https://niti.gov.in/ev-policy",
            title="National EV Policy",
            query="India EV policy",
            source_type=SourceType.WEB,
            relevance_score=0.95,
            publication_date="2026-01-01",
        )

        assert src.domain == "niti.gov.in"
        assert src.query == "India EV policy"
        assert src.publication_date == "2026-01-01"
        assert src.published_date == "2026-01-01"  # Alias synced
        assert src.relevance_score == 0.95
        assert isinstance(src.retrieved_date, datetime)


class TestSearchResultProcessor:
    def test_process_result_raw_dict(self):
        raw = {
            "title": "Indian EV Market Size & Forecast",
            "href": "https://www.statista.com/topics/indian-ev",
            "body": "Detailed revenue and unit sales forecasts for 2026.",
            "date": "2026-02-01",
        }
        processed = search_result_processor.process_result(
            raw_result=raw,
            query="Indian EV market size 2026",
            default_source_type=SourceType.WEB,
            relevance_score=0.88,
        )

        assert processed.url == "https://www.statista.com/topics/indian-ev"
        assert processed.domain == "statista.com"
        assert processed.title == "Indian EV Market Size & Forecast"
        assert processed.snippet == "Detailed revenue and unit sales forecasts for 2026."
        assert processed.publication_date == "2026-02-01"
        assert processed.query == "Indian EV market size 2026"
        assert processed.relevance_score == 0.88
        assert processed.source_type == "web"

    def test_process_batch(self):
        raw_items = [
            {"title": "Item 1", "url": "https://site1.org/doc", "snippet": "Text 1"},
            {"title": "Item 2", "url": "https://site2.edu/paper", "snippet": "Text 2", "source_type": "academic"},
        ]
        batch = search_result_processor.process_batch(raw_items, query="test query")
        assert len(batch) == 2
        assert batch[0].domain == "site1.org"
        assert batch[1].domain == "site2.edu"
        assert batch[1].source_type == "academic"

    def test_to_source_conversion(self):
        item = ProcessedSearchResult(
            url="https://iea.org/reports/global-ev-outlook",
            title="Global EV Outlook",
            domain="iea.org",
            snippet="IEA report snippet",
            query="global EV trends",
            source_type=SourceType.WEB,
            relevance_score=0.94,
        )
        source = search_result_processor.to_source(
            processed=item,
            research_id="res-456",
            clean_text="Full extracted report text from IEA...",
            author="IEA Energy Bureau",
            additional_metadata={"custom_key": "val"},
        )

        assert source.research_id == "res-456"
        assert source.domain == "iea.org"
        assert source.author == "IEA Energy Bureau"
        assert source.clean_text.startswith("Full extracted")
        assert source.metadata["custom_key"] == "val"
        assert source.metadata["query_used"] == "global EV trends"


class TestDeepWebResearchAgentWithProcessedResults:
    @pytest.mark.asyncio
    async def test_agent_generates_processed_sources(self):
        agent = DeepWebResearchAgent()

        mock_search_results = [
            {
                "title": "India EV Policy 2026",
                "url": "https://pib.gov.in/press/ev-2026",
                "snippet": "Government subsidies and manufacturing targets.",
                "date": "2026-01-15",
            }
        ]

        with patch("app.search.query_generator.query_generator.generate_queries", new_callable=AsyncMock) as mock_q, \
             patch("app.search.web_search.web_search_engine.search", new_callable=AsyncMock) as mock_s, \
             patch("app.scraping.extractor.content_extractor.extract_from_url", new_callable=AsyncMock) as mock_e:

            mock_q.return_value = ["India EV government policy"]
            mock_s.return_value = mock_search_results
            mock_e.return_value = {
                "title": "Ministry Press Release: India EV Policy",
                "text": "Full text of EV policy release...",
                "author": "Ministry of Heavy Industries",
                "date": "2026-01-15",
            }

            sources = await agent.execute("India EV policy", "res-day13-test")
            assert len(sources) == 1
            s = sources[0]
            assert s.url == "https://pib.gov.in/press/ev-2026"
            assert s.domain == "pib.gov.in"
            assert s.publication_date == "2026-01-15"
            assert s.query == "India EV government policy"
            assert s.source_type == "web"
            assert s.relevance_score > 0.0
            assert isinstance(s.retrieved_date, datetime)


class TestSourcesAPIFiltering:
    @pytest.mark.asyncio
    async def test_filter_sources_by_domain_and_type(self):
        res_id = "test-res-filter-id"
        s1 = Source(
            research_id=res_id,
            url="https://reuters.com/article1",
            title="Reuters EV",
            domain="reuters.com",
            source_type=SourceType.NEWS,
            relevance_score=0.9,
        )
        s2 = Source(
            research_id=res_id,
            url="https://niti.gov.in/report1",
            title="NITI Aayog Policy",
            domain="niti.gov.in",
            source_type=SourceType.WEB,
            relevance_score=0.7,
        )
        await research_repo.add_source(s1)
        await research_repo.add_source(s2)

        # 1. Fetch all
        r_all = client.get(f"/api/v1/sources/research/{res_id}")
        assert r_all.status_code == 200
        assert len(r_all.json()) >= 2

        # 2. Filter by domain
        r_domain = client.get(f"/api/v1/sources/research/{res_id}?domain=reuters.com")
        assert r_domain.status_code == 200
        data_domain = r_domain.json()
        assert len(data_domain) == 1
        assert data_domain[0]["domain"] == "reuters.com"

        # 3. Filter by source_type
        r_type = client.get(f"/api/v1/sources/research/{res_id}?source_type=news")
        assert r_type.status_code == 200
        data_type = r_type.json()
        assert all(item["source_type"] == "news" for item in data_type)

        # 4. Filter by min_relevance
        r_score = client.get(f"/api/v1/sources/research/{res_id}?min_relevance=0.8")
        assert r_score.status_code == 200
        data_score = r_score.json()
        assert all(item["relevance_score"] >= 0.8 for item in data_score)
