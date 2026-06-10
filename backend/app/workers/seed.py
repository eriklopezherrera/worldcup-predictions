"""
Development-only seed script.
Populates the DB with a small set of World Cup 2026 fixture data so local
testing doesn't require a live api-football.com key.

Usage:
    cd backend
    python -m app.workers.seed
"""

import asyncio
import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.match import Match
from app.models.tournament import Team, Tournament, TournamentTeam
from app.models.user import User
from app.services.party_service import auto_join_global_parties

log = structlog.get_logger()

# Fixed dev user for MOCK_AUTH local testing. The UUID must match the
# frontend's VITE_DEV_USER_ID (sent as the X-Dev-User-Id header).
_DEV_USER = {
    "id": uuid.UUID("00000000-0000-0000-0000-000000000001"),
    "cognito_sub": "dev-mock-user",
    "username": "devuser",
    "email": "dev@example.com",
    "display_name": "Dev User",
}

# --------------------------------------------------------------------------- #
# Hard-coded seed data (representative subset of WC 2026)
# --------------------------------------------------------------------------- #

_TOURNAMENT = {
    "external_id": 1,
    "name": "FIFA World Cup 2026",
    "season": "2026",
    "country": "USA/Canada/Mexico",
    "status": "upcoming",
}

_TEAMS = [
    {"external_id": 1508, "name": "USA",       "short_name": "USA"},
    {"external_id": 6,    "name": "Mexico",    "short_name": "MEX"},
    {"external_id": 24,   "name": "Canada",    "short_name": "CAN"},
    {"external_id": 9,    "name": "Brazil",    "short_name": "BRA"},
    {"external_id": 26,   "name": "Argentina", "short_name": "ARG"},
    {"external_id": 2,    "name": "England",   "short_name": "ENG"},
    {"external_id": 27,   "name": "France",    "short_name": "FRA"},
    {"external_id": 8,    "name": "Germany",   "short_name": "GER"},
]

_FIXTURES = [
    # Group A — match day 1
    {
        "external_id": 900001,
        "home_ext": 1508,  # USA
        "away_ext": 6,     # Mexico
        "kickoff_utc": datetime(2026, 6, 11, 20, 0, tzinfo=timezone.utc),
        "venue": "SoFi Stadium, Los Angeles",
        "stage": "group_stage",
        "group_name": "A",
        "match_day": 1,
        "status": "scheduled",
    },
    {
        "external_id": 900002,
        "home_ext": 24,    # Canada
        "away_ext": 9,     # Brazil
        "kickoff_utc": datetime(2026, 6, 12, 0, 0, tzinfo=timezone.utc),
        "venue": "BMO Field, Toronto",
        "stage": "group_stage",
        "group_name": "B",
        "match_day": 1,
        "status": "scheduled",
    },
    # Group B — match day 1
    {
        "external_id": 900003,
        "home_ext": 26,    # Argentina
        "away_ext": 2,     # England
        "kickoff_utc": datetime(2026, 6, 12, 16, 0, tzinfo=timezone.utc),
        "venue": "MetLife Stadium, New York",
        "stage": "group_stage",
        "group_name": "C",
        "match_day": 1,
        "status": "scheduled",
    },
    {
        "external_id": 900004,
        "home_ext": 27,    # France
        "away_ext": 8,     # Germany
        "kickoff_utc": datetime(2026, 6, 13, 0, 0, tzinfo=timezone.utc),
        "venue": "AT&T Stadium, Dallas",
        "stage": "group_stage",
        "group_name": "D",
        "match_day": 1,
        "status": "scheduled",
    },
    # Final (placeholder)
    {
        "external_id": 900064,
        "home_ext": None,
        "away_ext": None,
        "kickoff_utc": datetime(2026, 7, 19, 20, 0, tzinfo=timezone.utc),
        "venue": "MetLife Stadium, New York",
        "stage": "final",
        "group_name": None,
        "match_day": None,
        "status": "scheduled",
    },
]


async def seed(db: AsyncSession) -> None:
    log.info("seed.start")

    # 0. Dev user (for MOCK_AUTH local testing)
    stmt = (
        pg_insert(User)
        .values(**_DEV_USER)
        .on_conflict_do_update(
            index_elements=["id"],
            set_={
                "username": _DEV_USER["username"],
                "email": _DEV_USER["email"],
                "display_name": _DEV_USER["display_name"],
            },
        )
    )
    await db.execute(stmt)
    await db.commit()
    await auto_join_global_parties(db, _DEV_USER["id"])
    await db.commit()
    log.info("seed.dev_user_upserted", user_id=str(_DEV_USER["id"]))

    # 1. Tournament
    stmt = (
        pg_insert(Tournament)
        .values(**_TOURNAMENT)
        .on_conflict_do_update(
            index_elements=["external_id"],
            set_={
                "name": _TOURNAMENT["name"],
                "season": _TOURNAMENT["season"],
                "status": _TOURNAMENT["status"],
            },
        )
        .returning(Tournament.id)
    )
    row = (await db.execute(stmt)).fetchone()
    tournament_id = row[0]
    await db.commit()
    log.info("seed.tournament_upserted", tournament_id=str(tournament_id))

    # 2. Teams
    for t in _TEAMS:
        stmt = (
            pg_insert(Team)
            .values(**t)
            .on_conflict_do_update(
                index_elements=["external_id"],
                set_={"name": t["name"], "short_name": t["short_name"]},
            )
        )
        await db.execute(stmt)
    await db.commit()

    # Re-fetch team ID map.
    from sqlalchemy import select

    ext_ids = [t["external_id"] for t in _TEAMS]
    team_rows = (
        await db.execute(select(Team.external_id, Team.id).where(Team.external_id.in_(ext_ids)))
    ).all()
    team_map: dict[int, object] = {ext: db_id for ext, db_id in team_rows}
    log.info("seed.teams_upserted", count=len(team_map))

    # 3. Matches
    for f in _FIXTURES:
        home_id = team_map.get(f["home_ext"]) if f["home_ext"] else None
        away_id = team_map.get(f["away_ext"]) if f["away_ext"] else None
        stmt = (
            pg_insert(Match)
            .values(
                external_id=f["external_id"],
                tournament_id=tournament_id,
                home_team_id=home_id,
                away_team_id=away_id,
                kickoff_utc=f["kickoff_utc"],
                venue=f["venue"],
                stage=f["stage"],
                group_name=f["group_name"],
                match_day=f["match_day"],
                status=f["status"],
            )
            .on_conflict_do_update(
                index_elements=["external_id"],
                set_={
                    "home_team_id": home_id,
                    "away_team_id": away_id,
                    "kickoff_utc": f["kickoff_utc"],
                    "venue": f["venue"],
                    "stage": f["stage"],
                    "group_name": f["group_name"],
                    "match_day": f["match_day"],
                    "status": f["status"],
                },
            )
        )
        await db.execute(stmt)
    await db.commit()
    log.info("seed.matches_upserted", count=len(_FIXTURES))

    # 4. Tournament teams
    for db_id in team_map.values():
        stmt = (
            pg_insert(TournamentTeam)
            .values(tournament_id=tournament_id, team_id=db_id)
            .on_conflict_do_nothing()
        )
        await db.execute(stmt)
    await db.commit()

    log.info("seed.done")


async def _main() -> None:
    async with AsyncSessionLocal() as db:
        await seed(db)


if __name__ == "__main__":
    asyncio.run(_main())
