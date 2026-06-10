import uuid

from pydantic import BaseModel, ConfigDict, Field


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
