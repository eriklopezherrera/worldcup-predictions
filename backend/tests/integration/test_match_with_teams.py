"""
Tests for GET /matches/{match_id} focusing on:
  - team data embedded in the response
  - my_prediction field (present for the requesting user, absent for others)
  - placeholder matches with no teams assigned yet

Basic is_locked / actual_result / 404 cases are in tests/test_matches.py.
"""
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.match import Match
from app.models.tournament import Team, Tournament
from app.models.user import User


def _auth(u: User) -> dict:
    return {"X-Dev-User-Id": str(u.id)}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def home_team(db: AsyncSession) -> Team:
    t = Team(name="Brazil", short_name="BRA")
    db.add(t)
    await db.commit()
    await db.refresh(t)
    return t


@pytest.fixture
async def away_team(db: AsyncSession) -> Team:
    t = Team(name="Argentina", short_name="ARG")
    db.add(t)
    await db.commit()
    await db.refresh(t)
    return t


@pytest.fixture
async def match_with_teams(
    db: AsyncSession, tournament: Tournament, home_team: Team, away_team: Team
) -> Match:
    m = Match(
        tournament_id=tournament.id,
        home_team_id=home_team.id,
        away_team_id=away_team.id,
        kickoff_utc=datetime.now(timezone.utc) + timedelta(hours=2),
        stage="group_stage",
        group_name="A",
        status="scheduled",
    )
    db.add(m)
    await db.commit()
    await db.refresh(m)
    return m


# ---------------------------------------------------------------------------
# Team data
# ---------------------------------------------------------------------------


async def test_match_response_includes_home_team_name(
    auth_client: AsyncClient, user: User, match_with_teams: Match
):
    response = await auth_client.get(f"/matches/{match_with_teams.id}", headers=_auth(user))
    assert response.status_code == 200
    assert response.json()["home_team"]["name"] == "Brazil"
    assert response.json()["home_team"]["short_name"] == "BRA"


async def test_match_response_includes_away_team_name(
    auth_client: AsyncClient, user: User, match_with_teams: Match
):
    response = await auth_client.get(f"/matches/{match_with_teams.id}", headers=_auth(user))
    assert response.status_code == 200
    assert response.json()["away_team"]["name"] == "Argentina"
    assert response.json()["away_team"]["short_name"] == "ARG"


async def test_match_team_has_expected_fields(
    auth_client: AsyncClient, user: User, match_with_teams: Match
):
    response = await auth_client.get(f"/matches/{match_with_teams.id}", headers=_auth(user))
    assert response.status_code == 200
    for side in ("home_team", "away_team"):
        team = response.json()[side]
        assert "id" in team
        assert "name" in team
        assert "short_name" in team
        assert "logo_url" in team


async def test_placeholder_match_has_null_teams(
    auth_client: AsyncClient,
    user: User,
    db: AsyncSession,
    tournament: Tournament,
):
    """A final/semi-final placeholder has no teams assigned yet."""
    placeholder = Match(
        tournament_id=tournament.id,
        kickoff_utc=datetime.now(timezone.utc) + timedelta(days=30),
        stage="final",
        status="scheduled",
    )
    db.add(placeholder)
    await db.commit()
    await db.refresh(placeholder)

    response = await auth_client.get(f"/matches/{placeholder.id}", headers=_auth(user))
    assert response.status_code == 200
    data = response.json()
    assert data["home_team"] is None
    assert data["away_team"] is None


# ---------------------------------------------------------------------------
# my_prediction embedding
# ---------------------------------------------------------------------------


async def test_match_my_prediction_null_before_any_submission(
    auth_client: AsyncClient, user: User, match_with_teams: Match
):
    response = await auth_client.get(f"/matches/{match_with_teams.id}", headers=_auth(user))
    assert response.status_code == 200
    assert response.json()["my_prediction"] is None


async def test_match_my_prediction_present_after_submission(
    auth_client: AsyncClient, user: User, match_with_teams: Match
):
    await auth_client.put(
        f"/predictions/{match_with_teams.id}",
        json={"predicted_home_score": 3, "predicted_away_score": 1},
        headers=_auth(user),
    )

    response = await auth_client.get(f"/matches/{match_with_teams.id}", headers=_auth(user))
    assert response.status_code == 200
    pred = response.json()["my_prediction"]
    assert pred is not None
    assert pred["predicted_home_score"] == 3
    assert pred["predicted_away_score"] == 1


async def test_match_my_prediction_reflects_latest_update(
    auth_client: AsyncClient, user: User, match_with_teams: Match
):
    await auth_client.put(
        f"/predictions/{match_with_teams.id}",
        json={"predicted_home_score": 1, "predicted_away_score": 0},
        headers=_auth(user),
    )
    await auth_client.put(
        f"/predictions/{match_with_teams.id}",
        json={"predicted_home_score": 2, "predicted_away_score": 2},
        headers=_auth(user),
    )

    response = await auth_client.get(f"/matches/{match_with_teams.id}", headers=_auth(user))
    pred = response.json()["my_prediction"]
    assert pred["predicted_home_score"] == 2
    assert pred["predicted_away_score"] == 2


async def test_match_my_prediction_is_user_scoped(
    auth_client: AsyncClient, user: User, other_user: User, match_with_teams: Match
):
    """A prediction made by user must not appear in other_user's match view."""
    await auth_client.put(
        f"/predictions/{match_with_teams.id}",
        json={"predicted_home_score": 2, "predicted_away_score": 0},
        headers=_auth(user),
    )

    response = await auth_client.get(
        f"/matches/{match_with_teams.id}", headers=_auth(other_user)
    )
    assert response.status_code == 200
    assert response.json()["my_prediction"] is None


async def test_match_list_also_embeds_my_prediction(
    auth_client: AsyncClient, user: User, tournament: Tournament, match_with_teams: Match
):
    """my_prediction must be present in the tournament match list too, not only the single-match endpoint."""
    await auth_client.put(
        f"/predictions/{match_with_teams.id}",
        json={"predicted_home_score": 1, "predicted_away_score": 1},
        headers=_auth(user),
    )

    response = await auth_client.get(
        f"/tournaments/{tournament.id}/matches", headers=_auth(user)
    )
    assert response.status_code == 200
    matches = response.json()
    our_match = next(m for m in matches if m["id"] == str(match_with_teams.id))
    pred = our_match["my_prediction"]
    assert pred is not None
    assert pred["predicted_home_score"] == 1
    assert pred["predicted_away_score"] == 1
