import uuid
from datetime import datetime

from sqlalchemy import JSON, ForeignKey, Integer, Text, func
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Cluster(Base):
    __tablename__ = "clusters"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    topology: Mapped[str] = mapped_column(Text, nullable=False)
    mongodb_version: Mapped[str] = mapped_column(Text, nullable=False)
    mongodb_port: Mapped[int] = mapped_column(Integer, nullable=False, default=37017)
    replicaset_name: Mapped[str] = mapped_column(
        Text, nullable=False, default="rs0"
    )
    config: Mapped[dict] = mapped_column(JSON, nullable=False, server_default="{}")
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    admin_credentials_secret_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("secrets.id"), nullable=True
    )
    last_deployed_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    last_deployed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    hosts: Mapped[list["ClusterHost"]] = relationship(  # noqa: F821
        "ClusterHost", back_populates="cluster", cascade="all, delete-orphan"
    )
