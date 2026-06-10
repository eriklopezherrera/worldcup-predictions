"""
Populate the local DB with the full FIFA World Cup 2026 team list.

Reads ``backend/worldcup2026_teams.json`` and:
  * ensures the "FIFA World Cup 2026" tournament row exists (external_id=1),
  * upserts each team into ``teams`` (matched by name, since the JSON has no
    external_id),
  * links each team to the tournament in ``tournament_teams`` with its
    ``group_name``.

Idempotent: safe to re-run.

Usage:
    cd backend
    python -m app.workers.populate_wc2026_teams
"""

import asyncio
import json
from pathlib import Path

import structlog
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.tournament import Team, Tournament, TournamentTeam

log = structlog.get_logger()

# parents[2] is backend/ locally and /var/task in Lambda — the JSON sits at
# that root in both cases.
_JSON_PATH = Path(__file__).resolve().parents[2] / "worldcup2026_teams.json"

_TOURNAMENT = {
    "external_id": 1,
    "name": "FIFA World Cup 2026",
    "season": "2026",
    "country": "USA/Canada/Mexico",
    "status": "upcoming",
}


async def populate(db: AsyncSession) -> None:
    teams = json.loads(_JSON_PATH.read_text(encoding="utf-8"))
    log.info("populate.start", teams=len(teams), source=str(_JSON_PATH))

    # 1. Tournament (upsert by external_id).
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
    tournament_id = (await db.execute(stmt)).scalar_one()
    await db.commit()
    log.info("populate.tournament", tournament_id=str(tournament_id))

    # 2. Teams + tournament_teams. Match teams by name (no external_id in JSON).
    linked = 0
    for t in teams:
        team = (
            await db.execute(select(Team).where(Team.name == t["name"]))
        ).scalar_one_or_none()
        if team is None:
            team = Team(name=t["name"], short_name=t["short_name"])
            db.add(team)
            await db.flush()  # populate team.id
        else:
            team.short_name = t["short_name"]

        link_stmt = (
            pg_insert(TournamentTeam)
            .values(
                tournament_id=tournament_id,
                team_id=team.id,
                group_name=t["group"],
            )
            .on_conflict_do_update(
                index_elements=["tournament_id", "team_id"],
                set_={"group_name": t["group"]},
            )
        )
        await db.execute(link_stmt)
        linked += 1

    await db.commit()
    log.info("populate.done", teams_linked=linked)


async def _main() -> None:
    async with AsyncSessionLocal() as db:
        await populate(db)


if __name__ == "__main__":
    asyncio.run(_main())
