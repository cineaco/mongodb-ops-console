import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, LargeBinary, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Secret(Base):
    __tablename__ = "secrets"
    __table_args__ = (UniqueConstraint("name", "type", name="uq_secrets_name_type"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[str] = mapped_column(Text, nullable=False)
    ciphertext: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    nonce: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    auth_tag: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
