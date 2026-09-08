import pytest
import httpx
from app.main import app


@pytest.mark.asyncio
async def test_health_endpoint():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "service" in data


@pytest.mark.asyncio
async def test_start_research_job():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post("/api/v1/research/start", json={
            "query": "State of Quantum Computing 2026",
            "depth": 2,
            "breadth": 3,
            "categories": ["web", "academic", "market"]
        })
    assert response.status_code == 200
    job = response.json()
    assert "id" in job
    assert job["query"] == "State of Quantum Computing 2026"
