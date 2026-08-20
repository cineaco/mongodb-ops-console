import uuid
from typing import Annotated
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.user import User
from app.models.role import Role

_bearer = HTTPBearer()

ROLE_HIERARCHY = {"admin": 3, "operator": 2, "viewer": 1}


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    try:
        payload = decode_access_token(credentials.credentials)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid token type")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()

    if not user or user.disabled:
        raise HTTPException(status_code=401, detail="User not found or disabled")

    return user


def require_role(minimum_role: str):
    min_level = ROLE_HIERARCHY[minimum_role]

    async def dependency(
        user: Annotated[User, Depends(get_current_user)],
        db: Annotated[AsyncSession, Depends(get_db)],
    ) -> User:
        result = await db.execute(select(Role).where(Role.id == user.role_id))
        role = result.scalar_one()
        user_level = ROLE_HIERARCHY.get(role.name, 0)
        if user_level < min_level:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        user._role_name = role.name
        return user

    return dependency
