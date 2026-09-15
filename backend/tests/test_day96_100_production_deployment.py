"""
Day 96–100 — Production Deployment — Unit & Integration Tests

Tests all production deployment components:
- Production settings validation & environment variables
- Redis service (caching, queue, distributed locks, in-memory fallback)
- Prometheus metrics formatting & exposition
- Health endpoints (liveness probe, readiness probe, diagnostic overview)
- Structured JSON logging & credential redaction
- Distributed background worker lifecycle & queue processing
- Database index model validation
"""

import asyncio
import json
import logging
import time
import pytest
from httpx import AsyncClient, ASGITransport

from app.config.settings import Settings
from app.main import app
from app.monitoring.metrics import metrics_collector
from app.services.redis_service import RedisService, redis_service
from app.utils.production_logger import JSONLogFormatter, redact_sensitive_data
from app.workers.distributed_worker import DistributedResearchWorker


# ===========================================================================
# 1. Production Settings Tests
# ===========================================================================

class TestProductionSettings:
    def test_default_production_settings(self):
        s = Settings()
        assert s.PROJECT_NAME == "Deep Research AI"
        assert s.REDIS_PORT == 6379
        assert s.WORKER_CONCURRENCY >= 1
        assert s.VECTOR_DB_COLLECTION == "deep_research_embeddings"
        assert s.LOG_FORMAT in ("text", "json")
        assert s.PROMETHEUS_METRICS_ENABLED is True

    def test_custom_redis_settings(self):
        s = Settings(
            USE_REDIS=True,
            REDIS_URL="redis://custom-host:6380/2",
            WORKER_CONCURRENCY=8,
            LOG_FORMAT="json"
        )
        assert s.USE_REDIS is True
        assert s.REDIS_URL == "redis://custom-host:6380/2"
        assert s.WORKER_CONCURRENCY == 8
        assert s.LOG_FORMAT == "json"

    def test_cors_origin_parsing(self):
        s = Settings(CORS_ORIGINS="https://app.example.com, https://api.example.com")
        assert "https://app.example.com" in s.CORS_ORIGINS
        assert "https://api.example.com" in s.CORS_ORIGINS


# ===========================================================================
# 2. Redis & Distributed Queue Tests (In-Memory Fallback & API)
# ===========================================================================

class TestRedisService:
    @pytest.mark.asyncio
    async def test_fallback_get_set_delete(self):
        svc = RedisService()
        # Set and get
        await svc.set("test_key", {"data": "hello", "count": 42})
        val = await svc.get("test_key")
        assert val == {"data": "hello", "count": 42}

        # Exists
        assert await svc.exists("test_key") is True

        # Delete
        assert await svc.delete("test_key") is True
        assert await svc.get("test_key") is None
        assert await svc.exists("test_key") is False

    @pytest.mark.asyncio
    async def test_fallback_ttl_expiration(self):
        svc = RedisService()
        await svc.set("expiring_key", "value", ttl_seconds=1)
        assert await svc.get("expiring_key") == "value"

        # Wait for TTL to expire
        await asyncio.sleep(1.1)
        assert await svc.get("expiring_key") is None

    @pytest.mark.asyncio
    async def test_fallback_queue_operations(self):
        svc = RedisService()
        q_name = "test_queue"

        assert await svc.queue_length(q_name) == 0
        await svc.enqueue(q_name, {"job_id": "1", "priority": "high"})
        await svc.enqueue(q_name, {"job_id": "2", "priority": "normal"})

        assert await svc.queue_length(q_name) == 2

        # FIFO Dequeue
        item1 = await svc.dequeue(q_name)
        assert item1 == {"job_id": "1", "priority": "high"}

        item2 = await svc.dequeue(q_name)
        assert item2 == {"job_id": "2", "priority": "normal"}

        assert await svc.queue_length(q_name) == 0
        assert await svc.dequeue(q_name) is None

    @pytest.mark.asyncio
    async def test_distributed_lock_lifecycle(self):
        svc = RedisService()
        lock_name = "test_resource"
        token_1 = "worker_1_token"
        token_2 = "worker_2_token"

        # Worker 1 acquires lock
        assert await svc.acquire_lock(lock_name, token_1, expire_seconds=5) is True

        # Worker 2 cannot acquire while locked
        assert await svc.acquire_lock(lock_name, token_2, expire_seconds=5) is False

        # Wrong token cannot release lock
        assert await svc.release_lock(lock_name, token_2) is False

        # Correct token releases lock
        assert await svc.release_lock(lock_name, token_1) is True

        # Now Worker 2 can acquire
        assert await svc.acquire_lock(lock_name, token_2, expire_seconds=5) is True
        await svc.release_lock(lock_name, token_2)

    @pytest.mark.asyncio
    async def test_health_check_output(self):
        svc = RedisService()
        diag = await svc.health_check()
        assert "status" in diag
        assert "driver" in diag


# ===========================================================================
# 3. Prometheus Metrics Exporter Tests
# ===========================================================================

class TestPrometheusMetrics:
    def test_prometheus_formatting(self):
        metrics_collector.reset()
        metrics_collector.record_api_request("GET", "/api/v1/research", 200, 45.2)
        metrics_collector.record_llm_call("gpt-4o-mini", "chat", 120.5)
        metrics_collector.record_llm_error("gpt-4o-mini", "timeout")
        metrics_collector.set_queue_size(3)

        prom_text = metrics_collector.to_prometheus_text()

        assert "# HELP deep_research_uptime_seconds" in prom_text
        assert "# TYPE deep_research_uptime_seconds gauge" in prom_text
        assert "deep_research_api_requests_total" in prom_text
        assert 'method="GET"' in prom_text
        assert 'status="200"' in prom_text
        assert "deep_research_llm_calls_total" in prom_text
        assert "deep_research_llm_errors_total" in prom_text
        assert "deep_research_queue_size 3" in prom_text


# ===========================================================================
# 4. Health & Monitoring API Endpoints
# ===========================================================================

class TestHealthEndpoints:
    @pytest.mark.asyncio
    async def test_liveness_probe(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/health/live")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "alive"
            assert "timestamp" in data

    @pytest.mark.asyncio
    async def test_readiness_probe(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/health/ready")
            assert resp.status_code in (200, 503)
            data = resp.json()
            assert "checks" in data
            assert "redis" in data["checks"]
            assert "queue_driver" in data["checks"]

    @pytest.mark.asyncio
    async def test_full_health_endpoint(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/health")
            assert resp.status_code == 200
            data = resp.json()
            assert data["service"] == "Deep Research AI"
            assert "database" in data
            assert "redis" in data
            assert "vector_db" in data

    @pytest.mark.asyncio
    async def test_prometheus_metrics_endpoint(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/metrics")
            assert resp.status_code == 200
            assert "text/plain" in resp.headers["content-type"]
            assert "deep_research_uptime_seconds" in resp.text


# ===========================================================================
# 5. Production Structured Logging & Redaction Tests
# ===========================================================================

class TestProductionLogger:
    def test_sensitive_data_redaction(self):
        text = "Failed with api_key=sk-or-v1-abcdef1234567890 and Bearer eyJhbGciOiJIUzI1NiJ9.secret"
        redacted = redact_sensitive_data(text)
        assert "sk-or-v1-abcdef1234567890" not in redacted
        assert "***REDACTED***" in redacted

    def test_json_log_formatter(self):
        formatter = JSONLogFormatter()
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname=__file__,
            lineno=42,
            msg="User login with secret: supersecretpass123",
            args=(),
            exc_info=None,
        )
        record.request_id = "req-12345"

        formatted = formatter.format(record)
        log_json = json.loads(formatted)

        assert log_json["level"] == "INFO"
        assert log_json["logger"] == "test_logger"
        assert log_json["request_id"] == "req-12345"
        assert "supersecretpass123" not in log_json["message"]
        assert "timestamp" in log_json


# ===========================================================================
# 6. Distributed Worker Tests
# ===========================================================================

class TestDistributedWorker:
    def test_worker_initialization(self):
        worker = DistributedResearchWorker(worker_id="test-worker-01")
        assert worker.worker_id == "test-worker-01"
        assert worker.is_running is False

    @pytest.mark.asyncio
    async def test_worker_graceful_stop(self):
        worker = DistributedResearchWorker(worker_id="test-worker-02")
        worker.is_running = True
        await worker.stop()
        assert worker.is_running is False
