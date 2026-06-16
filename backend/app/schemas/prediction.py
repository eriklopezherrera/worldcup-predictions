import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.match import TeamSummary


class PredictionCreate(BaseModel):
    predicted_home_score: int = Field(ge=0, le=30)
    predicted_away_score: int = Field(ge=0, le=30)


class PredictionResponse(BaseModel):
    id: uuid.UUID
    match_id: uuid.UUID
    predicted_home_score: int
    predicted_away_score: int
    points_result: int
    points_exact: int
    total_points: int
    is_locked: bool

    model_config = ConfigDict(from_attributes=True)


class PredictionSummary(BaseModel):
    total_points: int
    exact_scores: int
    predictions_made: int


class PublicPredictionResponse(BaseModel):
    """A single scored prediction of another user, with read-only match context.

    Deliberately carries no information about the predicting user beyond the
    pick itself — caller identity is supplied separately via PublicUserResponse.
    """

    match_id: uuid.UUID
    tournament_id: uuid.UUID
    home_team: TeamSummary | None
    away_team: TeamSummary | None
    kickoff_utc: datetime
    stage: str
    group_name: str | None
    home_score: int | None
    away_score: int | None
    actual_result: str | None  # "home_win" | "away_win" | "draw" | None
    predicted_home_score: int
    predicted_away_score: int
    points_result: int
    points_exact: int
    total_points: int
