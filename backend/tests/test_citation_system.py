"""
Day 19 — Citation System Test Suite
Comprehensive testing for:
  Claim -> Evidence -> Source -> URL
"""

import pytest
from unittest.mock import AsyncMock, patch
from app.database.models.source import Source, SourceType
from app.database.models.evidence import Evidence
from app.database.models.report import Citation, CitationTrace, ResearchReport
from app.research.citation import CitationEngine, citation_engine
from app.agents.synthesizer import SynthesizerAgent, synthesizer_agent
from app.reports.formatter import ReportFormatter, report_formatter


class TestCitationModel:
    def test_format_standard_reference(self):
        cit = Citation(
            index=1,
            title="NITI Aayog EV Report",
            url="https://niti.gov.in/report/ev-2026",
            source_type="government",
        )
        assert cit.format_reference(style="standard") == "[1] NITI Aayog EV Report — https://niti.gov.in/report/ev-2026"

    def test_format_markdown_reference(self):
        cit = Citation(
            index=2,
            title="Reuters Global Energy",
            url="https://reuters.com/markets/energy",
        )
        assert cit.format_reference(style="markdown_link") == "[2] **[Reuters Global Energy](https://reuters.com/markets/energy)**"

    def test_citation_trace_dict(self):
        cit = Citation(
            index=1,
            title="Autocar EV Market Update",
            url="https://autocarpro.in/ev",
            source_id="src-101",
            claim="EV sales grew 45%",
            quote="According to industry data, EV sales grew 45% in 2025.",
            confidence=0.95,
        )
        trace = cit.to_trace_dict()
        assert trace["index"] == 1
        assert trace["claim"] == "EV sales grew 45%"
        assert trace["evidence"] == "According to industry data, EV sales grew 45% in 2025."
        assert trace["source_title"] == "Autocar EV Market Update"
        assert trace["url"] == "https://autocarpro.in/ev"
        assert trace["confidence"] == 0.95


class TestCitationEngine:
    def test_build_citations_deduplication_and_indexing(self):
        engine = CitationEngine()
        src1 = Source(
            source_id="s1",
            url="https://reuters.com/article1",
            title="Reuters First Article",
        )
        src2 = Source(
            source_id="s2",
            url="https://bloomberg.com/article2",
            title="Bloomberg Energy",
        )
        src3_dup = Source(
            source_id="s3",
            url="https://reuters.com/article1",  # Duplicate URL
            title="Reuters First Article Duplicate",
        )

        citations = engine.build_citations([src1, src2, src3_dup])
        assert len(citations) == 2
        assert citations[0].index == 1
        assert citations[0].title == "Reuters First Article"
        assert citations[0].url == "https://reuters.com/article1"
        assert citations[1].index == 2
        assert citations[1].title == "Bloomberg Energy"
        assert citations[1].url == "https://bloomberg.com/article2"

    def test_build_traceability_matrix_hierarchy(self):
        engine = CitationEngine()
        src = Source(
            source_id="src-gov-1",
            url="https://niti.gov.in/ev-policy",
            title="NITI Aayog National EV Policy",
        )
        ev = Evidence(
            research_id="res-1",
            source_id="src-gov-1",
            claim="India targets 80% two-wheeler electrification by 2030",
            quote="The government policy roadmap targets 80% two-wheeler electrification by 2030.",
            confidence=0.96,
        )

        traces = engine.build_traceability_matrix(
            evidence_list=[ev],
            sources=[src],
        )

        assert len(traces) == 1
        t = traces[0]
        # Verify 4-tier chain: Claim -> Evidence -> Source -> URL
        assert t.claim == "India targets 80% two-wheeler electrification by 2030"
        assert t.evidence == "The government policy roadmap targets 80% two-wheeler electrification by 2030."
        assert t.source_title == "NITI Aayog National EV Policy"
        assert t.url == "https://niti.gov.in/ev-policy"
        assert t.citation_index == 1
        assert t.confidence == 0.96

    def test_format_bibliography_markdown(self):
        engine = CitationEngine()
        citations = [
            Citation(index=1, title="Economic Times EV Market", url="https://economictimes.com/ev"),
            Citation(index=2, title="Ministry of Heavy Industries", url="https://heavyindustries.gov.in/scheme"),
        ]

        bib = engine.format_bibliography_markdown(citations)
        expected = """## Sources & References

[1] Economic Times EV Market — https://economictimes.com/ev
[2] Ministry of Heavy Industries — https://heavyindustries.gov.in/scheme
"""
        assert bib.strip() == expected.strip()

    def test_inject_citations_to_text(self):
        engine = CitationEngine()
        src = Source(
            source_id="src-siam-1",
            url="https://siam.in/report-2025",
            title="SIAM Annual Vehicle Report",
        )
        ev = Evidence(
            source_id="src-siam-1",
            claim="India EV market grew significantly during the period studied",
            quote="India's EV market grew significantly during the period studied with 45% annual expansion.",
            metrics=["45%"],
        )
        citations = engine.build_citations([src], [ev])

        body_text = "India's EV market grew significantly during the period studied. Infrastructure deployment also expanded across cities."
        annotated = engine.inject_citations_to_text(body_text, [ev], citations)

        # Must attach .[1] cleanly to the matching sentence
        assert "India's EV market grew significantly during the period studied.[1]" in annotated

    def test_verify_citations_valid_and_orphan(self):
        engine = CitationEngine()
        citations = [
            Citation(index=1, title="Source 1", url="https://src1.com"),
            Citation(index=2, title="Source 2", url="https://src2.com"),
        ]

        valid_text = "EV market grew rapidly in 2025.[1] Battery chemistry shifted towards LFP.[2]"
        audit_valid = engine.verify_citations(valid_text, citations)
        assert audit_valid["valid"] is True
        assert audit_valid["cited_indices"] == [1, 2]
        assert audit_valid["orphan_indices"] == []

        orphan_text = "EV market grew rapidly in 2025.[1] An unsupported claim here.[99]"
        audit_orphan = engine.verify_citations(orphan_text, citations)
        assert audit_orphan["valid"] is False
        assert audit_orphan["orphan_indices"] == [99]


class TestSynthesizerAgentCitations:
    @pytest.mark.asyncio
    async def test_synthesizer_builds_traceability_matrix_and_bibliography(self):
        agent = SynthesizerAgent()

        src = Source(
            source_id="src-test-100",
            research_id="res-100",
            url="https://autocarpro.in/ev-report",
            title="AutoCar India EV Report",
        )
        ev = Evidence(
            research_id="res-100",
            source_id="src-test-100",
            claim="Commercial EV sales grew by 45% in 2025",
            quote="Official data shows commercial EV sales grew by 45% in 2025.",
            confidence=0.95,
        )

        mock_llm_markdown = "Commercial EV sales grew by 45% in 2025."

        with patch.object(agent.llm, "execute_prompt", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = mock_llm_markdown

            report = await agent.synthesize_report(
                query="Indian Commercial EV Growth",
                sources=[src],
                evidence=[ev],
            )

            assert isinstance(report, ResearchReport)
            assert len(report.citations) == 1
            assert report.citations[0].index == 1
            assert report.citations[0].url == "https://autocarpro.in/ev-report"

            # Check Traceability Matrix
            assert len(report.traceability_matrix) == 1
            trace = report.traceability_matrix[0]
            assert trace.claim == "Commercial EV sales grew by 45% in 2025"
            assert trace.source_title == "AutoCar India EV Report"
            assert trace.url == "https://autocarpro.in/ev-report"
            assert trace.citation_index == 1

            # Check markdown has inline citation and bibliography
            assert "[1] AutoCar India EV Report — https://autocarpro.in/ev-report" in report.markdown_content



class TestReportFormatterCitations:
    def test_format_full_markdown_with_citations(self):
        formatter = ReportFormatter()
        cit1 = Citation(index=1, title="SIAM Report", url="https://siam.in/ev")
        report = ResearchReport(
            research_id="res-fmt-1",
            title="Electric Vehicles in India",
            executive_summary="Summary text.",
            markdown_content="India's EV market grew significantly during the period studied.[1]",
            citations=[cit1],
        )

        full_md = formatter.format_full_markdown(report)
        assert "India's EV market grew significantly during the period studied.[1]" in full_md
        assert "[1] SIAM Report — https://siam.in/ev" in full_md
