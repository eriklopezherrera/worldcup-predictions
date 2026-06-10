import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TeamSummary(BaseModel):
    id: uuid.UUID
    name: str
    short_name: str | None
    logo_url: str | None

    model_config = ConfigDict(from_attributes=True)


class PredictionInMatch(BaseModel):
    id: uuid.UUID
    predicted_home_score: int
    predicted_away_score: int
    points_result: int
    points_exact: int
    total_points: int

    model_config = ConfigDict(from_attributes=True)


class MatchResponse(BaseModel):
    id: uuid.UUID
    tournament_id: uuid.UUID
    home_team: TeamSummary | None
    away_team: TeamSummary | None
    kickoff_utc: datetime
    venue: str | None
    stage: str
    group_name: str | None
    match_day: int | None
    home_score: int | None
    away_score: int | None
    status: str
    is_locked: bool
    actual_result: str | None  # "home_win" | "away_win" | "draw" | None
    my_prediction: PredictionInMatch | None


class MatchResultRequest(BaseModel):
    home_score: int = Field(ge=0, le=99)
    away_score: int = Field(ge=0, le=99)


class MatchResultResponse(BaseModel):
    match_id: uuid.UUID
    home_score: int
    away_score: int
    status: str
    predictions_scored: int
    leaderboards_recomputed: int
