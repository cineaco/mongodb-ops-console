"""seed roles

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    roles_table = sa.table(
        "roles",
        sa.column("name", sa.Text),
        sa.column("description", sa.Text),
    )
    op.bulk_insert(
        roles_table,
        [
            {"name": "admin", "description": "Full access to all resources"},
            {"name": "operator", "description": "Deploy and manage clusters"},
            {"name": "viewer", "description": "Read-only access"},
        ],
    )


def downgrade() -> None:
    op.execute("DELETE FROM roles WHERE name IN ('admin', 'operator', 'viewer')")
