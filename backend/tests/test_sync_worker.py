"""
Tests for the sync worker modules.

API calls are mocked at the FootballApiClient method level so no real HTTP
requests are made. All DB operations run against the test PostgreSQL database.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

import app.models  # noqa: F401 — register all ORM models
from app.models.leaderboard import LeaderboardSnapshot
from app.models.match import Match
from app.models.party import Party, PartyMember
from app.models.prediction import Prediction
from app.models.tournament import Team, Tournament, TournamentTeam
from app.models.user import User
from app.workers.fixture_sync import _map_stage, sync_fixtures
from app.workers.football_api_client import FootballApiClient, STATUS_MAP
from app.workers.score_sync import sync_scores


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def tournament(db):
    t = Tournament(
        name="FIFA World Cup 2026",
        season="2026",
        external_id=1,
        status="active",
    )
    db.add(t)
    await db.commit()
    await db.refresh(t)
    return t


@pytest.fixture
async def two_teams(db):
    home = Team(external_id=10, name="Brazil", short_name="BRA")
    away = Team(external_id=11, name="Mexico", short_name="MEX")
    db.add_all([home, away])
    await db.commit()
    await db.refresh(home)
    await db.refresh(away)
    return home, away


@pytest.fixture
def sample_teams_api():
    return [
        {"team": {"id": 10, "name": "Brazil", "code": "BRA", "logo": "https://bra.png"}},
        {"team": {"id": 11, "name": "Mexico", "code": "MEX", "logo": "https://mex.png"}},
    ]


@pytest.fixture
def sample_fixtures_api():
    return [
        {
            "fixture": {
                "id": 1001,
                "date": "2026-06-11T18:00:00+00:00",
                "venue": {"name": "MetLife Stadium"},
                "status": {"short": "NS"},
            },
            "league": {"round": "Group Stage - 1"},
            "teams": {
                "home": {"id": 10, "name": "Brazil"},
                "away": {"id": 11, "name": "Mexico"},
            },
            "score": {
                "fulltime": {"home": None, "away": None},
                "halftime": {"home": None, "away": None},
            },
        }
    ]


def _mock_api(teams=None, fixtures=None, live=None) -> AsyncMock:
    client = AsyncMock(spec=FootballApiClient)
    client.get_teams.return_value = teams or []
    client.get_fixtures.return_value = fixtures or []
    client.get_live_fixtures.return_value = live or []
    return client


# ---------------------------------------------------------------------------
# STATUS_MAP coverage
# ---------------------------------------------------------------------------


class TestStatusMap:
    ALL_KNOWN = ["NS", "1H", "HT", "2H", "ET", "BT", "P", "FT", "AET", "PEN", "PST", "CANC", "SUSP"]

    def test_all_statuses_present(self):
        for s in self.ALL_KNOWN:
            assert s in STATUS_MAP, f"Missing status: {s}"

    def test_scheduled(self):
        assert STATUS_MAP["NS"] == "scheduled"

    def test_live_statuses(self):
        for s in ["1H", "HT", "2H", "ET", "BT", "P"]:
            assert STATUS_MAP[s] == "live"

    def test_finished_statuses(self):
        for s in ["FT", "AET", "PEN"]:
            assert STATUS_MAP[s] == "finished"

    def test_postponed(self):
        assert STATUS_MAP["PST"] == "postponed"

    def test_cancelled_statuses(self):
        for s in ["CANC", "SUSP"]:
            assert STATUS_MAP[s] == "cancelled"


# ---------------------------------------------------------------------------
# Stage mapping
# ---------------------------------------------------------------------------


class TestMapStage:
    def test_group_stage_day_1(self):
        stage, day = _map_stage("Group Stage - 1")
        assert stage == "group_stage"
        assert day == 1

    def test_group_stage_day_3(self):
        stage, day = _map_stage("Group Stage - 3")
        assert stage == "group_stage"
        assert day == 3

    def test_round_of_16(self):
        stage, day = _map_stage("Round of 16")
        assert stage == "round_of_16"
        assert day is None

    def test_quarter_final(self):
        stage, _ = _map_stage("Quarter-finals")
        assert stage == "quarter_final"

    def test_semi_final(self):
        stage, _ = _map_stage("Semi-finals")
        assert stage == "semi_final"

    def test_third_place_final(self):
        stage, _ = _map_stage("3rd Place Final")
        assert stage == "third_place"

    def test_final(self):
        stage, _ = _map_stage("Final")
        assert stage == "final"

    def test_case_insensitive(self):
        stage, day = _map_stage("GROUP STAGE - 2")
        assert stage == "group_stage"
        assert day == 2


# ---------------------------------------------------------------------------
# sync_fixtures
# ---------------------------------------------------------------------------


class TestSyncFixtures:
    async def test_creates_teams_and_match(
        self, db, tournament, sample_teams_api, sample_fixtures_api
    ):
        client = _mock_api(teams=sample_teams_api, fixtures=sample_fixtures_api)
        result = await sync_fixtures(db, client, league_id=1, season=2026)

        assert result["teams"] == 2
        assert result["fixtures"] == 1

        teams = (await db.execute(select(Team))).scalars().all()
        assert {t.name for t in teams} == {"Brazil", "Mexico"}

        matches = (await db.execute(select(Match))).scalars().all()
        assert len(matches) == 1
        m = matches[0]
        assert m.external_id == 1001
        assert m.status == "scheduled"
        assert m.stage == "group_stage"
        assert m.match_day == 1

    async def test_team_ids_linked_to_match(
        self, db, tournament, sample_teams_api, sample_fixtures_api
    ):
        client = _mock_api(teams=sample_teams_api, fixtures=sample_fixtures_api)
        await sync_fixtures(db, client, league_id=1, season=2026)

        match = (await db.execute(select(Match))).scalar_one()
        brazil = (await db.execute(select(Team).where(Team.external_id == 10))).scalar_one()
        mexico = (await db.execute(select(Team).where(Team.external_id == 11))).scalar_one()

        assert match.home_team_id == brazil.id
        assert match.away_team_id == mexico.id

    async def test_idempotent_second_sync_does_not_duplicate(
        self, db, tournament, sample_teams_api, sample_fixtures_api
    ):
        client = _mock_api(teams=sample_teams_api, fixtures=sample_fixtures_api)
        await sync_fixtures(db, client, league_id=1, season=2026)
        await sync_fixtures(db, client, league_id=1, season=2026)

        teams = (await db.execute(select(Team))).scalars().all()
        matches = (await db.execute(select(Match))).scalars().all()
        assert len(teams) == 2
        assert len(matches) == 1

    async def test_upsert_updates_existing_team_name(
        self, db, tournament, sample_teams_api
    ):
        client = _mock_api(teams=sample_teams_api, fixtures=[])
        await sync_fixtures(db, client, league_id=1, season=2026)

        updated = [{"team": {"id": 10, "name": "Brasil", "code": "BRA", "logo": ""}}]
        client2 = _mock_api(teams=updated, fixtures=[])
        await sync_fixtures(db, client2, league_id=1, season=2026)

        team = (await db.execute(select(Team).where(Team.external_id == 10))).scalar_one()
        assert team.name == "Brasil"

    async def test_tournament_teams_upserted(
        self, db, tournament, sample_teams_api, sample_fixtures_api
    ):
        client = _mock_api(teams=sample_teams_api, fixtures=sample_fixtures_api)
        await sync_fixtures(db, client, league_id=1, season=2026)

        tt = (await db.execute(select(TournamentTeam))).scalars().all()
        assert len(tt) == 2

    async def test_missing_tournament_returns_error(self, db):
        client = _mock_api()
        result = await sync_fixtures(db, client, league_id=999, season=2099)
        assert "error" in result

    async def test_status_mapping_applied_to_match(self, db, tournament, sample_teams_api):
        fixture = {
            "fixture": {
                "id": 2001,
                "date": "2026-06-15T18:00:00+00:00",
                "venue": {"name": "Stadium"},
                "status": {"short": "FT"},
            },
            "league": {"round": "Group Stage - 2"},
            "teams": {"home": {"id": 10, "name": "Brazil"}, "away": {"id": 11, "name": "Mexico"}},
            "score": {
                "fulltime": {"home": 2, "away": 1},
                "halftime": {"home": 1, "away": 0},
            },
        }
        client = _mock_api(teams=sample_teams_api, fixtures=[fixture])
        await sync_fixtures(db, client, league_id=1, season=2026)

        match = (await db.execute(select(Match).where(Match.external_id == 2001))).scalar_one()
        assert match.status == "finished"
        assert match.home_score == 2
        assert match.away_score == 1
        assert match.home_score_ht == 1


# ---------------------------------------------------------------------------
# sync_scores
# ---------------------------------------------------------------------------


def _finished_fixture(ext_id: int, home: int, away: int) -> dict:
    return {
        "fixture": {
            "id": ext_id,
            "status": {"short": "FT"},
            "date": "2026-06-11T18:00:00+00:00",
            "venue": {"name": "Stadium"},
        },
        "league": {"round": "Group Stage - 1"},
        "teams": {"home": {"id": 10, "name": "Brazil"}, "away": {"id": 11, "name": "Mexico"}},
        "score": {
            "fulltime": {"home": home, "away": away},
            "halftime": {"home": 0, "away": 0},
        },
    }


async def _setup_match(db, tournament, two_teams, ext_id=1001, status="scheduled"):
    home_team, away_team = two_teams
    match = Match(
        tournament_id=tournament.id,
        home_team_id=home_team.id,
        away_team_id=away_team.id,
        kickoff_utc=datetime(2026, 6, 11, 18, 0, tzinfo=timezone.utc),
        stage="group_stage",
        status=status,
        external_id=ext_id,
    )
    db.add(match)
    await db.commit()
    await db.refresh(match)
    return match


async def _setup_user_and_prediction(db, match, sub="test_sub", username="testuser"):
    user = User(cognito_sub=sub, username=username, email=f"{sub}@example.com")
    db.add(user)
    await db.flush()
    pred = Prediction(
        user_id=user.id,
        match_id=match.id,
        predicted_home_score=2,
        predicted_away_score=1,
    )
    db.add(pred)
    await db.commit()
    await db.refresh(pred)
    return user, pred


class TestSyncScores:
    async def test_scores_exact_prediction(self, db, tournament, two_teams):
        match = await _setup_match(db, tournament, two_teams)
        user, pred = await _setup_user_and_prediction(db, match)

        client = _mock_api(fixtures=[_finished_fixture(1001, 2, 1)], live=[])
        result = await sync_scores(db, client, league_ids=[1], seasons=[2026])

        assert result["scored_matches"] == 1
        await db.refresh(pred)
        assert pred.points_result == 2   # correct direction
        assert pred.points_exact == 3    # exact scoreline
        assert pred.scored_at is not None

    async def test_scores_direction_only(self, db, tournament, two_teams):
        match = await _setup_match(db, tournament, two_teams)
        user, pred = await _setup_user_and_prediction(db, match)
        pred.predicted_home_score = 3
        pred.predicted_away_score = 1
        await db.commit()

        # Actual result 2-0 → same direction (home win) but not exact
        client = _mock_api(fixtures=[_finished_fixture(1001, 2, 0)], live=[])
        await sync_scores(db, client, league_ids=[1], seasons=[2026])

        await db.refresh(pred)
        assert pred.points_result == 2
        assert pred.points_exact == 0

    async def test_wrong_direction_scores_zero(self, db, tournament, two_teams):
        match = await _setup_match(db, tournament, two_teams)
        user, pred = await _setup_user_and_prediction(db, match)
        pred.predicted_home_score = 2
        pred.predicted_away_score = 1
        await db.commit()

        # Actual: away win 0-1
        client = _mock_api(fixtures=[_finished_fixture(1001, 0, 1)], live=[])
        await sync_scores(db, client, league_ids=[1], seasons=[2026])

        await db.refresh(pred)
        assert pred.points_result == 0
        assert pred.points_exact == 0

    async def test_does_not_rescore_already_scored_predictions(self, db, tournament, two_teams):
        match = await _setup_match(db, tournament, two_teams, status="finished")
        user, pred = await _setup_user_and_prediction(db, match)
        already_scored_at = datetime(2026, 6, 11, 20, 0, tzinfo=timezone.utc)
        pred.points_result = 2
        pred.points_exact = 3
        pred.scored_at = already_scored_at
        await db.commit()

        client = _mock_api(fixtures=[_finished_fixture(1001, 2, 1)], live=[])
        result = await sync_scores(db, client, league_ids=[1], seasons=[2026])

        assert result["scored_matches"] == 0
        await db.refresh(pred)
        assert pred.scored_at == already_scored_at  # unchanged

    async def test_live_match_updates_score_but_does_not_score_predictions(
        self, db, tournament, two_teams
    ):
        match = await _setup_match(db, tournament, two_teams)
        user, pred = await _setup_user_and_prediction(db, match)

        live_fixture = {
            "fixture": {
                "id": 1001,
                "status": {"short": "1H"},
                "date": "2026-06-11T18:00:00+00:00",
                "venue": {"name": "Stadium"},
            },
            "league": {"round": "Group Stage - 1"},
            "teams": {"home": {"id": 10}, "away": {"id": 11}},
            "score": {
                "fulltime": {"home": None, "away": None},
                "halftime": {"home": None, "away": None},
            },
        }
        client = _mock_api(fixtures=[], live=[live_fixture])
        result = await sync_scores(db, client, league_ids=[1], seasons=[2026])

        assert result["scored_matches"] == 0
        await db.refresh(match)
        assert match.status == "live"
        await db.refresh(pred)
        assert pred.scored_at is None   # not yet scored

    async def test_no_fixtures_returns_zero(self, db, tournament):
        client = _mock_api(fixtures=[], live=[])
        result = await sync_scores(db, client, league_ids=[1], seasons=[2026])
        assert result["scored_matches"] == 0

    async def test_triggers_leaderboard_recompute(self, db, tournament, two_teams):
        match = await _setup_match(db, tournament, two_teams)
        user, pred = await _setup_user_and_prediction(db, match)

        creator = User(cognito_sub="creator", username="creator", email="c@example.com")
        db.add(creator)
        await db.flush()

        party = Party(
            name="Test Party",
            invite_code="TST1234",
            created_by=creator.id,
            tournament_id=tournament.id,
        )
        db.add(party)
        await db.flush()
        db.add(PartyMember(party_id=party.id, user_id=user.id, role="member"))
        await db.commit()

        client = _mock_api(fixtures=[_finished_fixture(1001, 2, 1)], live=[])
        await sync_scores(db, client, league_ids=[1], seasons=[2026])

        snapshots = (await db.execute(select(LeaderboardSnapshot))).scalars().all()
        assert len(snapshots) == 1
        snap = snapshots[0]
        assert snap.party_id == party.id
        assert snap.total_points == 5       # 2 direction + 3 exact
        assert snap.exact_scores == 1
        assert snap.predictions_made == 1
        assert snap.rank == 1
