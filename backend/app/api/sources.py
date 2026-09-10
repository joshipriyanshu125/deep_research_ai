from typing import List, Optional
from fastapi import APIRouter, Query
from app.database.models.source import Source
from app.database.models.evidence import Evidence
from app.database.repositories.research_repo import research_repo

router = APIRouter(prefix="/sources", tags=["Sources & Evidence"])


@router.get("/research/{research_id}", response_model=List[Source])
async def get_research_sources(
    research_id: str,
    domain: Optional[str] = Query(None, description="Filter by domain name (e.g. reuters.com)"),
    source_type: Optional[str] = Query(None, description="Filter by source type (web, news, academic, company)"),
    min_relevance: Optional[float] = Query(None, description="Minimum relevance score filter"),
):
    return await research_repo.get_sources_by_research(
        research_id=research_id,
        domain=domain,
        source_type=source_type,
        min_relevance=min_relevance,
    )


@router.get("/research/{research_id}/evidence", response_model=List[Evidence])
async def get_research_evidence(research_id: str):
    return await research_repo.get_evidence_by_research(research_id)
