import uuid
from datetime import datetime, timezone

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.cluster import Cluster
from app.models.cluster_alert import ClusterAlert


async def get_active_alert(
    db: AsyncSession, cluster_id: uuid.UUID, metric: str
) -> ClusterAlert | None:
    result = await db.execute(
        select(ClusterAlert).where(
            ClusterAlert.cluster_id == cluster_id,
            ClusterAlert.metric == metric,
            ClusterAlert.status == "active",
        )
    )
    return result.scalar_one_or_none()


async def create_or_update_alert(
    db: AsyncSession,
    *,
    cluster_id: uuid.UUID,
    metric: str,
    severity: str,
    message: str,
    threshold_value: float,
    actual_value: float,
) -> tuple[ClusterAlert, bool]:
    existing = await get_active_alert(db, cluster_id, metric)
    if existing:
        existing.last_triggered_at = datetime.now(timezone.utc)
        existing.actual_value = actual_value
        existing.severity = severity
        existing.message = message
        await db.flush()
        return existing, False

    alert = ClusterAlert(
        cluster_id=cluster_id,
        metric=metric,
        severity=severity,
        message=message,
        threshold_value=threshold_value,
        actual_value=actual_value,
        status="active",
    )
    db.add(alert)
    await db.flush()
    return alert, True


async def resolve_alert(
    db: AsyncSession, cluster_id: uuid.UUID, metric: str
) -> bool:
    alert = await get_active_alert(db, cluster_id, metric)
    if not alert:
        return False
    alert.status = "resolved"
    alert.resolved_at = datetime.now(timezone.utc)
    await db.flush()
    return True


async def resolve_alert_by_id(
    db: AsyncSession, alert_id: uuid.UUID
) -> ClusterAlert | None:
    result = await db.execute(
        select(ClusterAlert).where(ClusterAlert.id == alert_id)
    )
    alert = result.scalar_one_or_none()
    if not alert or alert.status == "resolved":
        return None
    alert.status = "resolved"
    alert.resolved_at = datetime.now(timezone.utc)
    await db.flush()
    return alert


async def list_alerts(
    db: AsyncSession,
    *,
    cluster_id: uuid.UUID | None = None,
    status: str | None = None,
    limit: int = 50,
) -> list[ClusterAlert]:
    stmt = select(ClusterAlert)
    if cluster_id is not None:
        stmt = stmt.where(ClusterAlert.cluster_id == cluster_id)
    if status is not None:
        stmt = stmt.where(ClusterAlert.status == status)
    stmt = stmt.order_by(ClusterAlert.last_triggered_at.desc()).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def count_active_alerts(db: AsyncSession) -> int:
    result = await db.execute(
        select(func.count()).select_from(ClusterAlert).where(
            ClusterAlert.status == "active"
        )
    )
    return result.scalar_one()


def should_notify_slack(alert: ClusterAlert) -> bool:
    if not settings.SLACK_WEBHOOK_URL:
        return False
    if alert.notified_at is None:
        return True
    now = datetime.now(timezone.utc)
    notified = alert.notified_at
    if notified.tzinfo is None:
        notified = notified.replace(tzinfo=timezone.utc)
    elapsed = (now - notified).total_seconds() / 60.0
    return elapsed > settings.ALERT_DEBOUNCE_MINUTES


_SEVERITY_EMOJI = {
    "critical": "\U0001f534",
    "warning": "\U0001f7e0",
    "info": "\U0001f535",
}


async def send_slack_notification(
    db: AsyncSession, alert: ClusterAlert, cluster: Cluster
) -> None:
    if not settings.SLACK_WEBHOOK_URL:
        return

    emoji = _SEVERITY_EMOJI.get(alert.severity, "\u2753")
    text = (
        f"{emoji} {alert.severity}: {alert.metric} on *{cluster.name}*\n"
        f"Value: {alert.actual_value} (threshold: {alert.threshold_value})\n"
        f"Cluster: {cluster.name} | Topology: {cluster.topology} | Version: {cluster.mongodb_version}"
    )

    payload: dict = {"text": text}
    if settings.SLACK_CHANNEL:
        payload["channel"] = settings.SLACK_CHANNEL

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(settings.SLACK_WEBHOOK_URL, json=payload)
        alert.notified_at = datetime.now(timezone.utc)
        await db.flush()
    except Exception:
        pass
