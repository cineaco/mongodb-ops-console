import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.audit import AuditLogResponse
from app.core.database import get_db
from app.core.dependencies import require_role
from app.models.user import User
from app.services import audit_service

router = APIRouter(prefix="/api/audit-logs", tags=["audit-logs"])

_viewer_required = require_role("viewer")


@router.get("", response_model=list[AuditLogResponse])
async def list_audit_logs(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(_viewer_required)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    cursor: int | None = None,
    user_id: uuid.UUID | None = None,
    action: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
):
    logs = await audit_service.list_logs(
        db,
        limit=limit,
        cursor=cursor,
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
    )
    return [
        AuditLogResponse(
            id=log.id,
            user_id=str(log.user_id) if log.user_id else None,
            username=log.username,
            action=log.action,
            resource_type=log.resource_type,
            resource_id=log.resource_id,
            ip_address=str(log.ip_address) if log.ip_address else None,
            user_agent=log.user_agent,
            occurred_at=log.occurred_at,
        )
        for log in logs
    ]
