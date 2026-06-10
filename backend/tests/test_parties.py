"""
Tests for the parties and leaderboard endpoints.

Run with: cd backend && pytest tests/test_parties.py
Requires MOCK_AUTH=true (set via the mock_auth fixture).
"""
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.dependencies import get_db, get_redis
from app.main import app
from app.models.leaderboard import LeaderboardSnapshot
from app.models.party import Party, PartyMember
from app.models.tournament import Tournament
from app.models.user import User


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_auth(monkeypatch):
    monkeypatch.setattr(settings, "mock_auth", True)


@pytest.fixture
async def auth_client(db: AsyncSession, mock_auth):
    mock_redis = MagicMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.set = AsyncMock(return_value=True)
    mock_redis.aclose = AsyncMock()

    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_redis] = lambda: mock_redis
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
async def tournament(db: AsyncSession) -> Tournament:
    t = Tournament(name="FIFA World Cup 2026", season="2026", status="active")
    db.add(t)
    await db.commit()
    await db.refresh(t)
    return t


@pytest.fixture
async def user1(db: AsyncSession) -> User:
    u = User(cognito_sub="party-sub-1", username="partyuser1", email="party1@example.com")
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


@pytest.fixture
async def user2(db: AsyncSession) -> User:
    u = User(cognito_sub="party-sub-2", username="partyuser2", email="party2@example.com")
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


@pytest.fixture
async def system_user(db: AsyncSession) -> User:
    u = User(cognito_sub="__SYSTEM__", username="__system__", email="system@worldcup.internal")
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


def _auth(user: User) -> dict:
    return {"X-Dev-User-Id": str(user.id)}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _create_party_db(
    db: AsyncSession,
    owner: User,
    name: str = "Test Party",
    tournament_id=None,
    is_global: bool = False,
    invite_code: str | None = None,
) -> Party:
    code = invite_code or "TST" + str(uuid.uuid4()).replace("-", "")[:4].upper()
    party = Party(
        name=name,
        invite_code=code,
        created_by=owner.id,
        tournament_id=tournament_id,
        is_global=is_global,
    )
    db.add(party)
    await db.flush()
    db.add(PartyMember(party_id=party.id, user_id=owner.id, role="admin"))
    await db.commit()
    await db.refresh(party)
    return party


async def _add_member(db: AsyncSession, party: Party, user: User) -> None:
    db.add(PartyMember(party_id=party.id, user_id=user.id, role="member"))
    await db.commit()


async def _add_snapshot(
    db: AsyncSession,
    party: Party,
    user: User,
    tournament: Tournament,
    *,
    total_points: int,
    exact_scores: int,
    predictions_made: int = 1,
    rank: int,
    computed_at: datetime | None = None,
) -> LeaderboardSnapshot:
    snap = LeaderboardSnapshot(
        party_id=party.id,
        user_id=user.id,
        tournament_id=tournament.id,
        total_points=total_points,
        exact_scores=exact_scores,
        predictions_made=predictions_made,
        rank=rank,
        computed_at=computed_at or datetime.now(timezone.utc),
    )
    db.add(snap)
    await db.commit()
    await db.refresh(snap)
    return snap


# ---------------------------------------------------------------------------
# POST /parties — create party
# ---------------------------------------------------------------------------


async def test_create_party_generates_7char_invite_code(
    auth_client: AsyncClient, user1: User
):
    resp = await auth_client.post(
        "/parties", json={"name": "My Party"}, headers=_auth(user1)
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "My Party"
    code = data["invite_code"]
    assert len(code) == 7
    assert code.isalnum()
    assert code == code.upper()


async def test_create_party_invite_codes_are_unique(
    auth_client: AsyncClient, user1: User
):
    codes = set()
    for i in range(5):
        resp = await auth_client.post(
            "/parties", json={"name": f"Party {i}"}, headers=_auth(user1)
        )
        assert resp.status_code == 200
        codes.add(resp.json()["invite_code"])
    assert len(codes) == 5


async def test_create_party_creator_is_admin_and_member(
    auth_client: AsyncClient, user1: User, db: AsyncSession
):
    resp = await auth_client.post(
        "/parties", json={"name": "Admin Test"}, headers=_auth(user1)
    )
    assert resp.status_code == 200
    party_id = uuid.UUID(resp.json()["id"])

    from sqlalchemy import select
    from app.models.party import PartyMember

    member = (
        await db.execute(
            select(PartyMember).where(
                PartyMember.party_id == party_id,
                PartyMember.user_id == user1.id,
            )
        )
    ).scalar_one_or_none()
    assert member is not None
    assert member.role == "admin"


# ---------------------------------------------------------------------------
# POST /parties/join — join by invite code
# ---------------------------------------------------------------------------


async def test_join_party_adds_user(
    auth_client: AsyncClient, db: AsyncSession, user1: User, user2: User
):
    party = await _create_party_db(db, user1)

    resp = await auth_client.post(
        "/parties/join", json={"invite_code": party.invite_code}, headers=_auth(user2)
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == str(party.id)

    from sqlalchemy import select

    member = (
        await db.execute(
            select(PartyMember).where(
                PartyMember.party_id == party.id,
                PartyMember.user_id == user2.id,
            )
        )
    ).scalar_one_or_none()
    assert member is not None
    assert member.role == "member"


async def test_join_invalid_code_returns_404(
    auth_client: AsyncClient, user1: User
):
    resp = await auth_client.post(
        "/parties/join", json={"invite_code": "INVALID1"}, headers=_auth(user1)
    )
    assert resp.status_code == 404


async def test_cannot_join_same_party_twice(
    auth_client: AsyncClient, db: AsyncSession, user1: User, user2: User
):
    party = await _create_party_db(db, user1)

    await auth_client.post(
        "/parties/join", json={"invite_code": party.invite_code}, headers=_auth(user2)
    )
    resp = await auth_client.post(
        "/parties/join", json={"invite_code": party.invite_code}, headers=_auth(user2)
    )
    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# DELETE /parties/{id}/leave — leave party
# ---------------------------------------------------------------------------


async def test_leave_party_removes_member(
    auth_client: AsyncClient, db: AsyncSession, user1: User, user2: User
):
    party = await _create_party_db(db, user1)
    await _add_member(db, party, user2)

    resp = await auth_client.delete(
        f"/parties/{party.id}/leave", headers=_auth(user2)
    )
    assert resp.status_code == 200

    from sqlalchemy import select

    member = (
        await db.execute(
            select(PartyMember).where(
                PartyMember.party_id == party.id,
                PartyMember.user_id == user2.id,
            )
        )
    ).scalar_one_or_none()
    assert member is None


async def test_cannot_leave_global_party(
    auth_client: AsyncClient,
    db: AsyncSession,
    user1: User,
    system_user: User,
    tournament: Tournament,
):
    global_party = await _create_party_db(
        db, system_user, name="Global", is_global=True, invite_code="GLOBAL"
    )
    await _add_member(db, global_party, user1)

    resp = await auth_client.delete(
        f"/parties/{global_party.id}/leave", headers=_auth(user1)
    )
    assert resp.status_code == 403


async def test_leave_party_not_member_returns_404(
    auth_client: AsyncClient, db: AsyncSession, user1: User, user2: User
):
    party = await _create_party_db(db, user1)

    resp = await auth_client.delete(
        f"/parties/{party.id}/leave", headers=_auth(user2)
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /parties/{id}/leaderboard — leaderboard
# ---------------------------------------------------------------------------


async def test_leaderboard_returns_ranked_results(
    auth_client: AsyncClient,
    db: AsyncSession,
    user1: User,
    user2: User,
    tournament: Tournament,
):
    party = await _create_party_db(db, user1)
    await _add_member(db, party, user2)

    # user1: 5 pts (rank 1), user2: 3 pts (rank 2)
    await _add_snapshot(db, party, user1, tournament, total_points=5, exact_scores=1, rank=1)
    await _add_snapshot(db, party, user2, tournament, total_points=3, exact_scores=0, rank=2)

    resp = await auth_client.get(
        f"/parties/{party.id}/leaderboard",
        params={"tournament_id": str(tournament.id)},
        headers=_auth(user1),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["party_id"] == str(party.id)
    assert data["tournament_id"] == str(tournament.id)
    entries = data["entries"]
    assert len(entries) == 2
    assert entries[0]["rank"] == 1
    assert entries[0]["total_points"] == 5
    assert entries[1]["rank"] == 2
    assert entries[1]["total_points"] == 3


async def test_leaderboard_tiebreaker_exact_scores(
    auth_client: AsyncClient,
    db: AsyncSession,
    user1: User,
    user2: User,
    tournament: Tournament,
):
    """User with more exact scores wins the tiebreaker when total points are equal."""
    party = await _create_party_db(db, user1)
    await _add_member(db, party, user2)

    # Both have 5 total points; user1 has 2 exact scores, user2 has 1.
    await _add_snapshot(db, party, user1, tournament, total_points=5, exact_scores=2, rank=1)
    await _add_snapshot(db, party, user2, tournament, total_points=5, exact_scores=1, rank=2)

    resp = await auth_client.get(
        f"/parties/{party.id}/leaderboard",
        params={"tournament_id": str(tournament.id)},
        headers=_auth(user1),
    )
    assert resp.status_code == 200
    entries = resp.json()["entries"]
    assert len(entries) == 2

    first = next(e for e in entries if e["user_id"] == str(user1.id))
    second = next(e for e in entries if e["user_id"] == str(user2.id))
    assert first["rank"] == 1
    assert second["rank"] == 2
    assert first["exact_scores"] > second["exact_scores"]


async def test_leaderboard_empty_when_no_snapshots(
    auth_client: AsyncClient,
    db: AsyncSession,
    user1: User,
    tournament: Tournament,
):
    """Empty leaderboard is returned when no snapshots and no scored predictions exist."""
    party = await _create_party_db(db, user1)

    resp = await auth_client.get(
        f"/parties/{party.id}/leaderboard",
        params={"tournament_id": str(tournament.id)},
        headers=_auth(user1),
    )
    assert resp.status_code == 200
    assert resp.json()["entries"] == []


async def test_leaderboard_non_member_returns_403(
    auth_client: AsyncClient,
    db: AsyncSession,
    user1: User,
    user2: User,
    tournament: Tournament,
):
    party = await _create_party_db(db, user1)

    resp = await auth_client.get(
        f"/parties/{party.id}/leaderboard",
        params={"tournament_id": str(tournament.id)},
        headers=_auth(user2),
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# GET /parties — list user's parties
# ---------------------------------------------------------------------------


async def test_list_parties_includes_own_party(
    auth_client: AsyncClient, db: AsyncSession, user1: User
):
    await _create_party_db(db, user1, name="Alpha")
    await _create_party_db(db, user1, name="Beta")

    resp = await auth_client.get("/parties", headers=_auth(user1))
    assert resp.status_code == 200
    names = {p["name"] for p in resp.json()}
    assert {"Alpha", "Beta"}.issubset(names)


async def test_list_parties_excludes_unjoined(
    auth_client: AsyncClient, db: AsyncSession, user1: User, user2: User
):
    await _create_party_db(db, user2, name="OtherParty")

    resp = await auth_client.get("/parties", headers=_auth(user1))
    assert resp.status_code == 200
    names = [p["name"] for p in resp.json()]
    assert "OtherParty" not in names


# ---------------------------------------------------------------------------
# GET /parties/invite/{code} — public preview
# ---------------------------------------------------------------------------


async def test_party_preview_is_public(
    auth_client: AsyncClient, db: AsyncSession, user1: User
):
    party = await _create_party_db(db, user1, name="Preview Party")

    # Hit without auth header — should still succeed (public endpoint)
    resp = await auth_client.get(f"/parties/invite/{party.invite_code}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Preview Party"


async def test_party_preview_invalid_code_returns_404(auth_client: AsyncClient):
    resp = await auth_client.get("/parties/invite/NOTEXIST")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /parties/{id} — delete party
# ---------------------------------------------------------------------------


async def test_admin_can_delete_party(
    auth_client: AsyncClient, db: AsyncSession, user1: User
):
    party = await _create_party_db(db, user1)

    resp = await auth_client.delete(f"/parties/{party.id}", headers=_auth(user1))
    assert resp.status_code == 200

    deleted = await db.get(Party, party.id)
    assert deleted is None


async def test_non_admin_cannot_delete_party(
    auth_client: AsyncClient, db: AsyncSession, user1: User, user2: User
):
    party = await _create_party_db(db, user1)
    await _add_member(db, party, user2)

    resp = await auth_client.delete(f"/parties/{party.id}", headers=_auth(user2))
    assert resp.status_code == 403


async def test_cannot_delete_global_party(
    auth_client: AsyncClient,
    db: AsyncSession,
    user1: User,
    system_user: User,
):
    global_party = await _create_party_db(
        db, system_user, name="Global", is_global=True, invite_code="GLOBALX"
    )
    db.add(PartyMember(party_id=global_party.id, user_id=user1.id, role="admin"))
    await db.commit()

    resp = await auth_client.delete(f"/parties/{global_party.id}", headers=_auth(user1))
    assert resp.status_code == 403
