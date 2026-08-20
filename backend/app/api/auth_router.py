from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    TokenResponse,
    UserMeResponse,
)
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.role import Role
from app.models.user import User
from app.services import audit_service
from app.services import auth_service

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    user = await auth_service.authenticate(db, body.username, body.password)
    if user is None:
        await audit_service.record(
            db,
            action="login_failed",
            username=body.username,
        )
        await db.commit()
        raise HTTPException(status_code=401, detail="Invalid credentials")

    tokens = await auth_service.create_tokens(db, user)
    await audit_service.record(
        db,
        action="login",
        user_id=user.id,
        username=user.username,
    )
    await db.commit()
    return tokens


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    body: RefreshRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    tokens = await auth_service.refresh_tokens(db, body.refresh_token)
    if tokens is None:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
    await db.commit()
    return tokens


@router.post("/logout")
async def logout(
    body: RefreshRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    await auth_service.revoke_refresh_token(db, body.refresh_token)
    await audit_service.record(
        db,
        action="logout",
        user_id=current_user.id,
        username=current_user.username,
    )
    await db.commit()
    return {"detail": "Logged out"}


@router.get("/me", response_model=UserMeResponse)
async def me(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    result = await db.execute(select(Role).where(Role.id == current_user.role_id))
    role = result.scalar_one()
    return UserMeResponse(
        id=str(current_user.id),
        username=current_user.username,
        email=current_user.email,
        role=role.name,
        disabled=current_user.disabled,
    )
