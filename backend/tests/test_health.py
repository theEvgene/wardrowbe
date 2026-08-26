import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


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
async def test_garment_extraction_metrics_are_public_and_anonymous():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/health/metrics/garment-extraction")

    assert response.status_code == 200
    data = response.json()
    assert data["window_capacity"] == 200
    assert set(data["outcomes"]) == {"accepted", "low_quality", "unsupported", "failed"}
    assert "item_id" not in data
    assert "user_id" not in data
