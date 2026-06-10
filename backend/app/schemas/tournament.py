import uuid

from pydantic import BaseModel, ConfigDict


class TeamResponse(BaseModel):
    id: uuid.UUID
    name: str
    short_name: str | None
    logo_url: str | None

    model_config = ConfigDict(from_attributes=True)


class TournamentResponse(BaseModel):
    id: uuid.UUID
    name: str
    season: str
    status: str
    logo_url: str | None

    model_config = ConfigDict(from_attributes=True)


class TournamentTeamResponse(BaseModel):
    id: uuid.UUID
    name: str
    short_name: str | None
    logo_url: str | None
    group_name: str | None


class TournamentDetailResponse(BaseModel):
    id: uuid.UUID
    name: str
    season: str
    status: str
    logo_url: str | None
    country: str | None
    teams: list[TournamentTeamResponse]
