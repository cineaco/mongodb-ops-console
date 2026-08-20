import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.user import UserCreate, UserResponse, UserUpdate
from app.core.database import get_db
from app.core.dependencies import require_role
from app.models.role import Role
from app.models.user import User
from app.services import audit_service, user_service

router = APIRouter(prefix="/api/users", tags=["users"])

_admin_required = require_role("admin")


async def _user_to_response(db: AsyncSession, user: User) -> UserResponse:
    result = await db.execute(select(Role).where(Role.id == user.role_id))
    role = result.scalar_one()
    return UserResponse(
        id=str(user.id),
        username=user.username,
        email=user.email,
        role=role.name,
        disabled=user.disabled,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
    )


@router.get("", response_model=list[UserResponse])
async def list_users(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(_admin_required)],
):
    users = await user_service.list_users(db)
    return [await _user_to_response(db, u) for u in users]


@router.post("", response_model=UserResponse, status_code=201)
async def create_user(
    body: UserCreate,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(_admin_required)],
):
    user = await user_service.create_user(
        db,
        username=body.username,
        password=body.password,
        email=body.email,
        role_name=body.role,
    )
    await audit_service.record(
        db,
        action="create",
        user_id=current_user.id,
        username=current_user.username,
        resource_type="user",
        resource_id=str(user.id),
    )
    await db.commit()
    return await _user_to_response(db, user)


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(_admin_required)],
):
    user = await user_service.get_user(db, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return await _user_to_response(db, user)


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: uuid.UUID,
    body: UserUpdate,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(_admin_required)],
):
    user = await user_service.get_user(db, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    user = await user_service.update_user(
        db,
        user,
        role_name=body.role,
        disabled=body.disabled,
        password=body.password,
    )
    await audit_service.record(
        db,
        action="update",
        user_id=current_user.id,
        username=current_user.username,
        resource_type="user",
        resource_id=str(user.id),
    )
    await db.commit()
    return await _user_to_response(db, user)


@router.delete("/{user_id}", status_code=204)
async def delete_user(
    user_id: uuid.UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(_admin_required)],
):
    user = await user_service.get_user(db, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    await audit_service.record(
        db,
        action="delete",
        user_id=current_user.id,
        username=current_user.username,
        resource_type="user",
        resource_id=str(user.id),
    )
    await user_service.delete_user(db, user)
    await db.commit()
    return None
