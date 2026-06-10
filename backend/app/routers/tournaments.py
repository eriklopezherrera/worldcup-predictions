import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.match import MatchResponse
from app.schemas.tournament import (
    TournamentDetailResponse,
    TournamentResponse,
    TournamentTeamResponse,
)
from app.services import match_service

router = APIRouter(prefix="/tournaments", tags=["tournaments"])


@router.get("", response_model=list[TournamentResponse])
async def list_tournaments(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return await match_service.get_tournaments(db)


@router.get("/{tournament_id}", response_model=TournamentDetailResponse)
async def get_tournament(
    tournament_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    tournament, team_rows = await match_service.get_tournament(db, tournament_id)
    if tournament is None:
        raise HTTPException(status_code=404, detail="Tournament not found")

    teams = [
        TournamentTeamResponse(
            id=team.id,
            name=team.name,
            short_name=team.short_name,
            logo_url=team.logo_url,
            group_name=group_name,
        )
        for team, group_name in team_rows
    ]
    return TournamentDetailResponse(
        id=tournament.id,
        name=tournament.name,
        season=tournament.season,
        status=tournament.status,
        logo_url=tournament.logo_url,
        country=tournament.country,
        default_prediction_stage=tournament.default_prediction_stage,
        teams=teams,
    )


@router.get("/{tournament_id}/matches", response_model=list[MatchResponse])
async def list_tournament_matches(
    tournament_id: uuid.UUID,
    stage: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    group: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await match_service.get_matches(
        db,
        tournament_id,
        current_user.id,
        stage=stage,
        status=status,
        group=group,
    )
