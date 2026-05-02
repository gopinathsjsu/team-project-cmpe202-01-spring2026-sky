"""add event rejection reason

Revision ID: 0001_add_event_rejection_reason
Revises:
Create Date: 2026-05-01

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0001_add_event_rejection_reason"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE events ADD COLUMN IF NOT EXISTS rejection_reason TEXT")


def downgrade() -> None:
    op.execute("ALTER TABLE events DROP COLUMN IF EXISTS rejection_reason")
