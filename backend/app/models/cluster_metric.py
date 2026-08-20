import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Float, ForeignKey, Index, Integer, Text, func
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ClusterMetric(Base):
    __tablename__ = "cluster_metrics"
    __table_args__ = (
        Index("ix_cluster_metrics_cluster_id_collected_at", "cluster_id", "collected_at"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    cluster_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clusters.id", ondelete="CASCADE"), nullable=False
    )
    collected_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )

    # RS health
    rs_state: Mapped[str] = mapped_column(Text, nullable=False)
    primary_member: Mapped[str | None] = mapped_column(Text, nullable=True)
    members_up: Mapped[int] = mapped_column(Integer, nullable=False)
    members_total: Mapped[int] = mapped_column(Integer, nullable=False)
    max_replication_lag_seconds: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )

    # Server perf
    connections_current: Mapped[int | None] = mapped_column(Integer, nullable=True)
    connections_available: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ops_insert: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ops_query: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ops_update: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ops_delete: Mapped[int | None] = mapped_column(Integer, nullable=True)
    memory_resident_mb: Mapped[int | None] = mapped_column(Integer, nullable=True)
    memory_virtual_mb: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Cache (WiredTiger)
    wt_cache_used_bytes: Mapped[int | None] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), nullable=True
    )
    wt_cache_total_bytes: Mapped[int | None] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), nullable=True
    )
    wt_cache_dirty_bytes: Mapped[int | None] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), nullable=True
    )

    # Storage
    data_size_bytes: Mapped[int | None] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), nullable=True
    )
    storage_size_bytes: Mapped[int | None] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), nullable=True
    )
    index_size_bytes: Mapped[int | None] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), nullable=True
    )
    fs_total_bytes: Mapped[int | None] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), nullable=True
    )
    fs_used_bytes: Mapped[int | None] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), nullable=True
    )
