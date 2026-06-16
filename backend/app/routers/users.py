import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.prediction import PublicPredictionResponse
from app.schemas.user import PublicUserResponse, UserResponse, UserUpdateRequest
from app.services import prediction_service

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.patch("/me", response_model=UserResponse)
async def update_me(
    body: UserUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    for field in body.model_fields_set:
        setattr(current_user, field, getattr(body, field))

    db.add(current_user)
    await db.commit()
    await db.refresh(current_user)
    return current_user


@router.get("/{user_id}", response_model=PublicUserResponse)
async def get_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.get("/{user_id}/predictions", response_model=list[PublicPredictionResponse])
async def get_user_scored_predictions(
    user_id: uuid.UUID,
    tournament_id: Optional[uuid.UUID] = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """A player's already-scored predictions, viewable by any authenticated user.

    Exposes no email or private profile data — pair with GET /users/{id} for the
    public display name/avatar.
    """
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return await prediction_service.get_public_user_predictions(
        db, user_id, tournament_id=tournament_id
    )
