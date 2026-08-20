import uuid
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Integer, Text, func
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    username: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    email: Mapped[str | None] = mapped_column(Text, unique=True, nullable=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("roles.id"), nullable=False
    )
    disabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )

    role: Mapped["Role"] = relationship("Role", back_populates="users")  # noqa: F821
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(  # noqa: F821
        "RefreshToken", back_populates="user"
    )
