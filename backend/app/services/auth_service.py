import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token_value,
    hash_refresh_token,
    verify_password,
)
from app.models.refresh_token import RefreshToken
from app.models.role import Role
from app.models.user import User


async def authenticate(db: AsyncSession, username: str, password: str) -> User | None:
    """Look up user by username and verify password. Updates last_login_at on success."""
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if user is None:
        return None
    if user.disabled:
        return None
    if not await verify_password(user.password_hash, password):
        return None
    user.last_login_at = datetime.now(timezone.utc)
    await db.flush()
    return user


async def create_tokens(db: AsyncSession, user: User) -> dict:
    """Create an access JWT and a refresh token, storing the refresh hash in DB."""
    # Look up role name
    result = await db.execute(select(Role).where(Role.id == user.role_id))
    role = result.scalar_one()

    access_token = create_access_token(str(user.id), role.name)
    raw_refresh = create_refresh_token_value()
    token_hash = hash_refresh_token(raw_refresh)

    refresh_row = RefreshToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.JWT_REFRESH_TTL_DAYS),
    )
    db.add(refresh_row)
    await db.flush()

    return {
        "access_token": access_token,
        "refresh_token": raw_refresh,
        "token_type": "bearer",
    }


async def refresh_tokens(db: AsyncSession, refresh_token: str) -> dict | None:
    """Validate a refresh token, revoke the old one, and create a new token pair."""
    token_hash = hash_refresh_token(refresh_token)
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.revoked_at.is_(None),
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        return None
    if row.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        return None

    # Revoke old token
    row.revoked_at = datetime.now(timezone.utc)
    await db.flush()

    # Load user
    user_result = await db.execute(select(User).where(User.id == row.user_id))
    user = user_result.scalar_one_or_none()
    if user is None or user.disabled:
        return None

    return await create_tokens(db, user)


async def revoke_refresh_token(db: AsyncSession, refresh_token: str) -> bool:
    """Set revoked_at on a refresh token. Returns True if found and revoked."""
    token_hash = hash_refresh_token(refresh_token)
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.revoked_at.is_(None),
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        return False
    row.revoked_at = datetime.now(timezone.utc)
    await db.flush()
    return True
