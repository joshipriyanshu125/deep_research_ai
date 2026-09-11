"""
Day 21 — Academic Search Engine

Multi-source academic search across:
  - arXiv (open-access preprints)
  - Semantic Scholar (AI/ML/CS/Bio papers)
  - Crossref (DOI registry — all disciplines)
  - PubMed/NCBI (biomedical literature)
  - Europe PMC (life sciences open-access)

Pipeline:
  Question
    ↓
  Academic Query
    ↓
  Multi-source Paper Search (parallel)
    ↓
  Paper Metadata (title, authors, DOI, year, abstract)
    ↓
  Abstract → Evidence
"""

import asyncio
import re
import httpx
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional
from app.utils.logger import logger


# ---------------------------------------------------------------------------
# 1. arXiv Search (Open-access preprints — CS, Physics, Math, etc.)
# ---------------------------------------------------------------------------

class ArXivSearchEngine:
    BASE_URL = "http://export.arxiv.org/api/query"

    async def search(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """Search arXiv using the Atom feed API."""
        results = []
        try:
            params = {
                "search_query": f"all:{query}",
                "start": 0,
                "max_results": max_results,
                "sortBy": "relevance",
                "sortOrder": "descending",
            }
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(self.BASE_URL, params=params)
                if resp.status_code == 200:
                    root = ET.fromstring(resp.text)
                    ns = {
                        "atom": "http://www.w3.org/2005/Atom",
                        "arxiv": "http://arxiv.org/schemas/atom",
                    }
                    for entry in root.findall("atom:entry", ns):
                        title_el = entry.find("atom:title", ns)
                        summary_el = entry.find("atom:summary", ns)
                        id_el = entry.find("atom:id", ns)
                        published_el = entry.find("atom:published", ns)

                        # Authors
                        authors = []
                        for author_el in entry.findall("atom:author", ns):
                            name_el = author_el.find("atom:name", ns)
                            if name_el is not None and name_el.text:
                                authors.append(name_el.text.strip())

                        # PDF link
                        pdf_url = None
                        for link_el in entry.findall("atom:link", ns):
                            if link_el.get("type") == "application/pdf":
                                pdf_url = link_el.get("href")
                                break

                        # DOI
                        doi_el = entry.find("arxiv:doi", ns)
                        doi = doi_el.text.strip() if doi_el is not None and doi_el.text else None

                        # ArXiv ID → abstract page URL
                        arxiv_id_raw = (id_el.text or "").strip()
                        # Normalize to abstract URL
                        arxiv_abs_url = arxiv_id_raw
                        if "abs/" not in arxiv_id_raw and arxiv_id_raw:
                            arxiv_abs_url = f"https://arxiv.org/abs/{arxiv_id_raw.split('/')[-1]}"

                        year = None
                        if published_el is not None and published_el.text:
                            year = published_el.text[:4]

                        abstract = (summary_el.text or "").strip().replace("\n", " ")

                        results.append({
                            "title": (title_el.text or "").strip().replace("\n", " "),
                            "url": arxiv_abs_url,
                            "pdf_url": pdf_url or (arxiv_abs_url.replace("/abs/", "/pdf/") + ".pdf" if arxiv_abs_url else None),
                            "snippet": abstract[:600],
                            "abstract": abstract,
                            "authors": authors,
                            "year": year,
                            "doi": doi,
                            "source": "arxiv",
                            "source_type": "academic",
                        })
        except Exception as e:
            logger.warning(f"arXiv search failed for '{query}': {e}")
        return results


# ---------------------------------------------------------------------------
# 2. Semantic Scholar Search (AI/CS/Bio — rich metadata & citations)
# ---------------------------------------------------------------------------

class SemanticScholarSearchEngine:
    BASE_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
    FIELDS = "paperId,title,abstract,authors,year,externalIds,openAccessPdf,venue,citationCount"

    async def search(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """Search Semantic Scholar Graph API."""
        results = []
        try:
            params = {
                "query": query,
                "fields": self.FIELDS,
                "limit": max_results,
            }
            headers = {"User-Agent": "DeepResearchAI/1.0 (academic research assistant)"}
            async with httpx.AsyncClient(timeout=20.0, headers=headers) as client:
                resp = await client.get(self.BASE_URL, params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    for paper in data.get("data", []):
                        abstract = (paper.get("abstract") or "").replace("\n", " ").strip()
                        authors = [a.get("name", "") for a in paper.get("authors", [])]

                        doi = None
                        ext_ids = paper.get("externalIds") or {}
                        if ext_ids.get("DOI"):
                            doi = ext_ids["DOI"]

                        pdf_url = None
                        oap = paper.get("openAccessPdf") or {}
                        if oap.get("url"):
                            pdf_url = oap["url"]

                        paper_id = paper.get("paperId", "")
                        url = f"https://www.semanticscholar.org/paper/{paper_id}" if paper_id else ""

                        results.append({
                            "title": (paper.get("title") or "").strip(),
                            "url": url,
                            "pdf_url": pdf_url,
                            "snippet": abstract[:600],
                            "abstract": abstract,
                            "authors": authors,
                            "year": str(paper.get("year") or ""),
                            "doi": doi,
                            "venue": paper.get("venue", ""),
                            "citation_count": paper.get("citationCount", 0),
                            "source": "semantic_scholar",
                            "source_type": "academic",
                        })
        except Exception as e:
            logger.warning(f"Semantic Scholar search failed for '{query}': {e}")
        return results


# ---------------------------------------------------------------------------
# 3. Crossref Search (DOI registry — all academic disciplines)
# ---------------------------------------------------------------------------

class CrossrefSearchEngine:
    BASE_URL = "https://api.crossref.org/works"

    async def search(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """Search Crossref for metadata-rich academic works."""
        results = []
        try:
            params = {
                "query": query,
                "rows": max_results,
                "select": "DOI,title,author,abstract,published-print,published-online,container-title,URL",
            }
            headers = {
                "User-Agent": "DeepResearchAI/1.0 (mailto:research@deepresearch.ai)",
            }
            async with httpx.AsyncClient(timeout=20.0, headers=headers) as client:
                resp = await client.get(self.BASE_URL, params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    for item in data.get("message", {}).get("items", []):
                        title_parts = item.get("title") or []
                        title = title_parts[0] if title_parts else ""

                        abstract = (item.get("abstract") or "")
                        # Strip JATS XML tags from Crossref abstracts
                        abstract = re.sub(r"<[^>]+>", "", abstract).strip()

                        authors = []
                        for auth in item.get("author") or []:
                            name = f"{auth.get('given', '')} {auth.get('family', '')}".strip()
                            if name:
                                authors.append(name)

                        doi = item.get("DOI", "")
                        url = item.get("URL") or (f"https://doi.org/{doi}" if doi else "")

                        year = None
                        pub = item.get("published-print") or item.get("published-online") or {}
                        dp = pub.get("date-parts", [[]])
                        if dp and dp[0]:
                            year = str(dp[0][0])

                        journal = ""
                        ct = item.get("container-title") or []
                        if ct:
                            journal = ct[0]

                        results.append({
                            "title": title,
                            "url": url,
                            "pdf_url": None,
                            "snippet": abstract[:600],
                            "abstract": abstract,
                            "authors": authors,
                            "year": year or "",
                            "doi": doi,
                            "venue": journal,
                            "source": "crossref",
                            "source_type": "academic",
                        })
        except Exception as e:
            logger.warning(f"Crossref search failed for '{query}': {e}")
        return results


# ---------------------------------------------------------------------------
# 4. PubMed/NCBI Search (Biomedical literature)
# ---------------------------------------------------------------------------

class PubMedSearchEngine:
    ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

    async def search(self, query: str, max_results: int = 4) -> List[Dict[str, Any]]:
        """Search PubMed and fetch abstracts for top results."""
        results = []
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                # Step 1: Esearch — get PMIDs
                esearch_params = {
                    "db": "pubmed",
                    "term": query,
                    "retmax": max_results,
                    "retmode": "json",
                    "sort": "relevance",
                }
                esearch_resp = await client.get(self.ESEARCH_URL, params=esearch_params)
                if esearch_resp.status_code != 200:
                    return results

                esearch_data = esearch_resp.json()
                pmids = esearch_data.get("esearchresult", {}).get("idlist", [])
                if not pmids:
                    return results

                # Step 2: Efetch — get article metadata in XML
                efetch_params = {
                    "db": "pubmed",
                    "id": ",".join(pmids[:max_results]),
                    "retmode": "xml",
                    "rettype": "abstract",
                }
                efetch_resp = await client.get(self.EFETCH_URL, params=efetch_params)
                if efetch_resp.status_code != 200:
                    return results

                root = ET.fromstring(efetch_resp.text)
                for article in root.findall(".//PubmedArticle"):
                    try:
                        medline = article.find("MedlineCitation")
                        if medline is None:
                            continue
                        art_el = medline.find("Article")
                        if art_el is None:
                            continue

                        title_el = art_el.find("ArticleTitle")
                        title = (title_el.text or "") if title_el is not None else ""

                        # Abstract
                        abstract_texts = []
                        abstract_el = art_el.find("Abstract")
                        if abstract_el is not None:
                            for at in abstract_el.findall("AbstractText"):
                                label = at.get("Label", "")
                                text = at.text or ""
                                if label:
                                    abstract_texts.append(f"{label}: {text}")
                                else:
                                    abstract_texts.append(text)
                        abstract = " ".join(abstract_texts).strip()

                        # Authors
                        authors = []
                        author_list = art_el.find("AuthorList")
                        if author_list:
                            for auth in author_list.findall("Author"):
                                last = auth.find("LastName")
                                fore = auth.find("ForeName")
                                if last is not None:
                                    name = last.text or ""
                                    if fore is not None and fore.text:
                                        name = f"{fore.text} {name}"
                                    authors.append(name.strip())

                        # PMID
                        pmid_el = medline.find("PMID")
                        pmid = pmid_el.text if pmid_el is not None else ""
                        url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else ""

                        # Year
                        pub_date = art_el.find(".//PubDate")
                        year = ""
                        if pub_date is not None:
                            year_el = pub_date.find("Year")
                            if year_el is not None:
                                year = year_el.text or ""

                        results.append({
                            "title": title.strip(),
                            "url": url,
                            "pdf_url": None,
                            "snippet": abstract[:600],
                            "abstract": abstract,
                            "authors": authors,
                            "year": year,
                            "doi": None,
                            "source": "pubmed",
                            "source_type": "academic",
                        })
                    except Exception as parse_err:
                        logger.warning(f"PubMed article parse error: {parse_err}")

        except Exception as e:
            logger.warning(f"PubMed search failed for '{query}': {e}")
        return results


# ---------------------------------------------------------------------------
# 5. Unified Academic Search Engine (parallel multi-source)
# ---------------------------------------------------------------------------

class AcademicSearchEngine:
    """
    Day 21 — Unified Academic Search Engine.
    Queries arXiv, Semantic Scholar, Crossref, and PubMed in parallel,
    deduplicates results by title/DOI, and ranks by year + citation count.
    """

    def __init__(self):
        self.arxiv = ArXivSearchEngine()
        self.semantic_scholar = SemanticScholarSearchEngine()
        self.crossref = CrossrefSearchEngine()
        self.pubmed = PubMedSearchEngine()

    async def search(
        self,
        query: str,
        max_results: int = 8,
        sources: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Parallel multi-source academic search with deduplication and ranking.
        sources: list from ["arxiv", "semantic_scholar", "crossref", "pubmed"]
        """
        if sources is None:
            sources = ["arxiv", "semantic_scholar", "crossref", "pubmed"]

        per_source = max(2, max_results // len(sources))

        # Build coroutine list based on requested sources
        coros = []
        if "arxiv" in sources:
            coros.append(self.arxiv.search(query, per_source))
        if "semantic_scholar" in sources:
            coros.append(self.semantic_scholar.search(query, per_source))
        if "crossref" in sources:
            coros.append(self.crossref.search(query, per_source))
        if "pubmed" in sources:
            coros.append(self.pubmed.search(query, per_source))

        # Execute all searches in parallel
        gathered = await asyncio.gather(*coros, return_exceptions=True)

        # Collect and deduplicate
        all_results: List[Dict[str, Any]] = []
        seen_titles: set = set()
        seen_dois: set = set()

        for batch in gathered:
            if isinstance(batch, Exception):
                logger.warning(f"Academic search source error: {batch}")
                continue
            for item in batch:
                title_key = re.sub(r"\W+", "", (item.get("title") or "").lower())[:60]
                doi = (item.get("doi") or "").strip()

                if title_key and title_key in seen_titles:
                    continue
                if doi and doi in seen_dois:
                    continue

                if title_key:
                    seen_titles.add(title_key)
                if doi:
                    seen_dois.add(doi)

                all_results.append(item)

        # Sort: prefer papers with abstracts and pdf links, then by year descending
        def _rank(item: Dict) -> float:
            score = 0.0
            if item.get("abstract") and len(item["abstract"]) > 100:
                score += 0.5
            if item.get("pdf_url"):
                score += 0.3
            if item.get("year"):
                try:
                    score += min(0.2, int(item["year"]) / 20000)
                except ValueError:
                    pass
            if item.get("citation_count", 0):
                score += min(0.1, item["citation_count"] / 10000)
            return score

        all_results.sort(key=_rank, reverse=True)
        return all_results[:max_results]

    async def search_with_pdf_urls(
        self,
        query: str,
        max_results: int = 5,
    ) -> List[Dict[str, Any]]:
        """Search and return only papers that have open-access PDFs."""
        results = await self.search(query, max_results=max_results * 2)
        pdf_results = [r for r in results if r.get("pdf_url")]
        return pdf_results[:max_results]


# Singleton
academic_search_engine = AcademicSearchEngine()
