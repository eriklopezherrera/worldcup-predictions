"""
Tests for mock auth mode, GET /users/me, and PATCH /users/me.

All tests run with MOCK_AUTH=true — no Cognito or Redis required.
"""
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.dependencies import get_db, get_redis
from app.main import app
from app.models.user import User


@pytest.fixture
def mock_auth(monkeypatch):
    monkeypatch.setattr(settings, "mock_auth", True)


@pytest.fixture
async def test_user(db: AsyncSession) -> User:
    user = User(
        cognito_sub="test-sub-abc123",
        username="testuser",
        email="test@example.com",
        display_name="Test User",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest.fixture
async def auth_client(db: AsyncSession, mock_auth):
    """HTTP client with mock auth and a shared DB session."""
    mock_redis = MagicMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.set = AsyncMock(return_value=True)
    mock_redis.aclose = AsyncMock()

    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_redis] = lambda: mock_redis
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Mock auth mode behaviour
# ---------------------------------------------------------------------------


async def test_mock_auth_missing_header_returns_401(auth_client: AsyncClient):
    response = await auth_client.get("/users/me")
    assert response.status_code == 401
    assert "X-Dev-User-Id" in response.json()["detail"]


async def test_mock_auth_malformed_uuid_returns_400(auth_client: AsyncClient):
    response = await auth_client.get("/users/me", headers={"X-Dev-User-Id": "not-a-uuid"})
    assert response.status_code == 400


async def test_mock_auth_unknown_user_returns_404(auth_client: AsyncClient):
    response = await auth_client.get(
        "/users/me",
        headers={"X-Dev-User-Id": "00000000-0000-0000-0000-000000000000"},
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# GET /users/me
# ---------------------------------------------------------------------------


async def test_get_me_returns_own_profile(auth_client: AsyncClient, test_user: User):
    response = await auth_client.get(
        "/users/me",
        headers={"X-Dev-User-Id": str(test_user.id)},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(test_user.id)
    assert data["username"] == "testuser"
    assert data["email"] == "test@example.com"
    assert data["display_name"] == "Test User"
    assert data["is_active"] is True


# ---------------------------------------------------------------------------
# PATCH /users/me
# ---------------------------------------------------------------------------


async def test_patch_me_updates_display_name(auth_client: AsyncClient, test_user: User):
    response = await auth_client.patch(
        "/users/me",
        json={"display_name": "Updated Name"},
        headers={"X-Dev-User-Id": str(test_user.id)},
    )
    assert response.status_code == 200
    assert response.json()["display_name"] == "Updated Name"


async def test_patch_me_updates_avatar_url(auth_client: AsyncClient, test_user: User):
    response = await auth_client.patch(
        "/users/me",
        json={"avatar_url": "https://example.com/avatar.png"},
        headers={"X-Dev-User-Id": str(test_user.id)},
    )
    assert response.status_code == 200
    assert response.json()["avatar_url"] == "https://example.com/avatar.png"


async def test_patch_me_omitted_field_is_unchanged(auth_client: AsyncClient, test_user: User):
    """Omitting a field from the body must leave its current value intact."""
    await auth_client.patch(
        "/users/me",
        json={"display_name": "Name", "avatar_url": "https://example.com/a.png"},
        headers={"X-Dev-User-Id": str(test_user.id)},
    )
    response = await auth_client.patch(
        "/users/me",
        json={"display_name": "New Name"},
        headers={"X-Dev-User-Id": str(test_user.id)},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["display_name"] == "New Name"
    assert data["avatar_url"] == "https://example.com/a.png"


async def test_patch_me_explicit_null_clears_field(auth_client: AsyncClient, test_user: User):
    """Sending null for a field must clear it (set to None), not leave it unchanged."""
    await auth_client.patch(
        "/users/me",
        json={"display_name": "Name", "avatar_url": "https://example.com/a.png"},
        headers={"X-Dev-User-Id": str(test_user.id)},
    )
    response = await auth_client.patch(
        "/users/me",
        json={"avatar_url": None},
        headers={"X-Dev-User-Id": str(test_user.id)},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["avatar_url"] is None
    assert data["display_name"] == "Name"  # untouched
