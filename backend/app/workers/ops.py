"""
Operations Lambda handler: run DB migrations and data loads against the
deployed environment without needing direct network access to RDS.

Invoked manually (see ``infrastructure/scripts/migrate.sh``):

    aws lambda invoke --function-name worldcup-prod-ops \
        --payload '{"action": "migrate"}' out.json

Actions:
    {"action": "migrate"}                          -> alembic upgrade head
    {"action": "seed"}                             -> load WC2026 teams + matches
    {"action": "make_admin", "identifier": "x@y"}  -> grant admin (``"revoke": true`` to revoke)
    {"action": "update_match_kickoff",             -> reschedule one fixture
        "home_team": "Australia", "away_team": "Türkiye",
        "kickoff": "2026-06-14T04:00:00Z"}
"""

import asyncio
from pathlib import Path

import structlog

log = structlog.get_logger()

_BASE_DIR = Path(__file__).resolve().parents[2]  # backend/ locally, /var/task in Lambda


def _migrate() -> None:
    from alembic import command
    from alembic.config import Config

    from app.config import settings

    cfg = Config(str(_BASE_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(_BASE_DIR / "migrations"))
    # ConfigParser treats % as interpolation — escape the URL-encoded password.
    cfg.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))
    command.upgrade(cfg, "head")


async def _seed() -> None:
    from app.database import AsyncSessionLocal
    from app.workers import populate_wc2026_matches, populate_wc2026_teams

    async with AsyncSessionLocal() as db:
        await populate_wc2026_teams.populate(db)
    async with AsyncSessionLocal() as db:
        await populate_wc2026_matches.populate(db)


def handler(event, context):
    action = (event or {}).get("action")
    log.info("ops.invoke", action=action)

    if action == "migrate":
        _migrate()
    elif action == "seed":
        asyncio.run(_seed())
    elif action == "make_admin":
        from app.workers.make_admin import set_admin

        asyncio.run(set_admin(event["identifier"], not event.get("revoke", False)))
    elif action == "update_match_kickoff":
        from app.workers.update_match_kickoff import update_kickoff

        asyncio.run(
            update_kickoff(event["home_team"], event["away_team"], event["kickoff"])
        )
    else:
        raise ValueError(f"Unknown action: {action!r}")

    log.info("ops.done", action=action)
    return {"status": "ok", "action": action}
