import uuid
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.party import (
    JoinPartyRequest,
    LeaderboardResponse,
    MemberResponse,
    PartyCreate,
    PartyResponse,
)
from app.services import party_service

router = APIRouter(prefix="/parties", tags=["parties"])


# ------------------------------------------------------------------
# Public — no auth required
# ------------------------------------------------------------------


@router.get("/invite/{invite_code}", response_model=PartyResponse)
async def preview_party(
    invite_code: str,
    db: AsyncSession = Depends(get_db),
):
    return await party_service.get_party_preview(db, invite_code)


# ------------------------------------------------------------------
# Authenticated endpoints — literal paths before parametric
# ------------------------------------------------------------------


@router.post("/join", response_model=PartyResponse)
async def join_party(
    body: JoinPartyRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await party_service.join_party(db, current_user.id, body.invite_code)


@router.get("", response_model=list[PartyResponse])
async def list_parties(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await party_service.get_user_parties(db, current_user.id)


@router.post("", response_model=PartyResponse)
async def create_party(
    body: PartyCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await party_service.create_party(
        db, current_user.id, body.name, body.tournament_id
    )


# ------------------------------------------------------------------
# Parametric paths
# ------------------------------------------------------------------


@router.get("/{party_id}", response_model=PartyResponse)
async def get_party(
    party_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await party_service.get_party(db, party_id, current_user.id)


@router.get("/{party_id}/members", response_model=list[MemberResponse])
async def list_members(
    party_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await party_service.get_party_members(db, party_id, current_user.id)


@router.get("/{party_id}/leaderboard", response_model=LeaderboardResponse)
async def get_leaderboard(
    party_id: uuid.UUID,
    tournament_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await party_service.get_party_leaderboard(
        db, party_id, tournament_id, current_user.id
    )


@router.delete("/{party_id}/leave")
async def leave_party(
    party_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await party_service.leave_party(db, current_user.id, party_id)
    return {"message": "Left party"}


@router.delete("/{party_id}")
async def delete_party(
    party_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await party_service.delete_party(db, current_user.id, party_id)
    return {"message": "Party deleted"}
