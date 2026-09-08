from typing import List, Dict, Any
from app.database.models.source import Source
from app.database.models.report import Citation


class CitationEngine:
    def build_citations(self, sources: List[Source]) -> List[Citation]:
        citations = []
        for idx, s in enumerate(sources, 1):
            citations.append(
                Citation(
                    index=idx,
                    title=s.title or f"Source {idx}",
                    url=s.url,
                    source_type=s.source_type,
                    snippet=s.snippet or ""
                )
            )
        return citations

    def format_bibliography_markdown(self, citations: List[Citation]) -> str:
        lines = ["## References & Sources\n"]
        for c in citations:
            lines.append(f"[{c.index}] **[{c.title}]({c.url})** - *{c.source_type.title()} source*")
            if c.snippet:
                lines.append(f"   > {c.snippet}\n")
        return "\n".join(lines)


citation_engine = CitationEngine()
