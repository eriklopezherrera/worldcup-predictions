import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import TIMESTAMP, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Tournament(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "tournaments"

    name: Mapped[str] = mapped_column(String(120))
    season: Mapped[str] = mapped_column(String(10))
    country: Mapped[Optional[str]] = mapped_column(String(80))
    logo_url: Mapped[Optional[str]] = mapped_column(Text)
    external_id: Mapped[Optional[int]] = mapped_column(Integer, unique=True)
    status: Mapped[str] = mapped_column(String(20), server_default=text("'upcoming'"))


class Team(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "teams"

    name: Mapped[str] = mapped_column(String(120))
    short_name: Mapped[Optional[str]] = mapped_column(String(10))
    logo_url: Mapped[Optional[str]] = mapped_column(Text)
    external_id: Mapped[Optional[int]] = mapped_column(Integer, unique=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())


class TournamentTeam(Base):
    __tablename__ = "tournament_teams"

    tournament_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tournaments.id", ondelete="CASCADE"),
        primary_key=True,
    )
    team_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("teams.id", ondelete="CASCADE"),
        primary_key=True,
    )
    group_name: Mapped[Optional[str]] = mapped_column(String(5))
