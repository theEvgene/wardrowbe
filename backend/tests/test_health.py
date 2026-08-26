from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

import app.api.health as health_api
from app.main import app
from app.services.garment_extraction_metrics import GarmentExtractionMetrics


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    """Test that health check endpoint returns OK."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


@pytest.mark.asyncio
async def test_health_check_includes_version(client: AsyncClient):
    """Test that health check includes version info."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert "version" in data or "status" in data


@pytest.mark.asyncio
async def test_garment_extraction_metrics_are_shared_persistent_and_anonymous(monkeypatch):
    key_prefix = f"test:garment-extraction:{uuid4()}"
    writer = GarmentExtractionMetrics(key_prefix=key_prefix)
    reader_after_restart = GarmentExtractionMetrics(key_prefix=key_prefix)
    await writer.record(
        outcome="accepted",
        garment_category="upper",
        duration_ms=42.5,
        quality={
            "mask_area_ratio": 0.31,
            "largest_component_ratio": 0.98,
            "semantic_leakage_risk": 0.0,
        },
    )
    monkeypatch.setattr(health_api, "garment_extraction_metrics", reader_after_restart)

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/health/metrics/garment-extraction")
    finally:
        await writer.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["scope"] == "shared_redis"
    assert data["available"] is True
    assert data["total_requests"] == 1
    assert data["window_size"] == 1
    assert data["window_capacity"] == 200
    assert data["outcomes"]["accepted"] == 1
    assert data["quality"]["semantic_leakage_samples"] == 1
    assert set(data["outcomes"]) == {"accepted", "low_quality", "unsupported", "failed"}
    assert "item_id" not in str(data)
    assert "user_id" not in str(data)
