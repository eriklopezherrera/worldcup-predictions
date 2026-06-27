import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.match import Match
from app.models.prediction import Prediction
from app.models.tournament import Team
from app.services.match_service import _compute_actual_result, _team_dict
from app.services.scoring_service import is_knockout_stage


def _build_prediction_dict(prediction: Prediction, match: Match) -> dict:
    return {
        "id": prediction.id,
        "match_id": prediction.match_id,
        "predicted_home_score": prediction.predicted_home_score,
        "predicted_away_score": prediction.predicted_away_score,
        "predicted_advancing_team_id": prediction.predicted_advancing_team_id,
        "points_result": prediction.points_result,
        "points_exact": prediction.points_exact,
        "points_advancing": prediction.points_advancing,
        "total_points": prediction.total_points,
        "is_locked": match.kickoff_utc <= datetime.now(timezone.utc),
    }


def _resolve_advancing_team_id(
    match: Match, home: int, away: int, advancing_team_id: Optional[uuid.UUID]
) -> Optional[uuid.UUID]:
    """Determine the advancing pick to store for a prediction.

    Group stage: always None. Knockout decisive scoreline: inferred as the
    predicted winner (the client value is ignored). Knockout draw: the explicit
    pick is required and must be one of the two teams (422 otherwise).
    """
    if not is_knockout_stage(match.stage):
        return None

    if home > away:
        return match.home_team_id
    if away > home:
        return match.away_team_id

    # Predicted draw — the user must pick who advances on penalties.
    if advancing_team_id is None:
        raise HTTPException(
            status_code=422,
            detail="Pick the team you expect to advance when predicting a draw.",
        )
    if advancing_team_id not in (match.home_team_id, match.away_team_id):
        raise HTTPException(
            status_code=422,
            detail="The advancing team must be one of the two teams in this match.",
        )
    return advancing_team_id


async def upsert_prediction(
    db: AsyncSession,
    user_id: uuid.UUID,
    match_id: uuid.UUID,
    home: int,
    away: int,
    advancing_team_id: Optional[uuid.UUID] = None,
) -> dict:
    match = await db.get(Match, match_id)
    if match is None:
        raise HTTPException(status_code=404, detail="Match not found")

    if match.kickoff_utc <= datetime.now(timezone.utc):
        raise HTTPException(
            status_code=423,
            detail="Match has already started. Predictions are locked.",
        )

    if (
        not match.predictions_open
        or match.home_team_id is None
        or match.away_team_id is None
    ):
        raise HTTPException(
            status_code=409,
            detail="Predictions are not open for this match yet.",
        )

    resolved_advancing = _resolve_advancing_team_id(match, home, away, advancing_team_id)

    stmt = select(Prediction).where(
        Prediction.user_id == user_id,
        Prediction.match_id == match_id,
    )
    prediction = (await db.execute(stmt)).scalar_one_or_none()

    if prediction is None:
        prediction = Prediction(
            user_id=user_id,
            match_id=match_id,
            predicted_home_score=home,
            predicted_away_score=away,
            predicted_advancing_team_id=resolved_advancing,
        )
        db.add(prediction)
    else:
        prediction.predicted_home_score = home
        prediction.predicted_away_score = away
        prediction.predicted_advancing_team_id = resolved_advancing

    await db.commit()
    await db.refresh(prediction)
    return _build_prediction_dict(prediction, match)


async def get_user_predictions(
    db: AsyncSession,
    user_id: uuid.UUID,
    tournament_id: Optional[uuid.UUID] = None,
    status: Optional[str] = None,
) -> list[dict]:
    stmt = (
        select(Prediction, Match)
        .join(Match, Prediction.match_id == Match.id)
        .where(Prediction.user_id == user_id)
    )
    if tournament_id:
        stmt = stmt.where(Match.tournament_id == tournament_id)
    if status:
        stmt = stmt.where(Match.status == status)
    stmt = stmt.order_by(Match.kickoff_utc)

    rows = (await db.execute(stmt)).all()
    return [_build_prediction_dict(pred, match) for pred, match in rows]


async def get_public_user_predictions(
    db: AsyncSession,
    user_id: uuid.UUID,
    tournament_id: Optional[uuid.UUID] = None,
) -> list[dict]:
    """Return another user's predictions that have already been scored.

    Only predictions with ``scored_at`` set are exposed, so picks for matches
    that haven't been played/scored yet stay private.
    """
    stmt = (
        select(Prediction, Match)
        .join(Match, Prediction.match_id == Match.id)
        .where(
            Prediction.user_id == user_id,
            Prediction.scored_at.is_not(None),
        )
    )
    if tournament_id:
        stmt = stmt.where(Match.tournament_id == tournament_id)
    stmt = stmt.order_by(Match.kickoff_utc)

    rows = (await db.execute(stmt)).all()

    team_ids = {
        tid
        for _, match in rows
        for tid in (match.home_team_id, match.away_team_id)
        if tid is not None
    }
    teams: dict[uuid.UUID, Team] = {}
    if team_ids:
        team_result = await db.execute(select(Team).where(Team.id.in_(team_ids)))
        teams = {t.id: t for t in team_result.scalars()}

    return [
        {
            "match_id": match.id,
            "tournament_id": match.tournament_id,
            "home_team": _team_dict(teams.get(match.home_team_id)),
            "away_team": _team_dict(teams.get(match.away_team_id)),
            "kickoff_utc": match.kickoff_utc,
            "stage": match.stage,
            "group_name": match.group_name,
            "home_score": match.home_score,
            "away_score": match.away_score,
            "winner_team_id": match.winner_team_id,
            "decided_by": match.decided_by,
            "actual_result": _compute_actual_result(match),
            "predicted_home_score": pred.predicted_home_score,
            "predicted_away_score": pred.predicted_away_score,
            "predicted_advancing_team_id": pred.predicted_advancing_team_id,
            "points_result": pred.points_result,
            "points_exact": pred.points_exact,
            "points_advancing": pred.points_advancing,
            "total_points": pred.total_points,
        }
        for pred, match in rows
    ]


async def get_prediction_summary(
    db: AsyncSession,
    user_id: uuid.UUID,
    tournament_id: Optional[uuid.UUID] = None,
) -> dict:
    stmt = select(
        func.coalesce(func.sum(Prediction.total_points), 0).label("total_points"),
        func.count(case((Prediction.points_exact > 0, 1))).label("exact_scores"),
        func.count(Prediction.id).label("predictions_made"),
    ).where(Prediction.user_id == user_id)

    if tournament_id:
        stmt = stmt.join(Match, Prediction.match_id == Match.id).where(
            Match.tournament_id == tournament_id
        )

    row = (await db.execute(stmt)).one()
    return {
        "total_points": row.total_points,
        "exact_scores": row.exact_scores,
        "predictions_made": row.predictions_made,
    }
