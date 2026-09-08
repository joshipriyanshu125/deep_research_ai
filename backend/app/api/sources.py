from typing import List
from fastapi import APIRouter
from app.database.models.source import Source
from app.database.models.evidence import Evidence
from app.database.repositories.research_repo import research_repo

router = APIRouter(prefix="/sources", tags=["Sources & Evidence"])


@router.get("/research/{research_id}", response_model=List[Source])
async def get_research_sources(research_id: str):
    return await research_repo.get_sources_by_research(research_id)


@router.get("/research/{research_id}/evidence", response_model=List[Evidence])
async def get_research_evidence(research_id: str):
    return await research_repo.get_evidence_by_research(research_id)
