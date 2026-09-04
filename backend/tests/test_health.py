"""Test the health endpoint."""

import pytest


def test_health_endpoint(test_client):
    """Test that the health endpoint returns OK."""
    response = test_client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_cors_allows_the_configured_frontend_origin(test_client):
    response = test_client.options(
        "/health",
        headers={
            "origin": "http://localhost:5173",
            "access-control-request-method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_cors_does_not_allow_an_untrusted_origin(test_client):
    response = test_client.options(
        "/health",
        headers={
            "origin": "https://evil.example",
            "access-control-request-method": "GET",
        },
    )

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


@pytest.mark.asyncio
async def test_placeholder():
    """Placeholder test to verify pytest setup."""
    assert True
