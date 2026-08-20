"""add jobs table

Revision ID: 0004
Revises: 0003
Create Date: 2026-04-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("cluster_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clusters.id", ondelete="CASCADE"), nullable=False),
        sa.Column("operation", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("params", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
    )
    op.create_index("ix_jobs_cluster_created", "jobs", ["cluster_id", "created_at"])
    op.create_index("ix_jobs_status_pending", "jobs", ["status"])


def downgrade() -> None:
    op.drop_index("ix_jobs_status_pending", table_name="jobs")
    op.drop_index("ix_jobs_cluster_created", table_name="jobs")
    op.drop_table("jobs")
