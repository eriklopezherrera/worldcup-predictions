"""
Tests for tournament and match endpoints.

Run with: cd backend && pytest tests/test_matches.py
Requires MOCK_AUTH=true (set via the mock_auth fixture).
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.dependencies import get_db, get_redis
from app.main import app
from app.models.match import Match
from app.models.tournament import Tournament
from app.models.user import User


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_auth(monkeypatch):
    monkeypatch.setattr(settings, "mock_auth", True)


@pytest.fixture
async def test_user(db: AsyncSession) -> User:
    user = User(
        cognito_sub="match-test-sub",
        username="matchuser",
        email="match@example.com",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


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
async def matches(db: AsyncSession, tournament: Tournament) -> list[Match]:
    now = datetime.now(timezone.utc)
    past = Match(
        tournament_id=tournament.id,
        kickoff_utc=now - timedelta(hours=2),
        stage="group_stage",
        group_name="A",
        status="finished",
        home_score=2,
        away_score=1,
    )
    future = Match(
        tournament_id=tournament.id,
        kickoff_utc=now + timedelta(hours=2),
        stage="group_stage",
        group_name="B",
        status="scheduled",
    )
    db.add_all([past, future])
    await db.commit()
    await db.refresh(past)
    await db.refresh(future)
    return [past, future]


def _auth(user: User) -> dict:
    return {"X-Dev-User-Id": str(user.id)}


# ---------------------------------------------------------------------------
# GET /tournaments
# ---------------------------------------------------------------------------


async def test_get_tournaments_returns_list(
    auth_client: AsyncClient, test_user: User, tournament: Tournament
):
    response = await auth_client.get("/tournaments", headers=_auth(test_user))
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    entry = data[0]
    assert entry["name"] == "FIFA World Cup 2026"
    assert entry["season"] == "2026"
    assert entry["status"] == "active"
    assert "id" in entry


async def test_get_tournaments_empty_when_none_exist(
    auth_client: AsyncClient, test_user: User
):
    response = await auth_client.get("/tournaments", headers=_auth(test_user))
    assert response.status_code == 200
    assert response.json() == []


async def test_get_tournaments_requires_auth(auth_client: AsyncClient):
    response = await auth_client.get("/tournaments")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# GET /tournaments/{id}/matches
# ---------------------------------------------------------------------------


async def test_get_tournament_matches_returns_all(
    auth_client: AsyncClient,
    test_user: User,
    tournament: Tournament,
    matches: list[Match],
):
    response = await auth_client.get(
        f"/tournaments/{tournament.id}/matches", headers=_auth(test_user)
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    # ordered by kickoff_utc ascending — past match first
    assert data[0]["status"] == "finished"
    assert data[1]["status"] == "scheduled"


async def test_get_tournament_matches_filter_by_stage(
    auth_client: AsyncClient,
    test_user: User,
    tournament: Tournament,
    matches: list[Match],
):
    response = await auth_client.get(
        f"/tournaments/{tournament.id}/matches",
        params={"stage": "group_stage"},
        headers=_auth(test_user),
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert all(m["stage"] == "group_stage" for m in data)


async def test_get_tournament_matches_filter_by_group(
    auth_client: AsyncClient,
    test_user: User,
    tournament: Tournament,
    matches: list[Match],
):
    response = await auth_client.get(
        f"/tournaments/{tournament.id}/matches",
        params={"group": "A"},
        headers=_auth(test_user),
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["group_name"] == "A"


async def test_get_tournament_matches_filter_by_status(
    auth_client: AsyncClient,
    test_user: User,
    tournament: Tournament,
    matches: list[Match],
):
    response = await auth_client.get(
        f"/tournaments/{tournament.id}/matches",
        params={"status": "scheduled"},
        headers=_auth(test_user),
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["status"] == "scheduled"


# ---------------------------------------------------------------------------
# is_locked field (via GET /matches/{id})
# ---------------------------------------------------------------------------


async def test_match_is_locked_for_past_kickoff(
    auth_client: AsyncClient,
    test_user: User,
    tournament: Tournament,
    matches: list[Match],
):
    past_match = matches[0]
    response = await auth_client.get(f"/matches/{past_match.id}", headers=_auth(test_user))
    assert response.status_code == 200
    assert response.json()["is_locked"] is True


async def test_match_is_not_locked_for_future_kickoff(
    auth_client: AsyncClient,
    test_user: User,
    tournament: Tournament,
    matches: list[Match],
):
    future_match = matches[1]
    response = await auth_client.get(f"/matches/{future_match.id}", headers=_auth(test_user))
    assert response.status_code == 200
    assert response.json()["is_locked"] is False


async def test_match_includes_actual_result_when_finished(
    auth_client: AsyncClient,
    test_user: User,
    tournament: Tournament,
    matches: list[Match],
):
    past_match = matches[0]  # home_score=2, away_score=1 → home_win
    response = await auth_client.get(f"/matches/{past_match.id}", headers=_auth(test_user))
    assert response.status_code == 200
    assert response.json()["actual_result"] == "home_win"


async def test_match_actual_result_null_when_unfinished(
    auth_client: AsyncClient,
    test_user: User,
    tournament: Tournament,
    matches: list[Match],
):
    future_match = matches[1]  # no scores set
    response = await auth_client.get(f"/matches/{future_match.id}", headers=_auth(test_user))
    assert response.status_code == 200
    assert response.json()["actual_result"] is None


async def test_match_prediction_null_when_none_made(
    auth_client: AsyncClient,
    test_user: User,
    tournament: Tournament,
    matches: list[Match],
):
    response = await auth_client.get(f"/matches/{matches[0].id}", headers=_auth(test_user))
    assert response.status_code == 200
    assert response.json()["my_prediction"] is None


async def test_match_not_found_returns_404(
    auth_client: AsyncClient, test_user: User, tournament: Tournament
):
    response = await auth_client.get(
        "/matches/00000000-0000-0000-0000-000000000000", headers=_auth(test_user)
    )
    assert response.status_code == 404


async def test_tournament_matches_include_is_locked_field(
    auth_client: AsyncClient,
    test_user: User,
    tournament: Tournament,
    matches: list[Match],
):
    """is_locked must be present in every match returned by the list endpoint."""
    response = await auth_client.get(
        f"/tournaments/{tournament.id}/matches", headers=_auth(test_user)
    )
    assert response.status_code == 200
    data = response.json()
    assert all("is_locked" in m for m in data)
    locked_flags = {m["is_locked"] for m in data}
    assert True in locked_flags   # past match is locked
    assert False in locked_flags  # future match is not
