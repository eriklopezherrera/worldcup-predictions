"""
Tests for the predictions endpoints and scoring logic.

Run with: cd backend && pytest tests/test_predictions.py
Requires MOCK_AUTH=true (set via the mock_auth fixture).
"""
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.dependencies import get_db, get_redis
from app.main import app
from app.models.match import Match
from app.models.prediction import Prediction
from app.models.tournament import Team, Tournament
from app.models.user import User
from app.services.scoring_service import compute_points, compute_points_knockout


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_auth(monkeypatch):
    monkeypatch.setattr(settings, "mock_auth", True)


@pytest.fixture
async def test_user(db: AsyncSession) -> User:
    user = User(
        cognito_sub="pred-test-sub",
        username="preduser",
        email="pred@example.com",
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
async def future_match(db: AsyncSession, tournament: Tournament) -> Match:
    home = Team(name="Test Home", short_name="THM")
    away = Team(name="Test Away", short_name="TAW")
    db.add_all([home, away])
    await db.flush()
    m = Match(
        tournament_id=tournament.id,
        home_team_id=home.id,
        away_team_id=away.id,
        kickoff_utc=datetime.now(timezone.utc) + timedelta(hours=2),
        stage="group_stage",
        status="scheduled",
        predictions_open=True,
    )
    db.add(m)
    await db.commit()
    await db.refresh(m)
    return m


@pytest.fixture
async def ko_future_match(db: AsyncSession, tournament: Tournament) -> Match:
    home = Team(name="KO Home", short_name="KOH")
    away = Team(name="KO Away", short_name="KOA")
    db.add_all([home, away])
    await db.flush()
    m = Match(
        tournament_id=tournament.id,
        home_team_id=home.id,
        away_team_id=away.id,
        kickoff_utc=datetime.now(timezone.utc) + timedelta(hours=2),
        stage="round_of_32",
        status="scheduled",
        predictions_open=True,
    )
    db.add(m)
    await db.commit()
    await db.refresh(m)
    return m


@pytest.fixture
async def started_match(db: AsyncSession, tournament: Tournament) -> Match:
    m = Match(
        tournament_id=tournament.id,
        kickoff_utc=datetime.now(timezone.utc) - timedelta(minutes=30),
        stage="group_stage",
        status="live",
    )
    db.add(m)
    await db.commit()
    await db.refresh(m)
    return m


@pytest.fixture
async def finished_match(db: AsyncSession, tournament: Tournament) -> Match:
    m = Match(
        tournament_id=tournament.id,
        kickoff_utc=datetime.now(timezone.utc) - timedelta(hours=3),
        stage="group_stage",
        status="finished",
        home_score=2,
        away_score=1,
    )
    db.add(m)
    await db.commit()
    await db.refresh(m)
    return m


def _auth(user: User) -> dict:
    return {"X-Dev-User-Id": str(user.id)}


# ---------------------------------------------------------------------------
# Unit tests: compute_points
# ---------------------------------------------------------------------------


def test_compute_points_exact_score():
    points_result, points_exact = compute_points(2, 1, 2, 1)
    assert points_result == 2
    assert points_exact == 3


def test_compute_points_correct_direction_home_win():
    # Predicted 3-0, actual 2-1 — both home wins
    points_result, points_exact = compute_points(3, 0, 2, 1)
    assert points_result == 2
    assert points_exact == 0


def test_compute_points_correct_direction_draw():
    # Predicted 1-1, actual 0-0 — both draws
    points_result, points_exact = compute_points(1, 1, 0, 0)
    assert points_result == 2
    assert points_exact == 0


def test_compute_points_correct_direction_away_win():
    # Predicted 0-2, actual 1-3 — both away wins
    points_result, points_exact = compute_points(0, 2, 1, 3)
    assert points_result == 2
    assert points_exact == 0


def test_compute_points_wrong_direction():
    # Predicted home win, actual away win
    points_result, points_exact = compute_points(2, 0, 0, 1)
    assert points_result == 0
    assert points_exact == 0


def test_compute_points_wrong_predicted_draw():
    # Predicted draw, actual home win
    points_result, points_exact = compute_points(1, 1, 2, 0)
    assert points_result == 0
    assert points_exact == 0


def test_compute_points_exact_gives_max_5():
    points_result, points_exact = compute_points(1, 0, 1, 0)
    assert points_result + points_exact == 5


# ---------------------------------------------------------------------------
# Unit tests: compute_points_knockout (1 outcome / 2 exact / 2 advancing)
# ---------------------------------------------------------------------------

_TEAM_A = uuid.uuid4()
_TEAM_B = uuid.uuid4()


def test_knockout_exact_decisive_gives_max_5():
    # Predicted A 2-1 (advancing A), actual 2-1, A advanced.
    result, exact, advancing = compute_points_knockout(2, 1, _TEAM_A, 2, 1, _TEAM_A)
    assert (result, exact, advancing) == (1, 2, 2)
    assert result + exact + advancing == 5


def test_knockout_right_team_wrong_score():
    # Predicted A 2-1 (advancing A), actual A 2-0 → outcome + advancing, no exact.
    result, exact, advancing = compute_points_knockout(2, 1, _TEAM_A, 2, 0, _TEAM_A)
    assert (result, exact, advancing) == (1, 0, 2)


def test_knockout_decisive_pick_but_team_lost_on_penalties():
    # Predicted A 2-1 (advancing A), actual draw 1-1, B advanced on penalties.
    result, exact, advancing = compute_points_knockout(2, 1, _TEAM_A, 1, 1, _TEAM_B)
    assert (result, exact, advancing) == (0, 0, 0)


def test_knockout_predicted_draw_correct_advancing_gives_max_5():
    # Predicted 1-1 (advancing A), actual 1-1, A advanced on penalties.
    result, exact, advancing = compute_points_knockout(1, 1, _TEAM_A, 1, 1, _TEAM_A)
    assert (result, exact, advancing) == (1, 2, 2)
    assert result + exact + advancing == 5


def test_knockout_predicted_draw_wrong_advancing():
    # Predicted 1-1 (advancing A), actual 1-1, B advanced → draw + score, no advancing.
    result, exact, advancing = compute_points_knockout(1, 1, _TEAM_A, 1, 1, _TEAM_B)
    assert (result, exact, advancing) == (1, 2, 0)


def test_knockout_predicted_draw_but_decisive_result_keeps_advancing():
    # Predicted 1-1 (advancing A), actual A 2-0 → no draw/score, but A advanced.
    result, exact, advancing = compute_points_knockout(1, 1, _TEAM_A, 2, 0, _TEAM_A)
    assert (result, exact, advancing) == (0, 0, 2)


# ---------------------------------------------------------------------------
# PUT /predictions/{match_id}
# ---------------------------------------------------------------------------


async def test_create_prediction_succeeds_before_kickoff(
    auth_client: AsyncClient,
    test_user: User,
    future_match: Match,
):
    response = await auth_client.put(
        f"/predictions/{future_match.id}",
        json={"predicted_home_score": 2, "predicted_away_score": 1},
        headers=_auth(test_user),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["predicted_home_score"] == 2
    assert data["predicted_away_score"] == 1
    assert data["match_id"] == str(future_match.id)
    assert data["is_locked"] is False
    assert data["points_result"] == 0
    assert data["points_exact"] == 0
    assert data["total_points"] == 0
    assert "id" in data


async def test_update_prediction_succeeds_before_kickoff(
    auth_client: AsyncClient,
    test_user: User,
    future_match: Match,
):
    await auth_client.put(
        f"/predictions/{future_match.id}",
        json={"predicted_home_score": 1, "predicted_away_score": 0},
        headers=_auth(test_user),
    )
    response = await auth_client.put(
        f"/predictions/{future_match.id}",
        json={"predicted_home_score": 3, "predicted_away_score": 2},
        headers=_auth(test_user),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["predicted_home_score"] == 3
    assert data["predicted_away_score"] == 2


async def test_prediction_on_closed_stage_returns_409(
    auth_client: AsyncClient,
    test_user: User,
    db: AsyncSession,
    tournament: Tournament,
):
    home = Team(name="Closed Home", short_name="CLH")
    away = Team(name="Closed Away", short_name="CLA")
    db.add_all([home, away])
    await db.flush()
    m = Match(
        tournament_id=tournament.id,
        home_team_id=home.id,
        away_team_id=away.id,
        kickoff_utc=datetime.now(timezone.utc) + timedelta(hours=2),
        stage="round_of_32",
        status="scheduled",
        predictions_open=False,
    )
    db.add(m)
    await db.commit()
    await db.refresh(m)

    response = await auth_client.put(
        f"/predictions/{m.id}",
        json={"predicted_home_score": 1, "predicted_away_score": 0},
        headers=_auth(test_user),
    )
    assert response.status_code == 409


async def test_prediction_on_tbd_match_returns_409(
    auth_client: AsyncClient,
    test_user: User,
    db: AsyncSession,
    tournament: Tournament,
):
    # Stage opened but teams not decided yet — still not predictable.
    m = Match(
        tournament_id=tournament.id,
        kickoff_utc=datetime.now(timezone.utc) + timedelta(hours=2),
        stage="round_of_32",
        status="scheduled",
        predictions_open=True,
    )
    db.add(m)
    await db.commit()
    await db.refresh(m)

    response = await auth_client.put(
        f"/predictions/{m.id}",
        json={"predicted_home_score": 1, "predicted_away_score": 0},
        headers=_auth(test_user),
    )
    assert response.status_code == 409


async def test_prediction_locked_returns_423(
    auth_client: AsyncClient,
    test_user: User,
    started_match: Match,
):
    response = await auth_client.put(
        f"/predictions/{started_match.id}",
        json={"predicted_home_score": 1, "predicted_away_score": 1},
        headers=_auth(test_user),
    )
    assert response.status_code == 423


async def test_prediction_on_finished_match_returns_423(
    auth_client: AsyncClient,
    test_user: User,
    finished_match: Match,
):
    response = await auth_client.put(
        f"/predictions/{finished_match.id}",
        json={"predicted_home_score": 2, "predicted_away_score": 1},
        headers=_auth(test_user),
    )
    assert response.status_code == 423


async def test_prediction_on_nonexistent_match_returns_404(
    auth_client: AsyncClient,
    test_user: User,
):
    response = await auth_client.put(
        f"/predictions/{uuid.uuid4()}",
        json={"predicted_home_score": 1, "predicted_away_score": 0},
        headers=_auth(test_user),
    )
    assert response.status_code == 404


async def test_prediction_score_out_of_range_returns_422(
    auth_client: AsyncClient,
    test_user: User,
    future_match: Match,
):
    response = await auth_client.put(
        f"/predictions/{future_match.id}",
        json={"predicted_home_score": -1, "predicted_away_score": 0},
        headers=_auth(test_user),
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Knockout advancing pick on PUT /predictions/{match_id}
# ---------------------------------------------------------------------------


async def test_knockout_decisive_infers_advancing_team(
    auth_client: AsyncClient,
    test_user: User,
    ko_future_match: Match,
):
    # Decisive pick — no advancing_team_id sent; it's inferred as the home side.
    response = await auth_client.put(
        f"/predictions/{ko_future_match.id}",
        json={"predicted_home_score": 2, "predicted_away_score": 1},
        headers=_auth(test_user),
    )
    assert response.status_code == 200
    assert response.json()["predicted_advancing_team_id"] == str(
        ko_future_match.home_team_id
    )


async def test_knockout_draw_requires_advancing_team(
    auth_client: AsyncClient,
    test_user: User,
    ko_future_match: Match,
):
    response = await auth_client.put(
        f"/predictions/{ko_future_match.id}",
        json={"predicted_home_score": 1, "predicted_away_score": 1},
        headers=_auth(test_user),
    )
    assert response.status_code == 422


async def test_knockout_draw_with_advancing_team_succeeds(
    auth_client: AsyncClient,
    test_user: User,
    ko_future_match: Match,
):
    response = await auth_client.put(
        f"/predictions/{ko_future_match.id}",
        json={
            "predicted_home_score": 1,
            "predicted_away_score": 1,
            "advancing_team_id": str(ko_future_match.away_team_id),
        },
        headers=_auth(test_user),
    )
    assert response.status_code == 200
    assert response.json()["predicted_advancing_team_id"] == str(
        ko_future_match.away_team_id
    )


async def test_knockout_draw_advancing_team_must_be_in_match(
    auth_client: AsyncClient,
    test_user: User,
    ko_future_match: Match,
):
    response = await auth_client.put(
        f"/predictions/{ko_future_match.id}",
        json={
            "predicted_home_score": 0,
            "predicted_away_score": 0,
            "advancing_team_id": str(uuid.uuid4()),
        },
        headers=_auth(test_user),
    )
    assert response.status_code == 422


async def test_group_stage_ignores_advancing_team(
    auth_client: AsyncClient,
    test_user: User,
    future_match: Match,
):
    # Group stage draw needs no advancing pick and stores none.
    response = await auth_client.put(
        f"/predictions/{future_match.id}",
        json={"predicted_home_score": 1, "predicted_away_score": 1},
        headers=_auth(test_user),
    )
    assert response.status_code == 200
    assert response.json()["predicted_advancing_team_id"] is None


# ---------------------------------------------------------------------------
# GET /predictions
# ---------------------------------------------------------------------------


async def test_predictions_list_empty_when_none_made(
    auth_client: AsyncClient,
    test_user: User,
):
    response = await auth_client.get("/predictions", headers=_auth(test_user))
    assert response.status_code == 200
    assert response.json() == []


async def test_predictions_visible_for_past_matches(
    auth_client: AsyncClient,
    test_user: User,
    db: AsyncSession,
    finished_match: Match,
):
    # Bypass the API lock to simulate a prediction made before kickoff
    pred = Prediction(
        user_id=test_user.id,
        match_id=finished_match.id,
        predicted_home_score=2,
        predicted_away_score=1,
        points_result=2,
        points_exact=3,
    )
    db.add(pred)
    await db.commit()

    response = await auth_client.get("/predictions", headers=_auth(test_user))
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["match_id"] == str(finished_match.id)
    assert data[0]["is_locked"] is True
    assert data[0]["predicted_home_score"] == 2
    assert data[0]["predicted_away_score"] == 1


async def test_predictions_filter_by_tournament(
    auth_client: AsyncClient,
    test_user: User,
    db: AsyncSession,
    tournament: Tournament,
    future_match: Match,
):
    await auth_client.put(
        f"/predictions/{future_match.id}",
        json={"predicted_home_score": 1, "predicted_away_score": 0},
        headers=_auth(test_user),
    )

    response = await auth_client.get(
        "/predictions",
        params={"tournament_id": str(tournament.id)},
        headers=_auth(test_user),
    )
    assert response.status_code == 200
    assert len(response.json()) == 1

    response = await auth_client.get(
        "/predictions",
        params={"tournament_id": str(uuid.uuid4())},
        headers=_auth(test_user),
    )
    assert response.status_code == 200
    assert len(response.json()) == 0


async def test_predictions_filter_by_status(
    auth_client: AsyncClient,
    test_user: User,
    db: AsyncSession,
    future_match: Match,
    finished_match: Match,
):
    # Prediction on future (scheduled) match via API
    await auth_client.put(
        f"/predictions/{future_match.id}",
        json={"predicted_home_score": 1, "predicted_away_score": 0},
        headers=_auth(test_user),
    )
    # Prediction on finished match directly in DB
    pred = Prediction(
        user_id=test_user.id,
        match_id=finished_match.id,
        predicted_home_score=2,
        predicted_away_score=1,
    )
    db.add(pred)
    await db.commit()

    response = await auth_client.get(
        "/predictions",
        params={"status": "scheduled"},
        headers=_auth(test_user),
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["match_id"] == str(future_match.id)


# ---------------------------------------------------------------------------
# GET /predictions/summary
# ---------------------------------------------------------------------------


async def test_summary_empty_when_no_predictions(
    auth_client: AsyncClient,
    test_user: User,
):
    response = await auth_client.get("/predictions/summary", headers=_auth(test_user))
    assert response.status_code == 200
    data = response.json()
    assert data["total_points"] == 0
    assert data["exact_scores"] == 0
    assert data["predictions_made"] == 0


async def test_summary_returns_correct_totals(
    auth_client: AsyncClient,
    test_user: User,
    db: AsyncSession,
    tournament: Tournament,
    finished_match: Match,
):
    # Exact score prediction: points_result=2, points_exact=3 → total=5
    pred = Prediction(
        user_id=test_user.id,
        match_id=finished_match.id,
        predicted_home_score=2,
        predicted_away_score=1,
        points_result=2,
        points_exact=3,
    )
    db.add(pred)
    await db.commit()

    response = await auth_client.get(
        "/predictions/summary",
        params={"tournament_id": str(tournament.id)},
        headers=_auth(test_user),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total_points"] == 5
    assert data["exact_scores"] == 1
    assert data["predictions_made"] == 1


async def test_summary_multiple_predictions(
    auth_client: AsyncClient,
    test_user: User,
    db: AsyncSession,
    tournament: Tournament,
):
    now = datetime.now(timezone.utc)

    match1 = Match(
        tournament_id=tournament.id,
        kickoff_utc=now - timedelta(hours=5),
        stage="group_stage",
        status="finished",
        home_score=1,
        away_score=1,
    )
    match2 = Match(
        tournament_id=tournament.id,
        kickoff_utc=now - timedelta(hours=3),
        stage="group_stage",
        status="finished",
        home_score=3,
        away_score=0,
    )
    db.add_all([match1, match2])
    await db.commit()
    await db.refresh(match1)
    await db.refresh(match2)

    # Exact score on match1: 2 + 3 = 5 pts
    pred1 = Prediction(
        user_id=test_user.id,
        match_id=match1.id,
        predicted_home_score=1,
        predicted_away_score=1,
        points_result=2,
        points_exact=3,
    )
    # Correct direction on match2: 2 pts, no exact
    pred2 = Prediction(
        user_id=test_user.id,
        match_id=match2.id,
        predicted_home_score=2,
        predicted_away_score=0,
        points_result=2,
        points_exact=0,
    )
    db.add_all([pred1, pred2])
    await db.commit()

    response = await auth_client.get(
        "/predictions/summary",
        params={"tournament_id": str(tournament.id)},
        headers=_auth(test_user),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total_points"] == 7
    assert data["exact_scores"] == 1
    assert data["predictions_made"] == 2


async def test_summary_wrong_prediction_zero_points(
    auth_client: AsyncClient,
    test_user: User,
    db: AsyncSession,
    tournament: Tournament,
    finished_match: Match,
):
    pred = Prediction(
        user_id=test_user.id,
        match_id=finished_match.id,
        predicted_home_score=0,
        predicted_away_score=3,
        points_result=0,
        points_exact=0,
    )
    db.add(pred)
    await db.commit()

    response = await auth_client.get(
        "/predictions/summary",
        params={"tournament_id": str(tournament.id)},
        headers=_auth(test_user),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total_points"] == 0
    assert data["exact_scores"] == 0
    assert data["predictions_made"] == 1
