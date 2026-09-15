from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from fastapi import APIRouter, Depends, Query, HTTPException, status

from app.memory.entity_memory import entity_memory, EntityKnowledge, PreviousConclusion, EntityType
from app.memory.knowledge_graph import knowledge_graph, GraphPath, RelationType
from app.memory.manager import memory_manager
from app.middleware.auth import get_current_user
from app.database.models.user import UserInDB


router = APIRouter(prefix="/memory", tags=["Memory & Knowledge Graph"])


class GraphQueryRequest(BaseModel):
    source_entity: Optional[str] = None
    target_entity: Optional[str] = None
    center_entity: Optional[str] = None
    depth: int = 2
    max_depth: int = 6


@router.get("/entities", response_model=List[EntityKnowledge], summary="Search Entity Knowledge")
async def get_entities(
    query: Optional[str] = Query(None, description="Search term for entity or aliases"),
    entity_type: Optional[EntityType] = Query(None, description="Filter by entity type"),
    industry: Optional[str] = Query(None, description="Filter by industry"),
    country: Optional[str] = Query(None, description="Filter by country"),
    limit: int = Query(50, ge=1, le=200)
):
    """Search and browse cross-research entity knowledge base."""
    return await entity_memory.search_entities(
        query=query,
        entity_type=entity_type,
        industry=industry,
        country=country,
        limit=limit
    )


@router.get("/conclusions", response_model=List[PreviousConclusion], summary="List Previous Conclusions")
async def get_conclusions(
    topic: Optional[str] = Query(None, description="Filter by topic keyword"),
    limit: int = Query(50, ge=1, le=100)
):
    """Retrieve verified historical research conclusions and hypotheses."""
    if topic:
        return await entity_memory.get_conclusions_by_topic(topic=topic, limit=limit)
    return await entity_memory.list_conclusions(limit=limit)


@router.get("/graph", summary="Export Knowledge Graph")
async def get_knowledge_graph():
    """Retrieve full knowledge graph nodes and edges for visualization (e.g. D3 / ForceGraph)."""
    return knowledge_graph.export_graph()


@router.post("/graph/query", summary="Query Knowledge Graph Multi-Hop Path or Neighborhood")
async def query_knowledge_graph(request: GraphQueryRequest):
    """
    Perform graph operations:
    1. If source_entity and target_entity are provided: finds shortest multi-hop relationship path.
    2. If center_entity is provided: extracts sub-graph neighborhood.
    """
    if request.source_entity and request.target_entity:
        path = knowledge_graph.find_path(
            source_label_or_id=request.source_entity,
            target_label_or_id=request.target_entity,
            max_depth=request.max_depth
        )
        if not path:
            return {"found": False, "message": f"No path found between '{request.source_entity}' and '{request.target_entity}' within {request.max_depth} hops"}
        return {"found": True, "path": path}

    if request.center_entity:
        neighborhood = knowledge_graph.get_neighborhood(
            node_label_or_id=request.center_entity,
            depth=request.depth
        )
        return {"found": neighborhood["total_nodes"] > 0, "neighborhood": neighborhood}

    return {"error": "Provide either (source_entity, target_entity) or center_entity"}


@router.get("/ecosystem/{company_name}", summary="Get Company Market Ecosystem")
async def get_company_ecosystem(company_name: str):
    """
    Discovers complete company ecosystem: markets operated in,
    products manufactured, suppliers, competitors, and subsidiaries.
    """
    eco = knowledge_graph.find_market_ecosystem(company_name)
    if not eco:
        raise HTTPException(status_code=404, detail=f"Company '{company_name}' not found in Knowledge Graph")
    return eco
