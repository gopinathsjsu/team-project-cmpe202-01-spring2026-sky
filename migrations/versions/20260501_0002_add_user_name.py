"""add user name

Revision ID: 0002_add_user_name
Revises: 0001_add_event_rejection_reason
Create Date: 2026-05-01

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0002_add_user_name"
down_revision: Union[str, None] = "0001_add_event_rejection_reason"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS name VARCHAR")


def downgrade() -> None:
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS name")
