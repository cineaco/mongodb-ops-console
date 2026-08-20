"""Monitor service: collect MongoDB metrics via PyMongo and check alert thresholds."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from pymongo import MongoClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.core.config import settings
from app.core.crypto import decrypt
from app.models.cluster import Cluster
from app.models.cluster_alert import ClusterAlert
from app.models.cluster_host import ClusterHost
from app.models.cluster_metric import ClusterMetric
from app.models.secret import Secret
from app.services import alert_service

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 1. Synchronous metric collection (runs in threadpool)
# ---------------------------------------------------------------------------


def _collect_metrics_sync(uri: str, timeout_ms: int) -> dict[str, Any]:
    """Connect to MongoDB, run diagnostic commands, return flat metric dict."""
    client = MongoClient(uri, serverSelectionTimeoutMS=timeout_ms, connectTimeoutMS=timeout_ms)
    try:
        admin = client.admin

        rs_status = admin.command("replSetGetStatus")
        server_status = admin.command("serverStatus")
        db_stats = admin.command("dbStats", 1, freeStorage=1)

        # --- RS health ---
        members = rs_status.get("members", [])
        members_total = len(members)
        members_up = sum(1 for m in members if m.get("health", 0) == 1)
        primary_member: str | None = None
        primary_optime = None
        max_lag: float | None = None

        for m in members:
            if m.get("stateStr") == "PRIMARY":
                primary_member = m.get("name")
                primary_optime = m.get("optimeDate")

        if primary_optime is not None:
            lags = []
            for m in members:
                if m.get("stateStr") != "PRIMARY" and m.get("health", 0) == 1:
                    sec_optime = m.get("optimeDate")
                    if sec_optime is not None:
                        lag = (primary_optime - sec_optime).total_seconds()
                        lags.append(abs(lag))
            max_lag = max(lags) if lags else 0.0

        my_state = rs_status.get("myState", -1)
        if my_state == 1:
            rs_state = "ok"
        elif my_state in (2, 3, 5):
            rs_state = "ok"
        else:
            rs_state = "degraded"

        if members_up < members_total:
            rs_state = "degraded"

        if primary_member is None:
            rs_state = "no_primary"

        # --- Server perf ---
        conns = server_status.get("connections", {})
        opcounters = server_status.get("opcounters", {})
        mem = server_status.get("mem", {})

        # --- WiredTiger cache ---
        wt = server_status.get("wiredTiger", {}).get("cache", {})
        wt_cache_used = wt.get("bytes currently in the cache")
        wt_cache_total = wt.get("maximum bytes configured")
        wt_cache_dirty = wt.get("tracked dirty bytes in the cache")

        # --- Storage / FS ---
        fs_total = db_stats.get("fsTotalSize")
        fs_used = db_stats.get("fsUsedSize")

        return {
            "rs_state": rs_state,
            "primary_member": primary_member,
            "members_up": members_up,
            "members_total": members_total,
            "max_replication_lag_seconds": max_lag,
            "connections_current": conns.get("current"),
            "connections_available": conns.get("available"),
            "ops_insert": opcounters.get("insert"),
            "ops_query": opcounters.get("query"),
            "ops_update": opcounters.get("update"),
            "ops_delete": opcounters.get("delete"),
            "memory_resident_mb": mem.get("resident"),
            "memory_virtual_mb": mem.get("virtual"),
            "wt_cache_used_bytes": wt_cache_used,
            "wt_cache_total_bytes": wt_cache_total,
            "wt_cache_dirty_bytes": wt_cache_dirty,
            "data_size_bytes": db_stats.get("dataSize"),
            "storage_size_bytes": db_stats.get("storageSize"),
            "index_size_bytes": db_stats.get("indexSize"),
            "fs_total_bytes": fs_total,
            "fs_used_bytes": fs_used,
        }
    finally:
        client.close()


# ---------------------------------------------------------------------------
# 2. Async metric collection
# ---------------------------------------------------------------------------


async def collect_cluster_metrics(
    db: AsyncSession, cluster: Cluster
) -> ClusterMetric | None:
    """Collect metrics from a cluster's primary host and store them."""
    # Look up admin credentials
    if not cluster.admin_credentials_secret_id:
        logger.warning("Cluster %s has no admin credentials secret", cluster.name)
        return None

    result = await db.execute(
        select(Secret).where(Secret.id == cluster.admin_credentials_secret_id)
    )
    secret = result.scalar_one_or_none()
    if not secret:
        logger.warning("Admin credentials secret not found for cluster %s", cluster.name)
        return None

    password = decrypt(secret.ciphertext, secret.nonce, secret.auth_tag).decode()

    # Find the primary host
    result = await db.execute(
        select(ClusterHost).where(
            ClusterHost.cluster_id == cluster.id,
            ClusterHost.role == "primary",
        )
    )
    host = result.scalar_one_or_none()
    if not host:
        logger.warning("No primary host found for cluster %s", cluster.name)
        return None

    username = secret.name
    uri = f"mongodb://{username}:{password}@{host.ip_address}:{cluster.mongodb_port}/?authSource=admin"
    timeout_ms = settings.POLLER_TIMEOUT_SECONDS * 1000

    try:
        data = await run_in_threadpool(_collect_metrics_sync, uri, timeout_ms)
    except Exception as exc:
        logger.error("Failed to collect metrics from cluster %s: %s", cluster.name, exc)
        data = {
            "rs_state": "error",
            "primary_member": None,
            "members_up": 0,
            "members_total": 0,
            "max_replication_lag_seconds": None,
        }

    metric = ClusterMetric(cluster_id=cluster.id, **data)
    db.add(metric)
    await db.flush()
    return metric


# ---------------------------------------------------------------------------
# 3. Threshold helpers
# ---------------------------------------------------------------------------


def get_effective_thresholds(cluster: Cluster) -> dict[str, Any]:
    """Merge global defaults from settings with per-cluster overrides."""
    defaults = {
        "replication_lag_warning": settings.ALERT_REPLICATION_LAG_WARNING,
        "replication_lag_critical": settings.ALERT_REPLICATION_LAG_CRITICAL,
        "connections_warning": settings.ALERT_CONNECTIONS_WARNING,
        "connections_critical": settings.ALERT_CONNECTIONS_CRITICAL,
        "disk_usage_warning": settings.ALERT_DISK_USAGE_WARNING,
        "disk_usage_critical": settings.ALERT_DISK_USAGE_CRITICAL,
        "memory_warning": settings.ALERT_MEMORY_WARNING,
        "memory_critical": settings.ALERT_MEMORY_CRITICAL,
        "cache_dirty_warning": settings.ALERT_CACHE_DIRTY_WARNING,
        "member_down_critical": settings.ALERT_MEMBER_DOWN_CRITICAL,
    }
    overrides = (cluster.config or {}).get("alert_thresholds", {})
    defaults.update(overrides)
    return defaults


# ---------------------------------------------------------------------------
# 4. Threshold checking and alerting
# ---------------------------------------------------------------------------


async def check_thresholds_and_alert(
    db: AsyncSession, cluster: Cluster, metric: ClusterMetric
) -> None:
    """Check 6 metrics against thresholds and create/resolve alerts."""
    t = get_effective_thresholds(cluster)

    # --- Replication lag ---
    if metric.max_replication_lag_seconds is not None:
        lag = metric.max_replication_lag_seconds
        if lag >= t["replication_lag_critical"]:
            alert, is_new = await alert_service.create_or_update_alert(
                db, cluster_id=cluster.id, metric="replication_lag",
                severity="critical",
                message=f"Replication lag {lag:.1f}s exceeds critical threshold {t['replication_lag_critical']}s",
                threshold_value=t["replication_lag_critical"], actual_value=lag,
            )
            if is_new:
                await alert_service.send_slack_notification(db, alert, cluster)
        elif lag >= t["replication_lag_warning"]:
            alert, is_new = await alert_service.create_or_update_alert(
                db, cluster_id=cluster.id, metric="replication_lag",
                severity="warning",
                message=f"Replication lag {lag:.1f}s exceeds warning threshold {t['replication_lag_warning']}s",
                threshold_value=t["replication_lag_warning"], actual_value=lag,
            )
            if is_new:
                await alert_service.send_slack_notification(db, alert, cluster)
        else:
            await alert_service.resolve_alert(db, cluster.id, "replication_lag")

    # --- Connections ---
    if metric.connections_current is not None:
        conns = metric.connections_current
        if conns >= t["connections_critical"]:
            alert, is_new = await alert_service.create_or_update_alert(
                db, cluster_id=cluster.id, metric="connections",
                severity="critical",
                message=f"Connections {conns} exceeds critical threshold {t['connections_critical']}",
                threshold_value=float(t["connections_critical"]), actual_value=float(conns),
            )
            if is_new:
                await alert_service.send_slack_notification(db, alert, cluster)
        elif conns >= t["connections_warning"]:
            alert, is_new = await alert_service.create_or_update_alert(
                db, cluster_id=cluster.id, metric="connections",
                severity="warning",
                message=f"Connections {conns} exceeds warning threshold {t['connections_warning']}",
                threshold_value=float(t["connections_warning"]), actual_value=float(conns),
            )
            if is_new:
                await alert_service.send_slack_notification(db, alert, cluster)
        else:
            await alert_service.resolve_alert(db, cluster.id, "connections")

    # --- Disk usage ---
    if metric.fs_used_bytes is not None and metric.fs_total_bytes:
        disk_pct = (metric.fs_used_bytes / metric.fs_total_bytes) * 100
        if disk_pct >= t["disk_usage_critical"]:
            alert, is_new = await alert_service.create_or_update_alert(
                db, cluster_id=cluster.id, metric="disk_usage",
                severity="critical",
                message=f"Disk usage {disk_pct:.1f}% exceeds critical threshold {t['disk_usage_critical']}%",
                threshold_value=float(t["disk_usage_critical"]), actual_value=disk_pct,
            )
            if is_new:
                await alert_service.send_slack_notification(db, alert, cluster)
        elif disk_pct >= t["disk_usage_warning"]:
            alert, is_new = await alert_service.create_or_update_alert(
                db, cluster_id=cluster.id, metric="disk_usage",
                severity="warning",
                message=f"Disk usage {disk_pct:.1f}% exceeds warning threshold {t['disk_usage_warning']}%",
                threshold_value=float(t["disk_usage_warning"]), actual_value=disk_pct,
            )
            if is_new:
                await alert_service.send_slack_notification(db, alert, cluster)
        else:
            await alert_service.resolve_alert(db, cluster.id, "disk_usage")

    # --- Memory usage ---
    if metric.memory_resident_mb is not None and metric.memory_virtual_mb:
        mem_pct = (metric.memory_resident_mb / metric.memory_virtual_mb) * 100
        if mem_pct >= t["memory_critical"]:
            alert, is_new = await alert_service.create_or_update_alert(
                db, cluster_id=cluster.id, metric="memory_usage",
                severity="critical",
                message=f"Memory usage {mem_pct:.1f}% exceeds critical threshold {t['memory_critical']}%",
                threshold_value=float(t["memory_critical"]), actual_value=mem_pct,
            )
            if is_new:
                await alert_service.send_slack_notification(db, alert, cluster)
        elif mem_pct >= t["memory_warning"]:
            alert, is_new = await alert_service.create_or_update_alert(
                db, cluster_id=cluster.id, metric="memory_usage",
                severity="warning",
                message=f"Memory usage {mem_pct:.1f}% exceeds warning threshold {t['memory_warning']}%",
                threshold_value=float(t["memory_warning"]), actual_value=mem_pct,
            )
            if is_new:
                await alert_service.send_slack_notification(db, alert, cluster)
        else:
            await alert_service.resolve_alert(db, cluster.id, "memory_usage")

    # --- Cache pressure (dirty) ---
    if metric.wt_cache_dirty_bytes is not None and metric.wt_cache_total_bytes:
        cache_pct = (metric.wt_cache_dirty_bytes / metric.wt_cache_total_bytes) * 100
        if cache_pct >= t["cache_dirty_warning"]:
            alert, is_new = await alert_service.create_or_update_alert(
                db, cluster_id=cluster.id, metric="cache_pressure",
                severity="warning",
                message=f"Cache dirty {cache_pct:.1f}% exceeds warning threshold {t['cache_dirty_warning']}%",
                threshold_value=float(t["cache_dirty_warning"]), actual_value=cache_pct,
            )
            if is_new:
                await alert_service.send_slack_notification(db, alert, cluster)
        else:
            await alert_service.resolve_alert(db, cluster.id, "cache_pressure")

    # --- Member down ---
    if metric.members_total > 0 and metric.members_up < metric.members_total:
        down_count = metric.members_total - metric.members_up
        alert, is_new = await alert_service.create_or_update_alert(
            db, cluster_id=cluster.id, metric="member_down",
            severity="critical",
            message=f"{down_count} member(s) down out of {metric.members_total}",
            threshold_value=float(t["member_down_critical"]),
            actual_value=float(down_count),
        )
        if is_new:
            await alert_service.send_slack_notification(db, alert, cluster)
    else:
        await alert_service.resolve_alert(db, cluster.id, "member_down")


# ---------------------------------------------------------------------------
# 5. Cluster status update
# ---------------------------------------------------------------------------


async def update_cluster_status(
    db: AsyncSession, cluster: Cluster, metric: ClusterMetric
) -> None:
    """Update cluster.status based on rs_state and active alerts."""
    if metric.rs_state in ("error", "no_primary"):
        cluster.status = "failed"
    elif metric.rs_state == "degraded":
        cluster.status = "degraded"
    else:
        # rs_state is "ok" — check active alerts
        active_alerts = await alert_service.list_alerts(
            db, cluster_id=cluster.id, status="active"
        )
        has_critical = any(a.severity == "critical" for a in active_alerts)
        has_warning = any(a.severity == "warning" for a in active_alerts)

        if has_critical or has_warning:
            cluster.status = "degraded"
        else:
            cluster.status = "healthy"

    await db.flush()
