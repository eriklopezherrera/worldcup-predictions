import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import TIMESTAMP, Computed, ForeignKey, Index, Integer, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Prediction(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "predictions"
    __table_args__ = (
        UniqueConstraint("user_id", "match_id"),
        Index("idx_predictions_user", "user_id"),
        Index("idx_predictions_match", "match_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
    )
    match_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("matches.id", ondelete="CASCADE"),
    )
    predicted_home_score: Mapped[int] = mapped_column(Integer)
    predicted_away_score: Mapped[int] = mapped_column(Integer)
    points_result: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    points_exact: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    total_points: Mapped[int] = mapped_column(
        Integer,
        Computed("points_result + points_exact", persisted=True),
    )
    scored_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))
