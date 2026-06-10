import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.match import Match
from app.models.prediction import Prediction
from app.models.tournament import Team, Tournament, TournamentTeam


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
