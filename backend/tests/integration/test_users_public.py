"""
Tests for GET /users/{user_id} — public user profile.

The private /users/me and PATCH /users/me are covered in tests/test_auth.py.
These tests focus on the public-facing GET /users/{id} endpoint.
"""
import uuid

from httpx import AsyncClient

from app.models.user import User


def _auth(u: User) -> dict:
    return {"X-Dev-User-Id": str(u.id)}


async def test_get_user_returns_public_profile_fields(
    auth_client: AsyncClient, user: User, other_user: User
):
    response = await auth_client.get(f"/users/{other_user.id}", headers=_auth(user))
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(other_user.id)
    assert data["username"] == other_user.username
    assert "display_name" in data
    assert "avatar_url" in data


async def test_get_user_does_not_expose_email(
    auth_client: AsyncClient, user: User, other_user: User
):
    """Public profile must never include the email address."""
    response = await auth_client.get(f"/users/{other_user.id}", headers=_auth(user))
    assert response.status_code == 200
    assert "email" not in response.json()


async def test_get_user_can_view_own_public_profile(
    auth_client: AsyncClient, user: User
):
    response = await auth_client.get(f"/users/{user.id}", headers=_auth(user))
    assert response.status_code == 200
    assert response.json()["id"] == str(user.id)


async def test_get_user_with_display_name_set(
    auth_client: AsyncClient, user: User, other_user: User
):
    """display_name fixture value flows through correctly."""
    response = await auth_client.get(f"/users/{user.id}", headers=_auth(other_user))
    assert response.status_code == 200
    assert response.json()["display_name"] == "Integration User"


async def test_get_user_unknown_id_returns_404(
    auth_client: AsyncClient, user: User
):
    response = await auth_client.get(f"/users/{uuid.uuid4()}", headers=_auth(user))
    assert response.status_code == 404


async def test_get_user_requires_auth(auth_client: AsyncClient, user: User):
    response = await auth_client.get(f"/users/{user.id}")
    assert response.status_code == 401
