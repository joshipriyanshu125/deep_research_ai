from typing import Optional, Dict, Any, List
from pydantic import BaseModel, ConfigDict
from fastapi import Request, Header, HTTPException, status, Depends
from app.database.models.api_key import APIKey
from app.services.api_platform_service import api_platform_service


class APIClientContext(BaseModel):
    api_key: APIKey
    user_id: str
    organization_id: Optional[str] = None
    scopes: List[str] = []
    telemetry: Dict[str, Any] = {}

    model_config = ConfigDict(arbitrary_types_allowed=True)


async def get_api_client_context(
    request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    authorization: Optional[str] = Header(None)
) -> APIClientContext:
    """
    Extracts and authenticates API key from either 'X-API-Key' header
    or 'Authorization: Bearer <key>' / 'Authorization: Api-Key <key>'.
    """
    raw_key = None

    if x_api_key:
        raw_key = x_api_key.strip()
    elif authorization:
        parts = authorization.strip().split()
        if len(parts) == 2 and parts[0].lower() in ["bearer", "api-key", "apikey"]:
            raw_key = parts[1].strip()
        elif len(parts) == 1:
            raw_key = parts[0].strip()

    if not raw_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key required. Provide via 'X-API-Key' header or 'Authorization: Bearer <key>'.",
            headers={"WWW-Authenticate": "ApiKey"}
        )

    api_key, telemetry = await api_platform_service.authenticate_key(raw_key)

    context = APIClientContext(
        api_key=api_key,
        user_id=api_key.user_id,
        organization_id=api_key.organization_id,
        scopes=api_key.scopes,
        telemetry=telemetry
    )
    request.state.api_client = context
    return context


def require_scope(required_scope: str):
    """Dependency helper to enforce specific API key scopes."""
    async def _scope_checker(client: APIClientContext = Depends(get_api_client_context)) -> APIClientContext:
        if required_scope not in client.scopes and "*" not in client.scopes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"API Key does not have the required scope: '{required_scope}'"
            )
        return client
    return _scope_checker
