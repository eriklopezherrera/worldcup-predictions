"""knockout advancing scoring: winner/advancing columns + total_points

Adds the data needed for knockout-stage scoring (1 pt outcome / 2 pts exact /
2 pts advancing team):

- matches.winner_team_id  — the team that advanced (penalty winner for shootouts)
- matches.decided_by      — 'regulation' | 'extra_time' | 'penalties' (display)
- predictions.predicted_advancing_team_id — user's advancing pick (inferred for
  decisive predictions, explicit for predicted draws, null for group stage)
- predictions.points_advancing — the 0/2 advancing component

total_points is a STORED generated column, so its expression can't be altered in
place; it is dropped and recreated to fold in points_advancing.

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-06-27 12:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID


revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "matches",
        sa.Column("winner_team_id", UUID(as_uuid=True), sa.ForeignKey("teams.id"), nullable=True),
    )
    op.add_column("matches", sa.Column("decided_by", sa.String(length=20), nullable=True))

    op.add_column(
        "predictions",
        sa.Column(
            "predicted_advancing_team_id",
            UUID(as_uuid=True),
            sa.ForeignKey("teams.id"),
            nullable=True,
        ),
    )
    op.add_column(
        "predictions",
        sa.Column(
            "points_advancing",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )

    # Redefine the generated total_points column to include the advancing points.
    op.execute("ALTER TABLE predictions DROP COLUMN total_points")
    op.execute(
        "ALTER TABLE predictions ADD COLUMN total_points INTEGER "
        "GENERATED ALWAYS AS (points_result + points_exact + points_advancing) STORED"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE predictions DROP COLUMN total_points")
    op.execute(
        "ALTER TABLE predictions ADD COLUMN total_points INTEGER "
        "GENERATED ALWAYS AS (points_result + points_exact) STORED"
    )
    op.drop_column("predictions", "points_advancing")
    op.drop_column("predictions", "predicted_advancing_team_id")
    op.drop_column("matches", "decided_by")
    op.drop_column("matches", "winner_team_id")
