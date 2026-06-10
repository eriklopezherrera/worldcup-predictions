"""
Populate the local DB with the full FIFA World Cup 2026 match schedule.

Reads ``backend/worldcup2026_matches.json`` and inserts every match into the
``matches`` table, linked to the "FIFA World Cup 2026" tournament. Teams are
resolved by name; ``group_name`` for group-stage matches is derived from each
team's ``tournament_teams`` group. Knockout matches have null teams until the
bracket is decided.

Re-runnable: deletes existing matches for the tournament before inserting.

Usage:
    cd backend
    python -m app.workers.populate_wc2026_matches
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path

import structlog
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.match import Match
from app.models.tournament import Team, Tournament, TournamentTeam

log = structlog.get_logger()

# parents[2] is backend/ locally and /var/task in Lambda — the JSON sits at
# that root in both cases.
_JSON_PATH = Path(__file__).resolve().parents[2] / "worldcup2026_matches.json"
_TOURNAMENT_EXTERNAL_ID = 1


def _parse_kickoff(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


async def populate(db: AsyncSession) -> None:
    matches = json.loads(_JSON_PATH.read_text(encoding="utf-8"))
    log.info("populate.start", matches=len(matches), source=str(_JSON_PATH))

    tournament_id = (
        await db.execute(
            select(Tournament.id).where(
                Tournament.external_id == _TOURNAMENT_EXTERNAL_ID
            )
        )
    ).scalar_one()

    # name -> team.id
    team_map = {
        name: tid
        for name, tid in (await db.execute(select(Team.name, Team.id))).all()
    }
    # team.id -> group_name (for this tournament)
    group_map = {
        tid: grp
        for tid, grp in (
            await db.execute(
                select(TournamentTeam.team_id, TournamentTeam.group_name).where(
                    TournamentTeam.tournament_id == tournament_id
                )
            )
        ).all()
    }

    # Clean slate for this tournament so re-runs don't duplicate.
    await db.execute(delete(Match).where(Match.tournament_id == tournament_id))

    missing: set[str] = set()
    inserted = 0
    for m in matches:
        home_name = m["home_team"]
        away_name = m["away_team"]
        home_id = team_map.get(home_name) if home_name else None
        away_id = team_map.get(away_name) if away_name else None

        for nm, resolved in ((home_name, home_id), (away_name, away_id)):
            if nm and resolved is None:
                missing.add(nm)

        # Derive group only for group-stage matches with a known home team.
        group_name = None
        if m["stage"] == "group_stage" and home_id is not None:
            group_name = group_map.get(home_id)

        db.add(
            Match(
                tournament_id=tournament_id,
                home_team_id=home_id,
                away_team_id=away_id,
                kickoff_utc=_parse_kickoff(m["kick_off"]),
                venue=m.get("venue"),
                stage=m["stage"],
                group_name=group_name,
                status="scheduled",
            )
        )
        inserted += 1

    if missing:
        log.warning("populate.unmatched_teams", names=sorted(missing))

    await db.commit()
    log.info("populate.done", matches_inserted=inserted)


async def _main() -> None:
    async with AsyncSessionLocal() as db:
        await populate(db)


if __name__ == "__main__":
    asyncio.run(_main())
