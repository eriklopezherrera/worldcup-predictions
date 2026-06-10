"""
Tests for the admin match-result endpoint.

Run with: cd backend && pytest tests/test_admin.py
Requires MOCK_AUTH=true (set via the mock_auth fixture).
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.dependencies import get_db, get_redis
from app.main import app
from app.models.leaderboard import LeaderboardSnapshot
from app.models.match import Match
from app.models.party import Party, PartyMember
from app.models.prediction import Prediction
from app.models.tournament import Tournament
from app.models.user import User


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_auth(monkeypatch):
    monkeypatch.setattr(settings, "mock_auth", True)


@pytest.fixture
async def admin_user(db: AsyncSession) -> User:
    user = User(
        cognito_sub="admin-test-sub",
        username="adminuser",
        email="admin@example.com",
        is_admin=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest.fixture
async def regular_user(db: AsyncSession) -> User:
    user = User(
        cognito_sub="regular-test-sub",
        username="regularuser",
        email="regular@example.com",
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
async def match(db: AsyncSession, tournament: Tournament) -> Match:
    m = Match(
        tournament_id=tournament.id,
        kickoff_utc=datetime.now(timezone.utc) - timedelta(hours=2),
        stage="group_stage",
        group_name="A",
        status="scheduled",
    )
    db.add(m)
    await db.commit()
    await db.refresh(m)
    return m


@pytest.fixture
async def prediction(db: AsyncSession, regular_user: User, match: Match) -> Prediction:
    p = Prediction(
        user_id=regular_user.id,
        match_id=match.id,
        predicted_home_score=2,
        predicted_away_score=1,
    )
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return p


@pytest.fixture
async def party(
    db: AsyncSession, regular_user: User, tournament: Tournament
) -> Party:
    p = Party(
        name="Test Party",
        invite_code="TESTCODE",
        created_by=regular_user.id,
        tournament_id=tournament.id,
    )
    db.add(p)
    await db.commit()
    db.add(PartyMember(party_id=p.id, user_id=regular_user.id, role="owner"))
    await db.commit()
    await db.refresh(p)
    return p


def _auth(user: User) -> dict:
    return {"X-Dev-User-Id": str(user.id)}


def _url(match: Match) -> str:
    return f"/admin/matches/{match.id}/result"


# ---------------------------------------------------------------------------
# Authorization
# ---------------------------------------------------------------------------


async def test_non_admin_gets_403(
    auth_client: AsyncClient, regular_user: User, match: Match
):
    response = await auth_client.put(
        _url(match), json={"home_score": 1, "away_score": 0}, headers=_auth(regular_user)
    )
    assert response.status_code == 403


async def test_unauthenticated_gets_401(auth_client: AsyncClient, match: Match):
    response = await auth_client.put(_url(match), json={"home_score": 1, "away_score": 0})
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Setting a result
# ---------------------------------------------------------------------------


async def test_set_result_updates_match(
    auth_client: AsyncClient, admin_user: User, match: Match, db: AsyncSession
):
    response = await auth_client.put(
        _url(match), json={"home_score": 3, "away_score": 1}, headers=_auth(admin_user)
    )
    assert response.status_code == 200
    data = response.json()
    assert data["home_score"] == 3
    assert data["away_score"] == 1
    assert data["status"] == "finished"

    await db.refresh(match)
    assert match.home_score == 3
    assert match.away_score == 1
    assert match.status == "finished"


async def test_set_result_unknown_match_returns_404(
    auth_client: AsyncClient, admin_user: User, tournament: Tournament
):
    response = await auth_client.put(
        "/admin/matches/00000000-0000-0000-0000-000000000000/result",
        json={"home_score": 1, "away_score": 0},
        headers=_auth(admin_user),
    )
    assert response.status_code == 404


async def test_set_result_rejects_negative_scores(
    auth_client: AsyncClient, admin_user: User, match: Match
):
    response = await auth_client.put(
        _url(match), json={"home_score": -1, "away_score": 0}, headers=_auth(admin_user)
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Prediction scoring
# ---------------------------------------------------------------------------


async def test_set_result_scores_predictions(
    auth_client: AsyncClient,
    admin_user: User,
    match: Match,
    prediction: Prediction,
    db: AsyncSession,
):
    # predicted 2-1, actual 2-1 → 2 (result) + 3 (exact) = 5
    response = await auth_client.put(
        _url(match), json={"home_score": 2, "away_score": 1}, headers=_auth(admin_user)
    )
    assert response.status_code == 200
    assert response.json()["predictions_scored"] == 1

    await db.refresh(prediction)
    assert prediction.points_result == 2
    assert prediction.points_exact == 3
    assert prediction.total_points == 5
    assert prediction.scored_at is not None


async def test_correcting_result_rescores_predictions(
    auth_client: AsyncClient,
    admin_user: User,
    match: Match,
    prediction: Prediction,
    db: AsyncSession,
):
    # First entry: wrong score 0-1 → predicted 2-1 earns 0 points.
    response = await auth_client.put(
        _url(match), json={"home_score": 0, "away_score": 1}, headers=_auth(admin_user)
    )
    assert response.status_code == 200
    await db.refresh(prediction)
    assert prediction.total_points == 0
    assert prediction.scored_at is not None

    # Correction: 2-1 → must re-score the already-scored prediction to 5.
    response = await auth_client.put(
        _url(match), json={"home_score": 2, "away_score": 1}, headers=_auth(admin_user)
    )
    assert response.status_code == 200
    await db.refresh(prediction)
    assert prediction.points_result == 2
    assert prediction.points_exact == 3
    assert prediction.total_points == 5


# ---------------------------------------------------------------------------
# Leaderboard recompute
# ---------------------------------------------------------------------------


async def test_set_result_recomputes_party_leaderboard(
    auth_client: AsyncClient,
    admin_user: User,
    regular_user: User,
    match: Match,
    prediction: Prediction,
    party: Party,
    db: AsyncSession,
):
    response = await auth_client.put(
        _url(match), json={"home_score": 2, "away_score": 1}, headers=_auth(admin_user)
    )
    assert response.status_code == 200
    assert response.json()["leaderboards_recomputed"] == 1

    snapshot = (
        await db.execute(
            select(LeaderboardSnapshot).where(
                LeaderboardSnapshot.party_id == party.id,
                LeaderboardSnapshot.user_id == regular_user.id,
            )
        )
    ).scalar_one()
    assert snapshot.total_points == 5
    assert snapshot.exact_scores == 1
    assert snapshot.rank == 1
