import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.secret import SecretCreate, SecretResponse
from app.core.database import get_db
from app.core.dependencies import require_role
from app.models.user import User
from app.services import audit_service, secret_service

router = APIRouter(prefix="/api/secrets", tags=["secrets"])


@router.get("", response_model=list[SecretResponse])
async def list_secrets(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role("operator"))],
):
    secrets = await secret_service.list_secrets(db)
    return [
        SecretResponse(
            id=str(s.id),
            name=s.name,
            type=s.type,
            created_at=s.created_at,
            created_by=str(s.created_by),
        )
        for s in secrets
    ]


@router.post("", response_model=SecretResponse, status_code=201)
async def create_secret(
    body: SecretCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role("operator"))],
):
    secret = await secret_service.create_secret(
        db,
        name=body.name,
        type=body.type,
        plaintext=body.plaintext,
        created_by=current_user.id,
    )
    await audit_service.record(
        db,
        action="create",
        user_id=current_user.id,
        username=current_user.username,
        resource_type="secret",
        resource_id=str(secret.id),
    )
    await db.commit()
    return SecretResponse(
        id=str(secret.id),
        name=secret.name,
        type=secret.type,
        created_at=secret.created_at,
        created_by=str(secret.created_by),
    )


@router.delete("/{secret_id}", status_code=204)
async def delete_secret(
    secret_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role("operator"))],
):
    secret = await secret_service.get_secret(db, secret_id)
    if secret is None:
        raise HTTPException(status_code=404, detail="Secret not found")
    await secret_service.delete_secret(db, secret)
    await audit_service.record(
        db,
        action="delete",
        user_id=current_user.id,
        username=current_user.username,
        resource_type="secret",
        resource_id=str(secret_id),
    )
    await db.commit()
