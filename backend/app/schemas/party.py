import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class PartyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    tournament_id: Optional[uuid.UUID] = None


class JoinPartyRequest(BaseModel):
    invite_code: str


class PartyResponse(BaseModel):
    id: uuid.UUID
    name: str
    invite_code: str
    created_by: uuid.UUID
    tournament_id: Optional[uuid.UUID]
    is_global: bool
    max_members: int
    member_count: int = 0
    model_config = ConfigDict(from_attributes=True)


class MemberResponse(BaseModel):
    user_id: uuid.UUID
    username: str
    display_name: Optional[str]
    avatar_url: Optional[str]
    role: str
    joined_at: datetime
    total_points: int = 0
    rank: Optional[int] = None


class LeaderboardEntry(BaseModel):
    user_id: uuid.UUID
    username: str
    display_name: Optional[str]
    avatar_url: Optional[str]
    total_points: int
    exact_scores: int
    predictions_made: int
    rank: int


class LeaderboardResponse(BaseModel):
    party_id: uuid.UUID
    tournament_id: uuid.UUID
    entries: list[LeaderboardEntry]
    computed_at: Optional[datetime] = None
