"""
Search module providing query generation, web/news/academic search engines,
result ranking, and standardized search result processing.
"""
from app.search.web_search import WebSearchEngine, web_search_engine
from app.search.news_search import NewsSearchEngine, news_search_engine
from app.search.academic_search import AcademicSearchEngine, academic_search_engine
from app.search.query_generator import QueryGenerator, query_generator
from app.search.result_ranker import ResultRanker, result_ranker
from app.search.result_processor import (
    SearchResultProcessor,
    search_result_processor,
    result_processor,
    normalize_publication_date,
)

__all__ = [
    "WebSearchEngine",
    "web_search_engine",
    "NewsSearchEngine",
    "news_search_engine",
    "AcademicSearchEngine",
    "academic_search_engine",
    "QueryGenerator",
    "query_generator",
    "ResultRanker",
    "result_ranker",
    "SearchResultProcessor",
    "search_result_processor",
    "result_processor",
    "normalize_publication_date",
]
