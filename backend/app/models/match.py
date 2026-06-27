import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import TIMESTAMP, Boolean, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Match(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "matches"
    __table_args__ = (
        Index("idx_matches_tournament", "tournament_id"),
        Index("idx_matches_kickoff", "kickoff_utc"),
        Index("idx_matches_status", "status"),
    )

    tournament_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tournaments.id", ondelete="CASCADE"),
    )
    home_team_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("teams.id"),
    )
    away_team_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("teams.id"),
    )
    kickoff_utc: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True))
    venue: Mapped[Optional[str]] = mapped_column(String(120))
    stage: Mapped[str] = mapped_column(String(30))
    group_name: Mapped[Optional[str]] = mapped_column(String(5))
    match_day: Mapped[Optional[int]] = mapped_column(Integer)
    home_score: Mapped[Optional[int]] = mapped_column(Integer)
    away_score: Mapped[Optional[int]] = mapped_column(Integer)
    home_score_ht: Mapped[Optional[int]] = mapped_column(Integer)
    away_score_ht: Mapped[Optional[int]] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), server_default=text("'scheduled'"))
    # When false, predictions are not yet allowed for this match (e.g. knockout
    # fixtures whose teams aren't decided). Admins open a whole stage at once.
    predictions_open: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    external_id: Mapped[Optional[int]] = mapped_column(Integer, unique=True)
