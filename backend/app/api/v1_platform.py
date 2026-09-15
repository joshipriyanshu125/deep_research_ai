import json
import time
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import StreamingResponse

from app.database.models.research import ResearchJob, ResearchRequest
from app.database.models.api_key import (
    APIKey,
    APIKeyCreate,
    APIKeyResponse,
    APIKeySecretResponse,
    APIUsageSummary,
    APIKeyScope
)
from app.database.repositories.research_repo import research_repo
from app.database.repositories.report_repo import report_repo
from app.services.research_service import research_service
from app.services.api_platform_service import api_platform_service
from app.middleware.api_key_auth import get_api_client_context, APIClientContext, require_scope
from app.middleware.auth import require_auth
from app.database.models.user import UserInDB


router = APIRouter(tags=["Platform API v1"])


# =====================================================================
# 1. Developer Research Endpoints (POST /v1/research, GET /v1/research/...)
# =====================================================================

@router.post(
    "/research",
    response_model=Dict[str, Any],
    summary="Start Deep Research",
    description="Trigger an autonomous deep research job using your developer API Key."
)
async def create_v1_research(
    request: ResearchRequest,
    client: APIClientContext = Depends(require_scope(APIKeyScope.RESEARCH_CREATE))
):
    start_t = time.perf_counter()
    user_id = client.user_id
    
    job = await research_service.create_research_job(
        request=request,
        user_id=user_id,
    )

    elapsed_ms = (time.perf_counter() - start_t) * 1000.0

    # Approximate token usage for initialization & request
    prompt_tokens = len(request.query.split()) * 4
    response_tokens = 150
    total_tokens = prompt_tokens + response_tokens

    # Track usage asynchronously
    await api_platform_service.record_api_call(
        api_key=client.api_key,
        endpoint="/v1/research",
        method="POST",
        status_code=status.HTTP_200_OK,
        request_tokens=prompt_tokens,
        response_tokens=response_tokens,
        latency_ms=elapsed_ms,
        model_used=request.llm_provider or "default",
        estimated_cost_usd=round((total_tokens / 1000.0) * 0.002, 6)
    )

    return {
        "job": job,
        "api_key_id": client.api_key.id,
        "user_id": client.user_id,
        "organization_id": client.organization_id,
        "limits": client.telemetry
    }


@router.get(
    "/research/{job_id}",
    response_model=ResearchJob,
    summary="Get Research Job Status"
)
async def get_v1_research_status(
    job_id: str,
    client: APIClientContext = Depends(require_scope(APIKeyScope.RESEARCH_READ))
):
    job = await research_service.get_job_status(job_id)
    return job


@router.get(
    "/research/{job_id}/report",
    summary="Get Research Report"
)
async def get_v1_research_report(
    job_id: str,
    client: APIClientContext = Depends(require_scope(APIKeyScope.RESEARCH_READ))
):
    await research_service.get_job_status(job_id)
    report = await report_repo.get_by_research_id(job_id)
    if not report:
        raise HTTPException(status_code=404, detail="Research report not found or research is still in progress")
    return report


@router.get(
    "/research/{job_id}/stream",
    summary="Stream Research Progress (SSE)"
)
async def stream_v1_research_progress(
    job_id: str,
    client: APIClientContext = Depends(require_scope(APIKeyScope.RESEARCH_READ))
):
    async def event_generator():
        try:
            async for event in research_service.stream_research_progress(job_id):
                yield f"data: {json.dumps(event)}\n\n"
        except Exception:
            yield f"data: {json.dumps({'event': 'stream_error', 'data': {'job_id': job_id}})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


# =====================================================================
# 2. Usage & Limits Telemetry (GET /v1/usage)
# =====================================================================

@router.get(
    "/usage",
    response_model=APIUsageSummary,
    summary="Get API Usage & Limits"
)
async def get_v1_usage(
    client: APIClientContext = Depends(require_scope(APIKeyScope.USAGE_READ))
):
    """
    Returns real-time usage metrics, tokens consumed, estimated cost,
    and remaining request/token quotas for the authenticated API key and organization.
    """
    summary = await api_platform_service.get_usage_summary(
        api_key_id=client.api_key.id,
        user_id=client.user_id,
        organization_id=client.organization_id
    )
    return summary


# =====================================================================
# 3. API Key Management (POST/GET/DELETE /v1/api-keys)
# =====================================================================

@router.post(
    "/api-keys",
    response_model=APIKeySecretResponse,
    summary="Create API Key"
)
async def create_api_key(
    data: APIKeyCreate,
    current_user: UserInDB = Depends(require_auth)
):
    """
    Generate a new API key for the logged-in user or organization.
    The secret key will only be shown once in this response!
    """
    return await api_platform_service.create_api_key(
        user_id=current_user.id,
        data=data
    )


@router.get(
    "/api-keys",
    response_model=List[APIKeyResponse],
    summary="List API Keys"
)
async def list_api_keys(
    current_user: UserInDB = Depends(require_auth)
):
    return await api_platform_service.list_keys_for_user(current_user.id)


@router.delete(
    "/api-keys/{key_id}",
    summary="Revoke API Key"
)
async def revoke_api_key(
    key_id: str,
    current_user: UserInDB = Depends(require_auth)
):
    success = await api_platform_service.revoke_api_key(key_id, current_user.id)
    return {"status": "success", "revoked": success, "key_id": key_id}
