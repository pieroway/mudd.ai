"""Test the health endpoint."""

import pytest


def test_health_endpoint(test_client):
    """Test that the health endpoint returns OK."""
    response = test_client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_placeholder():
    """Placeholder test to verify pytest setup."""
    assert True
