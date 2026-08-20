from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.alert import AlertCountResponse, AlertResponse
from app.core.database import get_db
from app.core.dependencies import require_role
from app.models.cluster_alert import ClusterAlert
from app.models.user import User
from app.services import alert_service, audit_service

router = APIRouter(tags=["alerts"])

_viewer = require_role("viewer")
_operator = require_role("operator")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _alert_to_response(a: ClusterAlert) -> AlertResponse:
    return AlertResponse(
        id=str(a.id),
        cluster_id=str(a.cluster_id),
        metric=a.metric,
        severity=a.severity,
        message=a.message,
        threshold_value=a.threshold_value,
        actual_value=a.actual_value,
        status=a.status,
        first_triggered_at=a.first_triggered_at,
        last_triggered_at=a.last_triggered_at,
        resolved_at=a.resolved_at,
        notified_at=a.notified_at,
        created_by=a.created_by,
    )


# ---------------------------------------------------------------------------
# Per-cluster endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/api/clusters/{cluster_id}/alerts",
    response_model=list[AlertResponse],
)
async def list_cluster_alerts(
    cluster_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(_viewer)],
    status: str | None = Query(None, pattern="^(active|resolved)$"),
):
    alerts = await alert_service.list_alerts(
        db, cluster_id=cluster_id, status=status,
    )
    return [_alert_to_response(a) for a in alerts]


@router.patch(
    "/api/clusters/{cluster_id}/alerts/{alert_id}",
    response_model=AlertResponse,
)
async def resolve_alert(
    cluster_id: uuid.UUID,
    alert_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(_operator)],
):
    # Resolve the alert and verify it belongs to the cluster
    alert = await alert_service.resolve_alert_by_id(db, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found or already resolved")
    if alert.cluster_id != cluster_id:
        raise HTTPException(status_code=404, detail="Alert does not belong to this cluster")

    await audit_service.record(
        db,
        action="resolve_alert",
        user_id=current_user.id,
        username=current_user.username,
        resource_type="alert",
        resource_id=str(alert_id),
    )
    await db.commit()
    return _alert_to_response(alert)


# ---------------------------------------------------------------------------
# Global endpoints
# ---------------------------------------------------------------------------

@router.get("/api/alerts", response_model=list[AlertResponse])
async def list_all_alerts(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(_viewer)],
    status: str | None = Query(None, pattern="^(active|resolved)$"),
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
):
    alerts = await alert_service.list_alerts(db, status=status, limit=limit)
    return [_alert_to_response(a) for a in alerts]


@router.get("/api/alerts/count", response_model=AlertCountResponse)
async def get_active_alert_count(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(_viewer)],
):
    count = await alert_service.count_active_alerts(db)
    return AlertCountResponse(active_count=count)
