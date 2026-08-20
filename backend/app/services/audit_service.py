import uuid
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.audit_log import AuditLog


async def record(
    db: AsyncSession,
    *,
    action: str,
    user_id: uuid.UUID | None = None,
    username: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> AuditLog:
    entry = AuditLog(
        user_id=user_id,
        username=username,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id else None,
        ip_address=ip_address,
        user_agent=user_agent,
        occurred_at=datetime.now(timezone.utc),
    )
    db.add(entry)
    await db.flush()
    return entry


async def list_logs(
    db: AsyncSession,
    *,
    limit: int = 50,
    cursor: int | None = None,
    user_id: uuid.UUID | None = None,
    action: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
) -> list[AuditLog]:
    query = select(AuditLog).order_by(AuditLog.id.desc()).limit(limit)
    if cursor:
        query = query.where(AuditLog.id < cursor)
    if user_id:
        query = query.where(AuditLog.user_id == user_id)
    if action:
        query = query.where(AuditLog.action == action)
    if resource_type:
        query = query.where(AuditLog.resource_type == resource_type)
    if resource_id:
        query = query.where(AuditLog.resource_id == resource_id)
    result = await db.execute(query)
    return list(result.scalars().all())
