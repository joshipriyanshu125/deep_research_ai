from app.database.models.report import Citation, ResearchReport
from app.reports.sections import select_report_section_keys


def test_section_selection_is_query_driven():
    market_keys = select_report_section_keys("Global EV market growth and pricing")
    technical_keys = select_report_section_keys("Quantum computing architecture benchmark")
    decision_keys = select_report_section_keys("Security risks and recommendations for adoption")

    assert "market_analysis" in market_keys
    assert "technical_analysis" in technical_keys
    assert "comparative_analysis" in technical_keys
    assert "risks" in decision_keys
    assert "recommendations" in decision_keys
    assert market_keys != technical_keys


def test_generic_questions_keep_a_sensible_market_default():
    keys = select_report_section_keys("What is the future of renewable energy?")

    assert "market_analysis" in keys
    assert "risks" in keys


def test_report_schema_serializes_structured_sources_and_recommendations():
    citation = Citation(index=1, title="Example", url="https://example.com")
    report = ResearchReport(
        research_id="research-1",
        title="Structured report",
        executive_summary="Summary",
        markdown_content="# Structured report",
        citations=[citation],
        recommendations=["Validate the highest-confidence finding"],
    )

    payload = report.model_dump(mode="json")

    assert payload["sources"][0]["url"] == "https://example.com"
    assert payload["citations"][0]["index"] == 1
    assert payload["recommendations"] == ["Validate the highest-confidence finding"]
    assert report.to_dict()["research_id"] == "research-1"


def test_legacy_citation_only_payload_populates_sources():
    report = ResearchReport(
        research_id="research-legacy",
        title="Legacy report",
        executive_summary="Summary",
        markdown_content="Body",
        citations=[{"index": 1, "title": "Legacy", "url": "https://legacy.example"}],
    )

    assert report.sources == report.citations


def test_sources_only_payload_remains_backward_compatible():
    report = ResearchReport(
        research_id="research-structured",
        title="Structured report",
        executive_summary="Summary",
        markdown_content="Body",
        sources=[{"index": 1, "title": "New", "url": "https://new.example"}],
    )

    assert report.citations == report.sources
