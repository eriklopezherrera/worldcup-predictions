"""add default_prediction_stage to tournaments

Revision ID: a1b2c3d4e5f6
Revises: 0f15b0829b0c
Create Date: 2026-06-10 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '0f15b0829b0c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'tournaments',
        sa.Column(
            'default_prediction_stage',
            sa.String(length=20),
            server_default=sa.text("'group'"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column('tournaments', 'default_prediction_stage')
