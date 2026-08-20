"""add metrics and alerts tables

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "cluster_metrics",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column(
            "cluster_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("clusters.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "collected_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        # RS health
        sa.Column("rs_state", sa.Text(), nullable=False),
        sa.Column("primary_member", sa.Text(), nullable=True),
        sa.Column("members_up", sa.Integer(), nullable=False),
        sa.Column("members_total", sa.Integer(), nullable=False),
        sa.Column("max_replication_lag_seconds", sa.Float(), nullable=True),
        # Server perf
        sa.Column("connections_current", sa.Integer(), nullable=True),
        sa.Column("connections_available", sa.Integer(), nullable=True),
        sa.Column("ops_insert", sa.Integer(), nullable=True),
        sa.Column("ops_query", sa.Integer(), nullable=True),
        sa.Column("ops_update", sa.Integer(), nullable=True),
        sa.Column("ops_delete", sa.Integer(), nullable=True),
        sa.Column("memory_resident_mb", sa.Integer(), nullable=True),
        sa.Column("memory_virtual_mb", sa.Integer(), nullable=True),
        # Cache (WiredTiger)
        sa.Column("wt_cache_used_bytes", sa.BigInteger(), nullable=True),
        sa.Column("wt_cache_total_bytes", sa.BigInteger(), nullable=True),
        sa.Column("wt_cache_dirty_bytes", sa.BigInteger(), nullable=True),
        # Storage
        sa.Column("data_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("storage_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("index_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("fs_total_bytes", sa.BigInteger(), nullable=True),
        sa.Column("fs_used_bytes", sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_cluster_metrics_cluster_id_collected_at",
        "cluster_metrics",
        ["cluster_id", "collected_at"],
    )

    op.create_table(
        "cluster_alerts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "cluster_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("clusters.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("metric", sa.Text(), nullable=False),
        sa.Column("severity", sa.Text(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("threshold_value", sa.Float(), nullable=False),
        sa.Column("actual_value", sa.Float(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="active"),
        sa.Column(
            "first_triggered_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "last_triggered_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("resolved_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("notified_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_by", sa.Text(), nullable=False, server_default="poller"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_cluster_alerts_cluster_id_status",
        "cluster_alerts",
        ["cluster_id", "status"],
    )
    op.create_index(
        "ix_cluster_alerts_status_last_triggered_at",
        "cluster_alerts",
        ["status", "last_triggered_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_cluster_alerts_status_last_triggered_at", table_name="cluster_alerts")
    op.drop_index("ix_cluster_alerts_cluster_id_status", table_name="cluster_alerts")
    op.drop_table("cluster_alerts")
    op.drop_index("ix_cluster_metrics_cluster_id_collected_at", table_name="cluster_metrics")
    op.drop_table("cluster_metrics")
