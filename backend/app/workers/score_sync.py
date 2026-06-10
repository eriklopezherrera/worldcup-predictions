import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.match import Match
from app.models.party import PartyMember
from app.models.prediction import Prediction
from app.services.leaderboard_service import recompute_party_leaderboard
from app.services.scoring_service import compute_points
from app.workers.football_api_client import FootballApiClient, STATUS_MAP

log = structlog.get_logger()


async def sync_scores(
    db: AsyncSession,
    api_client: FootballApiClient,
    league_ids: list[int],
    seasons: list[int],
) -> dict:
    log.info("score_sync.start", league_ids=league_ids, seasons=seasons)

    all_fixtures: dict[int, dict] = {}
    for league_id in league_ids:
        for season in seasons:
            finished = await api_client.get_fixtures(league_id, season, status="FT")
            live = await api_client.get_live_fixtures(league_id, season)
            for f in finished + live:
                all_fixtures[f["fixture"]["id"]] = f

    if not all_fixtures:
        log.info("score_sync.no_fixtures")
        return {"scored_matches": 0}

    # Bulk-load matches from DB in one query.
    ext_ids = list(all_fixtures.keys())
    existing = (
        await db.execute(select(Match).where(Match.external_id.in_(ext_ids)))
    ).scalars().all()
    match_by_ext: dict[int, Match] = {m.external_id: m for m in existing}

    now = datetime.now(timezone.utc)
    scored_match_ids: list[uuid.UUID] = []

    for ext_id, fixture in all_fixtures.items():
        match = match_by_ext.get(ext_id)
        if not match:
            continue

        fix = fixture["fixture"]
        score = fixture.get("score", {})
        ft = score.get("fulltime") or {}
        ht = score.get("halftime") or {}
        status_short: str = fix["status"]["short"]
        our_status = STATUS_MAP.get(status_short, "scheduled")

        home_score = ft.get("home")
        away_score = ft.get("away")

        match.status = our_status
        match.home_score = home_score
        match.away_score = away_score
        match.home_score_ht = ht.get("home")
        match.away_score_ht = ht.get("away")

        if our_status == "finished" and home_score is not None and away_score is not None:
            unscored_preds = (
                await db.execute(
                    select(Prediction).where(
                        Prediction.match_id == match.id,
                        Prediction.scored_at.is_(None),
                    )
                )
            ).scalars().all()

            for pred in unscored_preds:
                pts_result, pts_exact = compute_points(
                    pred.predicted_home_score,
                    pred.predicted_away_score,
                    home_score,
                    away_score,
                )
                pred.points_result = pts_result
                pred.points_exact = pts_exact
                pred.scored_at = now

            if unscored_preds:
                scored_match_ids.append(match.id)

    await db.commit()

    if not scored_match_ids:
        log.info("score_sync.done", scored_matches=0)
        return {"scored_matches": 0}

    # Find all party/tournament combos affected by the newly scored matches.
    rows = (
        await db.execute(
            select(PartyMember.party_id, Match.tournament_id)
            .join(Prediction, Prediction.user_id == PartyMember.user_id)
            .join(Match, Match.id == Prediction.match_id)
            .where(Match.id.in_(scored_match_ids))
            .distinct()
        )
    ).all()

    for party_id, tournament_id in rows:
        await recompute_party_leaderboard(db, party_id, tournament_id)

    log.info(
        "score_sync.done",
        scored_matches=len(scored_match_ids),
        leaderboards_recomputed=len(rows),
    )
    return {"scored_matches": len(scored_match_ids)}
