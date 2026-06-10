import uuid
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.prediction import PredictionCreate, PredictionResponse, PredictionSummary
from app.services import prediction_service

router = APIRouter(prefix="/predictions", tags=["predictions"])


@router.get("/summary", response_model=PredictionSummary)
async def get_prediction_summary(
    tournament_id: Optional[uuid.UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await prediction_service.get_prediction_summary(
        db, current_user.id, tournament_id=tournament_id
    )


@router.get("", response_model=list[PredictionResponse])
async def list_predictions(
    tournament_id: Optional[uuid.UUID] = None,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await prediction_service.get_user_predictions(
        db, current_user.id, tournament_id=tournament_id, status=status
    )


@router.put("/{match_id}", response_model=PredictionResponse)
async def upsert_prediction(
    match_id: uuid.UUID,
    body: PredictionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await prediction_service.upsert_prediction(
        db, current_user.id, match_id, body.predicted_home_score, body.predicted_away_score
    )
