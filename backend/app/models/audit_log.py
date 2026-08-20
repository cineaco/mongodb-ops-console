import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_user_id_occurred_at", "user_id", "occurred_at"),
        Index(
            "ix_audit_logs_resource_type_resource_id_occurred_at",
            "resource_type",
            "resource_id",
            "occurred_at",
        ),
        Index("ix_audit_logs_occurred_at", "occurred_at"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    username: Mapped[str | None] = mapped_column(Text, nullable=True)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    resource_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    resource_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )
