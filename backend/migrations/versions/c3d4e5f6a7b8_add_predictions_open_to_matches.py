"""add predictions_open to matches

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-06-25 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'matches',
        sa.Column(
            'predictions_open',
            sa.Boolean(),
            server_default=sa.text('false'),
            nullable=False,
        ),
    )
    # Group-stage fixtures have known teams and should be predictable already.
    op.execute(
        "UPDATE matches SET predictions_open = true WHERE stage = 'group_stage'"
    )


def downgrade() -> None:
    op.drop_column('matches', 'predictions_open')
