"""
Update the kickoff time of a single match, identified by its two team names.

Targeted single-row edit for when a fixture is rescheduled — safe to run
against a live DB (does not touch any other match or any predictions).

Usage:
    cd backend
    python -m app.workers.update_match_kickoff "Australia" "Türkiye" 2026-06-14T04:00:00Z
"""

import asyncio
import sys
from datetime import datetime

import structlog
from sqlalchemy import and_, or_, select

from app.database import AsyncSessionLocal
from app.models.match import Match
from app.models.tournament import Team

log = structlog.get_logger()


def _parse_kickoff(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


async def update_kickoff(home_team: str, away_team: str, kickoff: str) -> None:
    new_kickoff = _parse_kickoff(kickoff)
    async with AsyncSessionLocal() as db:
        home = (
            await db.execute(select(Team).where(Team.name == home_team))
        ).scalar_one_or_none()
        away = (
            await db.execute(select(Team).where(Team.name == away_team))
        ).scalar_one_or_none()
        if home is None or away is None:
            log.error(
                "update_match_kickoff.team_not_found",
                home_team=home_team,
                away_team=away_team,
            )
            raise SystemExit(1)

        # Match the fixture regardless of which side is recorded as home/away.
        matches = (
            await db.execute(
                select(Match).where(
                    or_(
                        and_(
                            Match.home_team_id == home.id,
                            Match.away_team_id == away.id,
                        ),
                        and_(
                            Match.home_team_id == away.id,
                            Match.away_team_id == home.id,
                        ),
                    )
                )
            )
        ).scalars().all()
        if len(matches) != 1:
            log.error(
                "update_match_kickoff.expected_one_match",
                found=len(matches),
                home_team=home_team,
                away_team=away_team,
            )
            raise SystemExit(1)

        match = matches[0]
        old_kickoff = match.kickoff_utc
        match.kickoff_utc = new_kickoff
        await db.commit()
        log.info(
            "update_match_kickoff.done",
            match_id=str(match.id),
            old_kickoff=old_kickoff.isoformat(),
            new_kickoff=new_kickoff.isoformat(),
        )


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print(__doc__)
        sys.exit(1)
    asyncio.run(update_kickoff(sys.argv[1], sys.argv[2], sys.argv[3]))
