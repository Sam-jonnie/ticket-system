"""add sla warning and escalated notification types

Revision ID: 9ba774b01eac
Revises: 64c0e3c7e4a2
Create Date: 2026-10-13 13:20:51.485557

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9ba774b01eac'
down_revision: Union[str, None] = '64c0e3c7e4a2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ALTER TYPE ... ADD VALUE must run outside a transaction block
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE notification_type ADD VALUE IF NOT EXISTS 'sla_warning'")
        op.execute("ALTER TYPE notification_type ADD VALUE IF NOT EXISTS 'sla_escalated'")


def downgrade() -> None:
    # Postgres can't drop a single enum value; leaving them in place is harmless.
    pass