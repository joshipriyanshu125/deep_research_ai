from typing import List
from app.search.academic_search import academic_search_engine
from app.database.models.source import Source, SourceType


class PaperAgent:
    async def execute(self, query: str, research_id: str) -> List[Source]:
        search_items = await academic_search_engine.search(query, max_results=3)
        sources = []
        for item in search_items:
            source = Source(
                research_id=research_id,
                url=item.get("url", ""),
                title=item.get("title", ""),
                source_type=SourceType.ACADEMIC,
                snippet=item.get("snippet", ""),
                clean_text=item.get("snippet", ""),
                relevance_score=0.95,
                credibility_score=0.98
            )
            sources.append(source)
        return sources


paper_agent = PaperAgent()
