import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class ClusterHost(Base):
    __tablename__ = "cluster_hosts"
    __table_args__ = (
        UniqueConstraint("cluster_id", "hostname", name="uq_cluster_hosts_cluster_hostname"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    cluster_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("clusters.id", ondelete="CASCADE"),
        nullable=False,
    )
    hostname: Mapped[str] = mapped_column(Text, nullable=False)
    ip_address: Mapped[str] = mapped_column(String(45), nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    ssh_user: Mapped[str] = mapped_column(Text, nullable=False, default="ubuntu")
    ssh_port: Mapped[int] = mapped_column(Integer, nullable=False, default=22)
    ssh_key_secret_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("secrets.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )

    cluster: Mapped["Cluster"] = relationship("Cluster", back_populates="hosts")  # noqa: F821
