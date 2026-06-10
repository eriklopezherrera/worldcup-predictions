"""
Tests for GET /tournaments/{tournament_id} — tournament detail with teams.

GET /tournaments (list) and GET /tournaments/{id}/matches are covered in
tests/test_matches.py. These tests focus on the detail endpoint that returns
the tournament together with its team roster.
"""
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tournament import Team, Tournament, TournamentTeam
from app.models.user import User


def _auth(u: User) -> dict:
    return {"X-Dev-User-Id": str(u.id)}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def three_teams(db: AsyncSession, tournament: Tournament) -> list[Team]:
    """Adds Brazil (Group A), Argentina (Group A), Germany (Group B)."""
    teams = [
        Team(name="Brazil", short_name="BRA"),
        Team(name="Argentina", short_name="ARG"),
        Team(name="Germany", short_name="GER"),
    ]
    for t in teams:
        db.add(t)
    await db.flush()

    db.add(TournamentTeam(tournament_id=tournament.id, team_id=teams[0].id, group_name="A"))
    db.add(TournamentTeam(tournament_id=tournament.id, team_id=teams[1].id, group_name="A"))
    db.add(TournamentTeam(tournament_id=tournament.id, team_id=teams[2].id, group_name="B"))
    await db.commit()
    for t in teams:
        await db.refresh(t)
    return teams


# ---------------------------------------------------------------------------
# Response shape
# ---------------------------------------------------------------------------


async def test_tournament_detail_returns_core_fields(
    auth_client: AsyncClient, user: User, tournament: Tournament
):
    response = await auth_client.get(f"/tournaments/{tournament.id}", headers=_auth(user))
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(tournament.id)
    assert data["name"] == "FIFA World Cup 2026"
    assert data["season"] == "2026"
    assert data["status"] == "active"
    assert data["country"] == "USA/Canada/Mexico"
    assert "logo_url" in data
    assert "teams" in data


async def test_tournament_detail_no_teams_returns_empty_list(
    auth_client: AsyncClient, user: User, tournament: Tournament
):
    response = await auth_client.get(f"/tournaments/{tournament.id}", headers=_auth(user))
    assert response.status_code == 200
    assert response.json()["teams"] == []


# ---------------------------------------------------------------------------
# Teams
# ---------------------------------------------------------------------------


async def test_tournament_detail_includes_all_teams(
    auth_client: AsyncClient,
    user: User,
    tournament: Tournament,
    three_teams: list[Team],
):
    response = await auth_client.get(f"/tournaments/{tournament.id}", headers=_auth(user))
    assert response.status_code == 200
    teams = response.json()["teams"]
    assert len(teams) == 3
    names = {t["name"] for t in teams}
    assert names == {"Brazil", "Argentina", "Germany"}


async def test_tournament_detail_team_has_required_fields(
    auth_client: AsyncClient,
    user: User,
    tournament: Tournament,
    three_teams: list[Team],
):
    response = await auth_client.get(f"/tournaments/{tournament.id}", headers=_auth(user))
    assert response.status_code == 200
    for team in response.json()["teams"]:
        assert "id" in team
        assert "name" in team
        assert "short_name" in team
        assert "logo_url" in team
        assert "group_name" in team


async def test_tournament_detail_teams_sorted_by_group_then_name(
    auth_client: AsyncClient,
    user: User,
    tournament: Tournament,
    three_teams: list[Team],
):
    response = await auth_client.get(f"/tournaments/{tournament.id}", headers=_auth(user))
    assert response.status_code == 200
    teams = response.json()["teams"]
    group_names = [t["group_name"] for t in teams]
    # All Group A entries must appear before Group B
    last_a = max((i for i, g in enumerate(group_names) if g == "A"), default=-1)
    first_b = min((i for i, g in enumerate(group_names) if g == "B"), default=999)
    assert last_a < first_b


async def test_tournament_detail_team_group_name_matches_registration(
    auth_client: AsyncClient,
    user: User,
    tournament: Tournament,
    three_teams: list[Team],
):
    response = await auth_client.get(f"/tournaments/{tournament.id}", headers=_auth(user))
    assert response.status_code == 200
    team_groups = {t["name"]: t["group_name"] for t in response.json()["teams"]}
    assert team_groups["Brazil"] == "A"
    assert team_groups["Argentina"] == "A"
    assert team_groups["Germany"] == "B"


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------


async def test_tournament_detail_unknown_id_returns_404(
    auth_client: AsyncClient, user: User
):
    response = await auth_client.get(f"/tournaments/{uuid.uuid4()}", headers=_auth(user))
    assert response.status_code == 404


async def test_tournament_detail_requires_auth(
    auth_client: AsyncClient, tournament: Tournament
):
    response = await auth_client.get(f"/tournaments/{tournament.id}")
    assert response.status_code == 401
