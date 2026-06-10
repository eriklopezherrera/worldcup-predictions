import re

import structlog
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.match import Match
from app.models.tournament import Team, Tournament, TournamentTeam
from app.workers.football_api_client import FootballApiClient, STATUS_MAP

log = structlog.get_logger()

_STAGE_MAP: dict[str, str] = {
    "group stage": "group_stage",
    "round of 16": "round_of_16",
    "quarter-finals": "quarter_final",
    "quarter-final": "quarter_final",
    "semi-finals": "semi_final",
    "semi-final": "semi_final",
    "3rd place final": "third_place",
    "3rd place playoff": "third_place",
    "third place": "third_place",
    "final": "final",
}

_GROUP_STAGE_RE = re.compile(r"group stage\s*-\s*(\d+)", re.IGNORECASE)


def _map_stage(round_name: str) -> tuple[str, int | None]:
    """Map an api-football round string to (stage, match_day)."""
    lower = round_name.lower().strip()
    m = _GROUP_STAGE_RE.match(lower)
    if m:
        return "group_stage", int(m.group(1))
    stage = _STAGE_MAP.get(lower)
    if stage:
        return stage, None
    log.warning("fixture_sync.unknown_round", round=round_name)
    return "group_stage", None


async def sync_fixtures(
    db: AsyncSession,
    api_client: FootballApiClient,
    league_id: int,
    season: int,
) -> dict:
    log.info("fixture_sync.start", league_id=league_id, season=season)

    # 1. Find the tournament.
    result = await db.execute(
        select(Tournament).where(
            Tournament.external_id == league_id,
            Tournament.season == str(season),
        )
    )
    tournament = result.scalar_one_or_none()
    if not tournament:
        log.warning(
            "fixture_sync.tournament_not_found",
            league_id=league_id,
            season=season,
        )
        return {"error": f"No tournament found for league_id={league_id} season={season}"}

    # 2. Upsert teams.
    teams_data = await api_client.get_teams(league_id, season)
    for item in teams_data:
        team = item["team"]
        stmt = (
            pg_insert(Team)
            .values(
                external_id=team["id"],
                name=team["name"],
                short_name=team.get("code") or None,
                logo_url=team.get("logo") or None,
            )
            .on_conflict_do_update(
                index_elements=["external_id"],
                set_={
                    "name": team["name"],
                    "short_name": team.get("code") or None,
                    "logo_url": team.get("logo") or None,
                },
            )
        )
        await db.execute(stmt)
    await db.commit()

    # 3. Build external_id → db UUID map for all upserted teams.
    team_ext_ids = [item["team"]["id"] for item in teams_data]
    team_rows = (
        await db.execute(
            select(Team.external_id, Team.id).where(Team.external_id.in_(team_ext_ids))
        )
    ).all()
    team_ext_to_db_id: dict[int, object] = {ext: db_id for ext, db_id in team_rows}
    log.info("fixture_sync.teams_upserted", count=len(team_ext_to_db_id))

    # 4. Upsert matches.
    fixtures_data = await api_client.get_fixtures(league_id, season)
    for fixture in fixtures_data:
        fix = fixture["fixture"]
        teams = fixture["teams"]
        score = fixture.get("score", {})
        league_info = fixture.get("league", {})

        ext_id: int = fix["id"]
        status_short: str = fix["status"]["short"]
        our_status = STATUS_MAP.get(status_short, "scheduled")
        stage, match_day = _map_stage(league_info.get("round", ""))

        home_ext_id: int = teams["home"]["id"]
        away_ext_id: int = teams["away"]["id"]
        home_db_id = team_ext_to_db_id.get(home_ext_id)
        away_db_id = team_ext_to_db_id.get(away_ext_id)

        ft = score.get("fulltime") or {}
        ht = score.get("halftime") or {}

        from datetime import datetime, timezone

        kickoff_str: str | None = fix.get("date")
        kickoff = datetime.fromisoformat(kickoff_str) if kickoff_str else None
        if kickoff and kickoff.tzinfo is None:
            kickoff = kickoff.replace(tzinfo=timezone.utc)

        venue_name: str | None = (fix.get("venue") or {}).get("name")

        values = dict(
            external_id=ext_id,
            tournament_id=tournament.id,
            home_team_id=home_db_id,
            away_team_id=away_db_id,
            kickoff_utc=kickoff,
            venue=venue_name,
            stage=stage,
            group_name=None,
            match_day=match_day,
            home_score=ft.get("home"),
            away_score=ft.get("away"),
            home_score_ht=ht.get("home"),
            away_score_ht=ht.get("away"),
            status=our_status,
        )
        stmt = (
            pg_insert(Match)
            .values(**values)
            .on_conflict_do_update(
                index_elements=["external_id"],
                set_={
                    k: values[k]
                    for k in (
                        "home_team_id",
                        "away_team_id",
                        "kickoff_utc",
                        "venue",
                        "stage",
                        "match_day",
                        "home_score",
                        "away_score",
                        "home_score_ht",
                        "away_score_ht",
                        "status",
                    )
                },
            )
        )
        await db.execute(stmt)
    await db.commit()

    # 5. Upsert tournament_teams for every team we synced.
    for db_id in team_ext_to_db_id.values():
        stmt = (
            pg_insert(TournamentTeam)
            .values(tournament_id=tournament.id, team_id=db_id)
            .on_conflict_do_nothing()
        )
        await db.execute(stmt)
    await db.commit()

    log.info(
        "fixture_sync.done",
        league_id=league_id,
        season=season,
        fixtures=len(fixtures_data),
        teams=len(team_ext_to_db_id),
    )
    return {"fixtures": len(fixtures_data), "teams": len(team_ext_to_db_id)}
