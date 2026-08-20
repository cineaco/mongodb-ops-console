import uuid
from datetime import datetime

from sqlalchemy import Float, ForeignKey, Index, Text, func
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ClusterAlert(Base):
    __tablename__ = "cluster_alerts"
    __table_args__ = (
        Index("ix_cluster_alerts_cluster_id_status", "cluster_id", "status"),
        Index("ix_cluster_alerts_status_last_triggered_at", "status", "last_triggered_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    cluster_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clusters.id", ondelete="CASCADE"), nullable=False
    )
    metric: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(Text, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    threshold_value: Mapped[float] = mapped_column(Float, nullable=False)
    actual_value: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="active")
    first_triggered_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )
    last_triggered_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    notified_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    created_by: Mapped[str] = mapped_column(Text, nullable=False, default="poller")
