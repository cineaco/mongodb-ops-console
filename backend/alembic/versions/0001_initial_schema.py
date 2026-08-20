"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-04-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- roles ---
    op.create_table(
        "roles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_roles_name"),
    )

    # --- users ---
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("username", sa.Text(), nullable=False),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.Column("disabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("last_login_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username", name="uq_users_username"),
        sa.UniqueConstraint("email", name="uq_users_email"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], name="fk_users_role_id"),
    )

    # --- refresh_tokens ---
    op.create_table(
        "refresh_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("expires_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("revoked_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_refresh_tokens_user_id",
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])
    op.create_index("ix_refresh_tokens_token_hash", "refresh_tokens", ["token_hash"])

    # --- secrets ---
    op.create_table(
        "secrets",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column("nonce", sa.LargeBinary(), nullable=False),
        sa.Column("auth_tag", sa.LargeBinary(), nullable=False),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", "type", name="uq_secrets_name_type"),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name="fk_secrets_created_by"
        ),
    )

    # --- clusters ---
    op.create_table(
        "clusters",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("topology", sa.Text(), nullable=False),
        sa.Column("mongodb_version", sa.Text(), nullable=False),
        sa.Column("mongodb_port", sa.Integer(), nullable=False, server_default=sa.text("37017")),
        sa.Column("replicaset_name", sa.Text(), nullable=False, server_default=sa.text("'rs0'")),
        sa.Column(
            "config",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'pending'")),
        sa.Column(
            "admin_credentials_secret_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column("last_deployed_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("last_deployed_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_clusters_name"),
        sa.ForeignKeyConstraint(
            ["admin_credentials_secret_id"],
            ["secrets.id"],
            name="fk_clusters_admin_credentials_secret_id",
        ),
        sa.ForeignKeyConstraint(
            ["last_deployed_by"],
            ["users.id"],
            name="fk_clusters_last_deployed_by",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name="fk_clusters_created_by"
        ),
    )

    # --- cluster_hosts ---
    op.create_table(
        "cluster_hosts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("cluster_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("hostname", sa.Text(), nullable=False),
        sa.Column("ip_address", postgresql.INET(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("ssh_user", sa.Text(), nullable=False, server_default=sa.text("'ubuntu'")),
        sa.Column("ssh_port", sa.Integer(), nullable=False, server_default=sa.text("22")),
        sa.Column("ssh_key_secret_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cluster_id", "hostname", name="uq_cluster_hosts_cluster_hostname"),
        sa.ForeignKeyConstraint(
            ["cluster_id"],
            ["clusters.id"],
            name="fk_cluster_hosts_cluster_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["ssh_key_secret_id"],
            ["secrets.id"],
            name="fk_cluster_hosts_ssh_key_secret_id",
        ),
    )

    # --- audit_logs ---
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("username", sa.Text(), nullable=True),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("resource_type", sa.Text(), nullable=True),
        sa.Column("resource_id", sa.Text(), nullable=True),
        sa.Column("ip_address", postgresql.INET(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column(
            "occurred_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_audit_logs_user_id_occurred_at", "audit_logs", ["user_id", "occurred_at"]
    )
    op.create_index(
        "ix_audit_logs_resource_type_resource_id_occurred_at",
        "audit_logs",
        ["resource_type", "resource_id", "occurred_at"],
    )
    op.create_index("ix_audit_logs_occurred_at", "audit_logs", ["occurred_at"])


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("cluster_hosts")
    op.drop_table("clusters")
    op.drop_table("secrets")
    op.drop_table("refresh_tokens")
    op.drop_table("users")
    op.drop_table("roles")
