import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, require_admin
from app.models.user import User
from app.schemas.match import (
    MatchResponse,
    MatchResultRequest,
    MatchResultResponse,
    MatchUpdateRequest,
    StagePredictionsRequest,
    StagePredictionsResponse,
)
from app.services import match_service

router = APIRouter(prefix="/admin", tags=["admin"])


@router.put("/matches/{match_id}/result", response_model=MatchResultResponse)
async def set_match_result(
    match_id: uuid.UUID,
    body: MatchResultRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    result = await match_service.set_match_result(
        db,
        match_id,
        body.home_score,
        body.away_score,
        winner_team_id=body.winner_team_id,
        decided_by=body.decided_by,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Match not found")
    return result


@router.put("/matches/{match_id}", response_model=MatchResponse)
async def update_match(
    match_id: uuid.UUID,
    body: MatchUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    result = await match_service.update_match(
        db,
        match_id,
        user_id=current_user.id,
        kickoff_utc=body.kickoff_utc,
        home_team_id=body.home_team_id,
        away_team_id=body.away_team_id,
        set_home_team=body.set_home_team,
        set_away_team=body.set_away_team,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Match not found")
    return result


@router.put(
    "/tournaments/{tournament_id}/stages/{stage}",
    response_model=StagePredictionsResponse,
)
async def set_stage_predictions(
    tournament_id: uuid.UUID,
    stage: str,
    body: StagePredictionsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    return await match_service.set_stage_predictions_open(
        db, tournament_id, stage, body.predictions_open
    )
