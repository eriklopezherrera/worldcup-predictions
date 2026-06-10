"""Tests for GET /health."""


async def test_health_returns_ok(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_health_no_auth_required(client):
    """Health check must be accessible without any credentials."""
    response = await client.get("/health")
    assert response.status_code == 200
