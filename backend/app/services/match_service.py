import uuid
from datetime import datetime, timezone
from typing import Optional

import structlog
from fastapi import HTTPException
from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.match import Match
from app.models.party import PartyMember
from app.models.prediction import Prediction
from app.models.tournament import Team, Tournament, TournamentTeam
from app.services.leaderboard_service import recompute_party_leaderboard
from app.services.scoring_service import compute_points

log = structlog.get_logger()


def _compute_actual_result(match: Match) -> Optional[str]:
    if match.home_score is None or match.away_score is None:
        return None
    if match.home_score > match.away_score:
        return "home_win"
    if match.away_score > match.home_score:
        return "away_win"
    return "draw"


def _team_dict(team: Optional[Team]) -> Optional[dict]:
    if team is None:
        return None
    return {
        "id": team.id,
        "name": team.name,
        "short_name": team.short_name,
        "logo_url": team.logo_url,
    }


def _prediction_dict(prediction: Optional[Prediction]) -> Optional[dict]:
    if prediction is None:
        return None
    return {
        "id": prediction.id,
        "predicted_home_score": prediction.predicted_home_score,
        "predicted_away_score": prediction.predicted_away_score,
        "points_result": prediction.points_result,
        "points_exact": prediction.points_exact,
        "total_points": prediction.total_points,
    }


def _build_match_dict(
    match: Match,
    home_team: Optional[Team],
    away_team: Optional[Team],
    prediction: Optional[Prediction],
) -> dict:
    return {
        "id": match.id,
        "tournament_id": match.tournament_id,
        "home_team": _team_dict(home_team),
        "away_team": _team_dict(away_team),
        "kickoff_utc": match.kickoff_utc,
        "venue": match.venue,
        "stage": match.stage,
        "group_name": match.group_name,
        "match_day": match.match_day,
        "home_score": match.home_score,
        "away_score": match.away_score,
        "status": match.status,
        "is_locked": match.kickoff_utc <= datetime.now(timezone.utc),
        "predictions_open": match.predictions_open,
        "actual_result": _compute_actual_result(match),
        "my_prediction": _prediction_dict(prediction),
    }


async def get_tournaments(db: AsyncSession) -> list[Tournament]:
    result = await db.execute(select(Tournament).order_by(Tournament.created_at.desc()))
    return list(result.scalars().all())


async def get_tournament(
    db: AsyncSession, tournament_id: uuid.UUID
) -> tuple[Optional[Tournament], list]:
    """Returns (Tournament, [(Team, group_name)]) or (None, [])."""
    tournament = await db.get(Tournament, tournament_id)
    if tournament is None:
        return None, []

    stmt = (
        select(Team, TournamentTeam.group_name)
        .join(TournamentTeam, TournamentTeam.team_id == Team.id)
        .where(TournamentTeam.tournament_id == tournament_id)
        .order_by(TournamentTeam.group_name, Team.name)
    )
    result = await db.execute(stmt)
    return tournament, result.all()


async def get_matches(
    db: AsyncSession,
    tournament_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    stage: Optional[str] = None,
    status: Optional[str] = None,
    group: Optional[str] = None,
) -> list[dict]:
    conditions = [Match.tournament_id == tournament_id]
    if stage:
        conditions.append(Match.stage == stage)
    if status:
        conditions.append(Match.status == status)
    if group:
        conditions.append(Match.group_name == group)

    stmt = (
        select(Match, Prediction)
        .outerjoin(
            Prediction,
            and_(Prediction.match_id == Match.id, Prediction.user_id == user_id),
        )
        .where(*conditions)
        .order_by(Match.kickoff_utc)
    )
    rows = (await db.execute(stmt)).all()

    team_ids = {
        tid
        for match, _ in rows
        for tid in (match.home_team_id, match.away_team_id)
        if tid is not None
    }
    teams: dict[uuid.UUID, Team] = {}
    if team_ids:
        team_result = await db.execute(select(Team).where(Team.id.in_(team_ids)))
        teams = {t.id: t for t in team_result.scalars()}

    return [
        _build_match_dict(
            match,
            teams.get(match.home_team_id),
            teams.get(match.away_team_id),
            prediction,
        )
        for match, prediction in rows
    ]


async def get_match(
    db: AsyncSession, match_id: uuid.UUID, user_id: uuid.UUID
) -> Optional[dict]:
    stmt = (
        select(Match, Prediction)
        .outerjoin(
            Prediction,
            and_(Prediction.match_id == Match.id, Prediction.user_id == user_id),
        )
        .where(Match.id == match_id)
    )
    row = (await db.execute(stmt)).first()
    if row is None:
        return None

    match, prediction = row
    home_team = await db.get(Team, match.home_team_id) if match.home_team_id else None
    away_team = await db.get(Team, match.away_team_id) if match.away_team_id else None
    return _build_match_dict(match, home_team, away_team, prediction)


async def _validate_team_in_tournament(
    db: AsyncSession, tournament_id: uuid.UUID, team_id: uuid.UUID
) -> None:
    exists = (
        await db.execute(
            select(TournamentTeam.team_id).where(
                TournamentTeam.tournament_id == tournament_id,
                TournamentTeam.team_id == team_id,
            )
        )
    ).scalar_one_or_none()
    if exists is None:
        raise HTTPException(
            status_code=400, detail="Team is not part of this tournament"
        )


async def update_match(
    db: AsyncSession,
    match_id: uuid.UUID,
    *,
    user_id: uuid.UUID,
    kickoff_utc: Optional[datetime] = None,
    home_team_id: Optional[uuid.UUID] = None,
    away_team_id: Optional[uuid.UUID] = None,
    set_home_team: bool = False,
    set_away_team: bool = False,
) -> Optional[dict]:
    """Admin edit of a single fixture (kickoff and/or teams).

    Teams may only be changed while the match has no predictions yet — swapping
    a team after people have predicted would invalidate their picks. Returns the
    updated match dict, or None if the match doesn't exist. Raises HTTPException
    (409) when a team change is blocked, (400) for an invalid team.
    """
    match = await db.get(Match, match_id)
    if match is None:
        return None

    changing_teams = set_home_team or set_away_team
    if changing_teams:
        prediction_count = (
            await db.execute(
                select(func.count(Prediction.id)).where(
                    Prediction.match_id == match_id
                )
            )
        ).scalar_one()
        if prediction_count > 0:
            raise HTTPException(
                status_code=409,
                detail="Cannot change teams: predictions already exist for this match",
            )

    if set_home_team:
        if home_team_id is not None:
            await _validate_team_in_tournament(db, match.tournament_id, home_team_id)
        match.home_team_id = home_team_id
    if set_away_team:
        if away_team_id is not None:
            await _validate_team_in_tournament(db, match.tournament_id, away_team_id)
        match.away_team_id = away_team_id
    if kickoff_utc is not None:
        match.kickoff_utc = kickoff_utc

    await db.commit()

    log.info(
        "match.updated",
        match_id=str(match_id),
        kickoff_changed=kickoff_utc is not None,
        home_team_changed=set_home_team,
        away_team_changed=set_away_team,
    )
    return await get_match(db, match_id, user_id)


async def set_stage_predictions_open(
    db: AsyncSession,
    tournament_id: uuid.UUID,
    stage: str,
    predictions_open: bool,
) -> dict:
    """Open or close predictions for every match of a stage in a tournament."""
    result = await db.execute(
        update(Match)
        .where(Match.tournament_id == tournament_id, Match.stage == stage)
        .values(predictions_open=predictions_open)
    )
    await db.commit()
    log.info(
        "stage.predictions_set",
        tournament_id=str(tournament_id),
        stage=stage,
        predictions_open=predictions_open,
        matches_updated=result.rowcount,
    )
    return {
        "stage": stage,
        "predictions_open": predictions_open,
        "matches_updated": result.rowcount or 0,
    }


async def set_match_result(
    db: AsyncSession,
    match_id: uuid.UUID,
    home_score: int,
    away_score: int,
) -> Optional[dict]:
    """Record a final score, (re-)score every prediction for the match, and
    recompute the leaderboards of all affected parties.

    Re-scores predictions even if already scored, so an admin can correct a
    score that was entered wrong. Returns None if the match doesn't exist.
    """
    match = await db.get(Match, match_id)
    if match is None:
        return None

    match.home_score = home_score
    match.away_score = away_score
    match.status = "finished"

    predictions = (
        await db.execute(select(Prediction).where(Prediction.match_id == match_id))
    ).scalars().all()

    now = datetime.now(timezone.utc)
    for pred in predictions:
        pred.points_result, pred.points_exact = compute_points(
            pred.predicted_home_score,
            pred.predicted_away_score,
            home_score,
            away_score,
        )
        pred.scored_at = now

    await db.commit()

    rows = (
        await db.execute(
            select(PartyMember.party_id)
            .join(Prediction, Prediction.user_id == PartyMember.user_id)
            .where(Prediction.match_id == match_id)
            .distinct()
        )
    ).scalars().all()

    for party_id in rows:
        await recompute_party_leaderboard(db, party_id, match.tournament_id)

    log.info(
        "match_result.set",
        match_id=str(match_id),
        home_score=home_score,
        away_score=away_score,
        predictions_scored=len(predictions),
        leaderboards_recomputed=len(rows),
    )
    return {
        "match_id": match.id,
        "home_score": home_score,
        "away_score": away_score,
        "status": match.status,
        "predictions_scored": len(predictions),
        "leaderboards_recomputed": len(rows),
    }
