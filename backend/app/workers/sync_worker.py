"""
Lambda handler for the data sync worker.

Triggered by EventBridge with payload:
    {"sync_type": "fixtures"}  — daily full fixture sync
    {"sync_type": "scores"}    — every-3-minute live score sync
"""

import asyncio

import structlog

from app.config import settings
from app.database import AsyncSessionLocal
from app.workers.fixture_sync import sync_fixtures
from app.workers.football_api_client import FootballApiClient
from app.workers.score_sync import sync_scores

log = structlog.get_logger()


def handler(event: dict, context: object) -> dict:
    sync_type = event.get("sync_type", "scores")
    log.info("sync_worker.invoked", sync_type=sync_type)

    if sync_type == "fixtures":
        asyncio.run(_run_fixture_sync())
    elif sync_type == "scores":
        asyncio.run(_run_score_sync())
    else:
        log.error("sync_worker.unknown_sync_type", sync_type=sync_type)
        return {"status": "error", "reason": f"Unknown sync_type: {sync_type!r}"}

    return {"status": "ok", "sync_type": sync_type}


async def _run_fixture_sync() -> None:
    league_ids = settings.get_league_ids()
    seasons = settings.get_seasons()
    async with FootballApiClient(settings.football_api_key) as client:
        async with AsyncSessionLocal() as db:
            for league_id in league_ids:
                for season in seasons:
                    try:
                        result = await sync_fixtures(db, client, league_id, season)
                        log.info(
                            "fixture_sync.league_done",
                            league_id=league_id,
                            season=season,
                            result=result,
                        )
                    except Exception:
                        log.exception(
                            "fixture_sync.league_failed",
                            league_id=league_id,
                            season=season,
                        )


async def _run_score_sync() -> None:
    league_ids = settings.get_league_ids()
    seasons = settings.get_seasons()
    async with FootballApiClient(settings.football_api_key) as client:
        async with AsyncSessionLocal() as db:
            try:
                result = await sync_scores(db, client, league_ids, seasons)
                log.info("score_sync.run_done", result=result)
            except Exception:
                log.exception("score_sync.run_failed")
