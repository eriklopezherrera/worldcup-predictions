"""
Tests for GET /parties/{party_id}/members and party membership edge cases:
  - members list shape and access control
  - member_count accuracy across create / join operations
  - max_members enforcement (HTTP 409 when party is full)
  - GET /parties/{id} access control for non-members

These complement tests/test_parties.py which covers create, join, leave, delete,
leaderboard, and the invite-code preview endpoint.
"""
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.party import Party, PartyMember
from app.models.user import User


def _auth(u: User) -> dict:
    return {"X-Dev-User-Id": str(u.id)}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _create_party(
    db: AsyncSession,
    owner: User,
    name: str = "Test Party",
    max_members: int = 200,
) -> Party:
    code = "MBR" + str(uuid.uuid4()).replace("-", "")[:5].upper()
    party = Party(name=name, invite_code=code, created_by=owner.id, max_members=max_members)
    db.add(party)
    await db.flush()
    db.add(PartyMember(party_id=party.id, user_id=owner.id, role="admin"))
    await db.commit()
    await db.refresh(party)
    return party


async def _add_member(db: AsyncSession, party: Party, user: User, role: str = "member") -> None:
    db.add(PartyMember(party_id=party.id, user_id=user.id, role=role))
    await db.commit()


# ---------------------------------------------------------------------------
# GET /parties/{id}/members — response shape
# ---------------------------------------------------------------------------


async def test_members_list_contains_owner(
    auth_client: AsyncClient, db: AsyncSession, user: User
):
    party = await _create_party(db, user)
    response = await auth_client.get(f"/parties/{party.id}/members", headers=_auth(user))
    assert response.status_code == 200
    members = response.json()
    assert len(members) == 1
    assert members[0]["user_id"] == str(user.id)
    assert members[0]["role"] == "admin"


async def test_members_list_has_required_fields(
    auth_client: AsyncClient, db: AsyncSession, user: User
):
    party = await _create_party(db, user)
    response = await auth_client.get(f"/parties/{party.id}/members", headers=_auth(user))
    assert response.status_code == 200
    member = response.json()[0]
    assert "user_id" in member
    assert "username" in member
    assert "display_name" in member
    assert "avatar_url" in member
    assert "role" in member
    assert "joined_at" in member
    assert "total_points" in member
    assert "rank" in member


async def test_members_list_includes_all_members(
    auth_client: AsyncClient, db: AsyncSession, user: User, other_user: User
):
    party = await _create_party(db, user)
    await _add_member(db, party, other_user)

    response = await auth_client.get(f"/parties/{party.id}/members", headers=_auth(user))
    assert response.status_code == 200
    members = response.json()
    assert len(members) == 2
    user_ids = {m["user_id"] for m in members}
    assert str(user.id) in user_ids
    assert str(other_user.id) in user_ids


async def test_members_list_shows_correct_roles(
    auth_client: AsyncClient, db: AsyncSession, user: User, other_user: User
):
    party = await _create_party(db, user)
    await _add_member(db, party, other_user, role="member")

    response = await auth_client.get(f"/parties/{party.id}/members", headers=_auth(user))
    members = response.json()
    roles = {m["user_id"]: m["role"] for m in members}
    assert roles[str(user.id)] == "admin"
    assert roles[str(other_user.id)] == "member"


# ---------------------------------------------------------------------------
# GET /parties/{id}/members — access control
# ---------------------------------------------------------------------------


async def test_members_list_non_member_returns_403(
    auth_client: AsyncClient, db: AsyncSession, user: User, other_user: User
):
    party = await _create_party(db, user)
    response = await auth_client.get(f"/parties/{party.id}/members", headers=_auth(other_user))
    assert response.status_code == 403


async def test_members_list_requires_auth(
    auth_client: AsyncClient, db: AsyncSession, user: User
):
    party = await _create_party(db, user)
    response = await auth_client.get(f"/parties/{party.id}/members")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# member_count accuracy
# ---------------------------------------------------------------------------


async def test_create_party_member_count_is_one(
    auth_client: AsyncClient, user: User
):
    resp = await auth_client.post("/parties", json={"name": "Solo Party"}, headers=_auth(user))
    assert resp.status_code == 200
    assert resp.json()["member_count"] == 1


async def test_join_party_increments_member_count(
    auth_client: AsyncClient, db: AsyncSession, user: User, other_user: User
):
    party = await _create_party(db, user)

    resp = await auth_client.post(
        "/parties/join",
        json={"invite_code": party.invite_code},
        headers=_auth(other_user),
    )
    assert resp.status_code == 200
    assert resp.json()["member_count"] == 2


async def test_get_party_member_count_matches_actual_members(
    auth_client: AsyncClient, db: AsyncSession, user: User, other_user: User
):
    party = await _create_party(db, user)
    await _add_member(db, party, other_user)

    resp = await auth_client.get(f"/parties/{party.id}", headers=_auth(user))
    assert resp.status_code == 200
    assert resp.json()["member_count"] == 2


async def test_list_parties_member_count_is_accurate(
    auth_client: AsyncClient, db: AsyncSession, user: User, other_user: User
):
    party = await _create_party(db, user)
    await _add_member(db, party, other_user)

    resp = await auth_client.get("/parties", headers=_auth(user))
    assert resp.status_code == 200
    our_party = next((p for p in resp.json() if p["id"] == str(party.id)), None)
    assert our_party is not None
    assert our_party["member_count"] == 2


# ---------------------------------------------------------------------------
# max_members enforcement
# ---------------------------------------------------------------------------


async def test_join_full_party_returns_409(
    auth_client: AsyncClient, db: AsyncSession, user: User
):
    party = await _create_party(db, user, max_members=1)

    extra = User(cognito_sub="extra-sub-99", username="extrauser99", email="extra99@example.com")
    db.add(extra)
    await db.commit()
    await db.refresh(extra)

    resp = await auth_client.post(
        "/parties/join",
        json={"invite_code": party.invite_code},
        headers=_auth(extra),
    )
    assert resp.status_code == 409
    assert "full" in resp.json()["detail"].lower()


async def test_party_max_members_field_is_present_in_response(
    auth_client: AsyncClient, user: User
):
    resp = await auth_client.post("/parties", json={"name": "Check Max"}, headers=_auth(user))
    assert resp.status_code == 200
    assert "max_members" in resp.json()
    assert resp.json()["max_members"] > 0


# ---------------------------------------------------------------------------
# GET /parties/{id} — access control
# ---------------------------------------------------------------------------


async def test_get_party_non_member_returns_403(
    auth_client: AsyncClient, db: AsyncSession, user: User, other_user: User
):
    party = await _create_party(db, user)
    resp = await auth_client.get(f"/parties/{party.id}", headers=_auth(other_user))
    assert resp.status_code == 403


async def test_get_party_not_found_returns_404(
    auth_client: AsyncClient, user: User
):
    resp = await auth_client.get(f"/parties/{uuid.uuid4()}", headers=_auth(user))
    assert resp.status_code == 404
