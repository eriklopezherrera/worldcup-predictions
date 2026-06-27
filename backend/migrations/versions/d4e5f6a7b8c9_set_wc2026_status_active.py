"""set FIFA World Cup 2026 status to active

The WC2026 tournament was seeded as 'upcoming' and never transitioned, so it
displayed as "Upcoming" while the tournament is actually ongoing. Flip it to
'active' so it shows as "Ongoing". Targeted by external_id so no match/result
data is touched.

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-06-27 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "UPDATE tournaments SET status = 'active' "
        "WHERE external_id = 1 AND status = 'upcoming'"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE tournaments SET status = 'upcoming' "
        "WHERE external_id = 1 AND status = 'active'"
    )
