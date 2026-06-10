import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, require_admin
from app.models.user import User
from app.schemas.match import MatchResultRequest, MatchResultResponse
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
        db, match_id, body.home_score, body.away_score
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Match not found")
    return result
