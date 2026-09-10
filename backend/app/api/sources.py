from typing import List, Optional
from fastapi import APIRouter, Query, HTTPException, status
from app.database.models.source import Source, SourceType
from app.database.models.evidence import Evidence
from app.database.repositories.source_repo import source_repo
from app.database.repositories.research_repo import research_repo

router = APIRouter(prefix="/sources", tags=["Sources & Evidence"])


@router.get("/research/{research_id}", response_model=List[Source])
async def get_research_sources(
    research_id: str,
    domain: Optional[str] = Query(None, description="Filter by domain name (e.g. reuters.com)"),
    source_type: Optional[str] = Query(None, description="Filter by source type (news, government, company, academic, financial, blog, forum, social, other)"),
    language: Optional[str] = Query(None, description="Filter by language code (e.g. en)"),
    min_relevance: Optional[float] = Query(None, description="Minimum relevance score filter"),
    min_credibility: Optional[float] = Query(None, description="Minimum credibility score filter"),
):
    return await source_repo.get_sources_by_research(
        research_id=research_id,
        domain=domain,
        source_type=source_type,
        language=language,
        min_relevance=min_relevance,
        min_credibility=min_credibility,
    )


@router.get("/{source_id}", response_model=Source)
async def get_source_by_id(source_id: str):
    source = await source_repo.get_source(source_id)
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source with id '{source_id}' not found.",
        )
    return source


@router.post("/", response_model=Source, status_code=status.HTTP_201_CREATED)
async def create_source(source: Source):
    return await source_repo.create_source(source)


@router.delete("/{source_id}", status_code=status.HTTP_200_OK)
async def delete_source(source_id: str):
    success = await source_repo.delete_source(source_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source with id '{source_id}' not found.",
        )
    return {"message": "Source successfully deleted", "source_id": source_id}


@router.get("/research/{research_id}/evidence", response_model=List[Evidence])
async def get_research_evidence(research_id: str):
    return await research_repo.get_evidence_by_research(research_id)
