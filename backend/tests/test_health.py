"""Tests for the /health endpoint."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check_returns_200(client: AsyncClient):
    """Health endpoint should return 200 with status info."""
    response = await client.get("/health")
    assert response.status_code == 200

    data = response.json()
    assert "status" in data
    assert "app" in data
    assert data["app"] == "QuizRoyale"
    assert "version" in data
    assert "services" in data


@pytest.mark.asyncio
async def test_health_check_contains_service_status(client: AsyncClient):
    """Health check should report database and redis status."""
    response = await client.get("/health")
    data = response.json()

    assert "database" in data["services"]
    assert "redis" in data["services"]


@pytest.mark.asyncio
async def test_docs_endpoint_available(client: AsyncClient):
    """Swagger docs should be accessible."""
    response = await client.get("/docs")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_api_auth_register_endpoint_exists(client: AsyncClient):
    """Register endpoint should exist and accept POST."""
    response = await client.post("/api/auth/register", json={
        "username": "testuser",
        "password": "test123456",
    })
    # Should be 201 (created) or validation error, not 404
    assert response.status_code != 404
