import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import TIMESTAMP, ForeignKey, Index, Integer, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base, UUIDPrimaryKeyMixin


class LeaderboardSnapshot(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "leaderboard_snapshots"
    __table_args__ = (
        UniqueConstraint("party_id", "user_id", "tournament_id"),
        Index("idx_leaderboard_party", "party_id", "tournament_id"),
    )

    party_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("parties.id", ondelete="CASCADE"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
    )
    tournament_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tournaments.id", ondelete="CASCADE"),
    )
    total_points: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    exact_scores: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    predictions_made: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    rank: Mapped[Optional[int]] = mapped_column(Integer)
    computed_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())
