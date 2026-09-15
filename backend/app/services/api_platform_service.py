import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any, Tuple
from fastapi import HTTPException, status

from app.database.models.api_key import (
    APIKey,
    APIKeyCreate,
    APIKeySecretResponse,
    APIKeyResponse,
    APIUsageRecord,
    APIUsageSummary,
    APIKeyScope
)
from app.database.repositories.api_key_repo import api_key_repo
from app.utils.helpers import get_utc_now
from app.utils.logger import logger


class APIPlatformService:
    KEY_PREFIX_LIVE = "dra_live_"
    KEY_PREFIX_TEST = "dra_test_"

    def _hash_key(self, plain_key: str) -> str:
        return hashlib.sha256(plain_key.encode("utf-8")).hexdigest()

    def generate_raw_key(self, is_test: bool = False) -> str:
        prefix = self.KEY_PREFIX_TEST if is_test else self.KEY_PREFIX_LIVE
        random_token = secrets.token_urlsafe(32)
        return f"{prefix}{random_token}"

    async def create_api_key(
        self,
        user_id: str,
        data: APIKeyCreate,
        is_test: bool = False
    ) -> APIKeySecretResponse:
        plain_key = self.generate_raw_key(is_test=is_test)
        hashed_key = self._hash_key(plain_key)
        key_prefix = plain_key[:12] + "..."

        expires_at = None
        if data.expires_in_days:
            expires_at = get_utc_now() + timedelta(days=data.expires_in_days)

        scopes = data.scopes or list(APIKeyScope.ALL)

        api_key = APIKey(
            name=data.name,
            key_prefix=key_prefix,
            hashed_key=hashed_key,
            user_id=user_id,
            organization_id=data.organization_id,
            scopes=scopes,
            rate_limit_per_minute=data.rate_limit_per_minute or 60,
            monthly_quota=data.monthly_quota or 1000,
            monthly_token_quota=data.monthly_token_quota or 2_000_000,
            is_active=True,
            expires_at=expires_at
        )

        saved = await api_key_repo.create_key(api_key)
        logger.info(f"Created API key {saved.id} for user {user_id}, prefix {key_prefix}")

        return APIKeySecretResponse(
            id=saved.id,
            name=saved.name,
            key_prefix=saved.key_prefix,
            user_id=saved.user_id,
            organization_id=saved.organization_id,
            scopes=saved.scopes,
            rate_limit_per_minute=saved.rate_limit_per_minute,
            monthly_quota=saved.monthly_quota,
            monthly_token_quota=saved.monthly_token_quota,
            is_active=saved.is_active,
            expires_at=saved.expires_at,
            created_at=saved.created_at,
            last_used_at=saved.last_used_at,
            secret_key=plain_key
        )

    async def authenticate_key(self, raw_key: str) -> Tuple[APIKey, Dict[str, Any]]:
        """
        Validate raw API key, check active state, expiration, rate limits, and quota.
        Returns the APIKey model and current rate/quota telemetry.
        """
        if not raw_key or not (raw_key.startswith(self.KEY_PREFIX_LIVE) or raw_key.startswith(self.KEY_PREFIX_TEST)):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API Key format. Expected dra_live_... or dra_test_...",
                headers={"WWW-Authenticate": "ApiKey"}
            )

        hashed = self._hash_key(raw_key)
        api_key = await api_key_repo.get_by_hash(hashed)

        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API Key. Key not found.",
                headers={"WWW-Authenticate": "ApiKey"}
            )

        if not api_key.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API Key has been revoked or deactivated.",
                headers={"WWW-Authenticate": "ApiKey"}
            )

        now = get_utc_now()
        if api_key.expires_at and api_key.expires_at < now:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API Key has expired.",
                headers={"WWW-Authenticate": "ApiKey"}
            )

        # Rate Limit Check (Per minute)
        req_count_minute = await api_key_repo.get_minute_request_count(api_key.id)
        if req_count_minute >= api_key.rate_limit_per_minute:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded: {api_key.rate_limit_per_minute} requests/min limit reached.",
                headers={
                    "Retry-After": "60",
                    "X-RateLimit-Limit": str(api_key.rate_limit_per_minute),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": "60"
                }
            )

        # Monthly Quota Check
        monthly_usage = await api_key_repo.get_monthly_usage(api_key_id=api_key.id)
        if monthly_usage["total_requests"] >= api_key.monthly_quota:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Monthly request quota exceeded: {api_key.monthly_quota} requests limit reached for this billing cycle.",
                headers={"Retry-After": "86400"}
            )

        if monthly_usage["total_tokens"] >= api_key.monthly_token_quota:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Monthly token quota exceeded: {api_key.monthly_token_quota} tokens limit reached for this billing cycle.",
                headers={"Retry-After": "86400"}
            )

        # Update last used in background/async
        await api_key_repo.update_last_used(api_key.id)

        telemetry = {
            "rate_limit_per_minute": api_key.rate_limit_per_minute,
            "requests_this_minute": req_count_minute + 1,
            "requests_remaining_minute": max(0, api_key.rate_limit_per_minute - req_count_minute - 1),
            "monthly_quota": api_key.monthly_quota,
            "monthly_requests_used": monthly_usage["total_requests"],
            "monthly_requests_remaining": max(0, api_key.monthly_quota - monthly_usage["total_requests"]),
            "monthly_token_quota": api_key.monthly_token_quota,
            "monthly_tokens_used": monthly_usage["total_tokens"],
            "monthly_tokens_remaining": max(0, api_key.monthly_token_quota - monthly_usage["total_tokens"])
        }

        return api_key, telemetry

    async def record_api_call(
        self,
        api_key: APIKey,
        endpoint: str,
        method: str = "POST",
        status_code: int = 200,
        request_tokens: int = 0,
        response_tokens: int = 0,
        latency_ms: float = 0.0,
        model_used: Optional[str] = None,
        estimated_cost_usd: float = 0.0,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> APIUsageRecord:
        total_tokens = request_tokens + response_tokens
        if estimated_cost_usd == 0.0 and total_tokens > 0:
            # Baseline estimation: ~$0.002 per 1k tokens standard
            estimated_cost_usd = round((total_tokens / 1000.0) * 0.002, 6)

        record = APIUsageRecord(
            api_key_id=api_key.id,
            user_id=api_key.user_id,
            organization_id=api_key.organization_id,
            endpoint=endpoint,
            method=method,
            status_code=status_code,
            request_tokens=request_tokens,
            response_tokens=response_tokens,
            total_tokens=total_tokens,
            estimated_cost_usd=estimated_cost_usd,
            latency_ms=latency_ms,
            model_used=model_used,
            ip_address=ip_address,
            user_agent=user_agent
        )
        return await api_key_repo.record_usage(record)

    async def get_usage_summary(
        self,
        api_key_id: Optional[str] = None,
        user_id: Optional[str] = None,
        organization_id: Optional[str] = None
    ) -> APIUsageSummary:
        monthly = await api_key_repo.get_monthly_usage(
            api_key_id=api_key_id,
            user_id=user_id,
            organization_id=organization_id
        )

        # Default limits or fetched from key
        key_limit_req = 1000
        key_limit_tokens = 2_000_000
        key_rate_limit = 60

        if api_key_id:
            key = await api_key_repo.get_by_id(api_key_id)
            if key:
                key_limit_req = key.monthly_quota
                key_limit_tokens = key.monthly_token_quota
                key_rate_limit = key.rate_limit_per_minute

        reqs_remaining = max(0, key_limit_req - monthly["total_requests"])
        tokens_remaining = max(0, key_limit_tokens - monthly["total_tokens"])

        return APIUsageSummary(
            api_key_id=api_key_id,
            user_id=user_id,
            organization_id=organization_id,
            total_requests=monthly["total_requests"],
            total_tokens=monthly["total_tokens"],
            total_cost_usd=monthly["total_cost_usd"],
            requests_remaining=reqs_remaining,
            tokens_remaining=tokens_remaining,
            rate_limit_per_minute=key_rate_limit,
            monthly_quota=key_limit_req,
            monthly_token_quota=key_limit_tokens,
            period_start=monthly["period_start"],
            period_end=monthly["period_end"]
        )

    async def list_keys_for_user(self, user_id: str) -> List[APIKeyResponse]:
        keys = await api_key_repo.list_by_user(user_id)
        return [
            APIKeyResponse(
                id=k.id,
                name=k.name,
                key_prefix=k.key_prefix,
                user_id=k.user_id,
                organization_id=k.organization_id,
                scopes=k.scopes,
                rate_limit_per_minute=k.rate_limit_per_minute,
                monthly_quota=k.monthly_quota,
                monthly_token_quota=k.monthly_token_quota,
                is_active=k.is_active,
                expires_at=k.expires_at,
                created_at=k.created_at,
                last_used_at=k.last_used_at
            )
            for k in keys
        ]

    async def revoke_api_key(self, key_id: str, user_id: str) -> bool:
        key = await api_key_repo.get_by_id(key_id)
        if not key or key.user_id != user_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")
        updated = await api_key_repo.revoke_key(key_id)
        return updated is not None and not updated.is_active


api_platform_service = APIPlatformService()
