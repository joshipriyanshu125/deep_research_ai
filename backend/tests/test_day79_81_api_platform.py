"""
Tests for DAY 79–81 — API Platform
Allows external applications to use the research engine via API Keys,
with tracking of api_key, user, organization, usage, and rate/quota limits.
"""

import pytest
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.database.models.api_key import (
    APIKeyCreate,
    APIKeyScope,
    APIKeyResponse,
    APIKeySecretResponse,
    APIUsageRecord
)
from app.database.models.user import UserInDB
from app.database.repositories.api_key_repo import api_key_repo
from app.database.repositories.user_repo import user_repo
from app.services.api_platform_service import api_platform_service
from app.middleware.auth import create_access_token
from app.utils.helpers import get_utc_now


@pytest.fixture(autouse=True)
def clear_api_stores():
    api_key_repo.clear_memory()
    user_repo._memory_users.clear()
    yield
    api_key_repo.clear_memory()
    user_repo._memory_users.clear()


@pytest.mark.asyncio
async def test_api_key_creation_and_hashing():
    user_id = "user_dev_01"
    key_create = APIKeyCreate(
        name="Production Key",
        organization_id="org_alpha_99",
        rate_limit_per_minute=100,
        monthly_quota=5000,
        monthly_token_quota=10_000_000
    )

    created = await api_platform_service.create_api_key(user_id=user_id, data=key_create)
    assert created.id is not None
    assert created.name == "Production Key"
    assert created.user_id == user_id
    assert created.organization_id == "org_alpha_99"
    assert created.secret_key.startswith("dra_live_")
    assert created.key_prefix.startswith("dra_live_")
    assert created.rate_limit_per_minute == 100
    assert created.monthly_quota == 5000

    # Ensure plain secret key is NOT saved in DB, only hashed
    saved_key = await api_key_repo.get_by_id(created.id)
    assert saved_key is not None
    assert saved_key.hashed_key != created.secret_key
    assert len(saved_key.hashed_key) == 64  # SHA-256


@pytest.mark.asyncio
async def test_api_key_authentication_success():
    user_id = "user_dev_02"
    key_create = APIKeyCreate(name="Test Key")
    created = await api_platform_service.create_api_key(user_id=user_id, data=key_create)

    # Valid auth
    api_key, telemetry = await api_platform_service.authenticate_key(created.secret_key)
    assert api_key.id == created.id
    assert api_key.user_id == user_id
    assert telemetry["rate_limit_per_minute"] == 60
    assert telemetry["monthly_quota"] == 1000


@pytest.mark.asyncio
async def test_api_key_authentication_failures():
    # 1. Invalid format
    with pytest.raises(HTTPException) as exc_info:
        await api_platform_service.authenticate_key("invalid_prefix_secret")
    assert exc_info.value.status_code == 401

    # 2. Non-existent key
    with pytest.raises(HTTPException) as exc_info:
        await api_platform_service.authenticate_key("dra_live_nonexistentkey12345678901234567890")
    assert exc_info.value.status_code == 401

    # 3. Deactivated / Revoked key
    created = await api_platform_service.create_api_key("user_dev_03", APIKeyCreate(name="To Revoke"))
    await api_platform_service.revoke_api_key(created.id, "user_dev_03")

    with pytest.raises(HTTPException) as exc_info:
        await api_platform_service.authenticate_key(created.secret_key)
    assert exc_info.value.status_code == 401
    assert "revoked" in exc_info.value.detail.lower()

    # 4. Expired key
    expired_key = await api_platform_service.create_api_key("user_dev_04", APIKeyCreate(name="Expired"))
    saved = await api_key_repo.get_by_id(expired_key.id)
    saved.expires_at = get_utc_now() - timedelta(days=1)

    with pytest.raises(HTTPException) as exc_info:
        await api_platform_service.authenticate_key(expired_key.secret_key)
    assert exc_info.value.status_code == 401
    assert "expired" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_rate_limiting_enforcement():
    user_id = "user_dev_05"
    key_create = APIKeyCreate(name="Rate Limited Key", rate_limit_per_minute=2)
    created = await api_platform_service.create_api_key(user_id=user_id, data=key_create)
    raw_key = created.secret_key

    # 1st request -> ok
    k1, t1 = await api_platform_service.authenticate_key(raw_key)
    await api_platform_service.record_api_call(k1, endpoint="/v1/research", request_tokens=50, response_tokens=50)

    # 2nd request -> ok
    k2, t2 = await api_platform_service.authenticate_key(raw_key)
    await api_platform_service.record_api_call(k2, endpoint="/v1/research", request_tokens=50, response_tokens=50)

    # 3rd request -> exceeds 2 req/min limit -> 429
    with pytest.raises(HTTPException) as exc_info:
        await api_platform_service.authenticate_key(raw_key)
    assert exc_info.value.status_code == 429
    assert "Rate limit exceeded" in exc_info.value.detail
    assert exc_info.value.headers.get("Retry-After") == "60"


@pytest.mark.asyncio
async def test_monthly_quota_enforcement():
    user_id = "user_dev_06"
    key_create = APIKeyCreate(name="Quota Key", monthly_quota=2, monthly_token_quota=1000)
    created = await api_platform_service.create_api_key(user_id=user_id, data=key_create)
    raw_key = created.secret_key

    # 1st and 2nd calls
    k, _ = await api_platform_service.authenticate_key(raw_key)
    await api_platform_service.record_api_call(k, endpoint="/v1/research", request_tokens=100, response_tokens=100)
    await api_platform_service.record_api_call(k, endpoint="/v1/research", request_tokens=100, response_tokens=100)

    # 3rd call exceeds monthly quota
    with pytest.raises(HTTPException) as exc_info:
        await api_platform_service.authenticate_key(raw_key)
    assert exc_info.value.status_code == 429
    assert "Monthly request quota exceeded" in exc_info.value.detail


@pytest.mark.asyncio
async def test_api_usage_summary_and_telemetry():
    user_id = "user_dev_07"
    org_id = "org_omega_10"
    created = await api_platform_service.create_api_key(
        user_id=user_id,
        data=APIKeyCreate(name="Telemetry Key", organization_id=org_id, monthly_quota=100, monthly_token_quota=50_000)
    )

    k, _ = await api_platform_service.authenticate_key(created.secret_key)
    await api_platform_service.record_api_call(
        api_key=k,
        endpoint="/v1/research",
        request_tokens=200,
        response_tokens=300,
        latency_ms=120.0
    )

    summary = await api_platform_service.get_usage_summary(
        api_key_id=k.id,
        user_id=user_id,
        organization_id=org_id
    )

    assert summary.total_requests == 1
    assert summary.total_tokens == 500
    assert summary.total_cost_usd > 0.0
    assert summary.requests_remaining == 99
    assert summary.tokens_remaining == 49500


@pytest.mark.asyncio
async def test_v1_research_endpoint_integration():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create a user & api key
        user = UserInDB(id="user_api_tester", email="dev@app.com", hashed_password="pw")
        await user_repo.create(user)
        key_res = await api_platform_service.create_api_key(
            user_id=user.id,
            data=APIKeyCreate(name="Dev Integration Key", organization_id="org_test")
        )
        api_key = key_res.secret_key

        # 1. POST /v1/research with X-API-Key header
        payload = {
            "query": "Quantum Computing commercial hardware roadmap 2026",
            "depth": 1,
            "breadth": 2,
            "categories": ["web", "academic"]
        }
        res = await client.post(
            "/v1/research",
            headers={"X-API-Key": api_key},
            json=payload
        )
        assert res.status_code == 200
        data = res.json()
        assert "job" in data
        assert data["job"]["query"] == payload["query"]
        assert data["user_id"] == "user_api_tester"
        assert data["organization_id"] == "org_test"
        job_id = data["job"]["id"]

        # 2. GET /v1/research/{job_id}
        res_get = await client.get(
            f"/v1/research/{job_id}",
            headers={"Authorization": f"Bearer {api_key}"}
        )
        assert res_get.status_code == 200
        job_data = res_get.json()
        assert job_data["id"] == job_id

        # 3. GET /v1/usage
        res_usage = await client.get(
            "/v1/usage",
            headers={"X-API-Key": api_key}
        )
        assert res_usage.status_code == 200
        usage_data = res_usage.json()
        assert usage_data["total_requests"] >= 1


@pytest.mark.asyncio
async def test_v1_api_keys_management_endpoints():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        user = UserInDB(id="user_mgmt_01", email="mgmt@test.com", hashed_password="pw")
        await user_repo.create(user)
        jwt_token = create_access_token({"sub": user.id})
        auth_headers = {"Authorization": f"Bearer {jwt_token}"}

        # 1. POST /v1/api-keys
        res = await client.post(
            "/v1/api-keys",
            headers=auth_headers,
            json={"name": "New Client Key", "rate_limit_per_minute": 30}
        )
        assert res.status_code == 200
        key_data = res.json()
        assert "secret_key" in key_data
        assert key_data["name"] == "New Client Key"
        key_id = key_data["id"]

        # 2. GET /v1/api-keys
        res_list = await client.get("/v1/api-keys", headers=auth_headers)
        assert res_list.status_code == 200
        keys_list = res_list.json()
        assert len(keys_list) == 1
        assert keys_list[0]["id"] == key_id

        # 3. DELETE /v1/api-keys/{key_id}
        res_del = await client.delete(f"/v1/api-keys/{key_id}", headers=auth_headers)
        assert res_del.status_code == 200
        del_data = res_del.json()
        assert del_data["revoked"] is True

        # Verify key is now inactive
        revoked_key = await api_key_repo.get_by_id(key_id)
        assert revoked_key.is_active is False
