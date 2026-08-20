from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.metrics import (
    CacheInfo,
    ConnectionsInfo,
    MemoryInfo,
    MetricLatestResponse,
    MetricPointResponse,
    MetricRangeResponse,
    OpsPerSecond,
    StorageInfo,
)
from app.core.database import get_db
from app.core.dependencies import require_role
from app.models.cluster import Cluster
from app.models.cluster_metric import ClusterMetric
from app.models.user import User

router = APIRouter(
    prefix="/api/clusters/{cluster_id}/metrics",
    tags=["metrics"],
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

RANGE_DURATIONS = {
    "1h": timedelta(hours=1),
    "6h": timedelta(hours=6),
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
}

DOWNSAMPLE_INTERVALS = {
    "6h": timedelta(minutes=2),
    "24h": timedelta(minutes=5),
    "7d": timedelta(minutes=30),
}


def _compute_ops_per_second(
    current: ClusterMetric, previous: ClusterMetric
) -> OpsPerSecond:
    """Compute ops/sec as delta between two consecutive metric snapshots."""
    dt = (current.collected_at - previous.collected_at).total_seconds()
    if dt <= 0:
        return OpsPerSecond()

    def _rate(cur_val: int | None, prev_val: int | None) -> float | None:
        if cur_val is None or prev_val is None:
            return None
        delta = cur_val - prev_val
        if delta < 0:
            return None  # counter reset
        return round(delta / dt, 2)

    return OpsPerSecond(
        insert=_rate(current.ops_insert, previous.ops_insert),
        query=_rate(current.ops_query, previous.ops_query),
        update=_rate(current.ops_update, previous.ops_update),
        delete=_rate(current.ops_delete, previous.ops_delete),
    )


def _fs_used_percent(metric: ClusterMetric) -> float | None:
    if metric.fs_used_bytes is not None and metric.fs_total_bytes:
        return round((metric.fs_used_bytes / metric.fs_total_bytes) * 100, 2)
    return None


def _cache_hit_ratio(metric: ClusterMetric) -> float | None:
    if metric.wt_cache_used_bytes is not None and metric.wt_cache_total_bytes:
        return round(
            (1 - metric.wt_cache_dirty_bytes / metric.wt_cache_total_bytes) * 100, 2
        ) if metric.wt_cache_dirty_bytes is not None else None
    return None


async def _get_cluster_or_404(
    db: AsyncSession, cluster_id: uuid.UUID
) -> Cluster:
    result = await db.execute(select(Cluster).where(Cluster.id == cluster_id))
    cluster = result.scalar_one_or_none()
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")
    return cluster


def _downsample(
    metrics: list[ClusterMetric], interval: timedelta
) -> list[ClusterMetric]:
    """Downsample by selecting the middle point from each time bucket."""
    if not metrics:
        return []
    buckets: list[list[ClusterMetric]] = []
    bucket_start = metrics[0].collected_at
    current_bucket: list[ClusterMetric] = []

    for m in metrics:
        if m.collected_at - bucket_start >= interval and current_bucket:
            buckets.append(current_bucket)
            current_bucket = [m]
            bucket_start = m.collected_at
        else:
            current_bucket.append(m)
    if current_bucket:
        buckets.append(current_bucket)

    return [b[len(b) // 2] for b in buckets]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/latest", response_model=MetricLatestResponse)
async def get_latest_metrics(
    cluster_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role("viewer"))],
):
    """Get the latest metrics for a cluster, computing ops/sec from delta."""
    cluster = await _get_cluster_or_404(db, cluster_id)

    result = await db.execute(
        select(ClusterMetric)
        .where(ClusterMetric.cluster_id == cluster.id)
        .order_by(ClusterMetric.collected_at.desc())
        .limit(2)
    )
    rows = result.scalars().all()

    if not rows:
        raise HTTPException(status_code=404, detail="No metrics found for this cluster")

    latest = rows[0]
    ops = OpsPerSecond()
    if len(rows) == 2:
        ops = _compute_ops_per_second(rows[0], rows[1])

    return MetricLatestResponse(
        cluster_id=str(cluster.id),
        collected_at=latest.collected_at,
        rs_state=latest.rs_state,
        primary_member=latest.primary_member,
        members_up=latest.members_up,
        members_total=latest.members_total,
        max_replication_lag_seconds=latest.max_replication_lag_seconds,
        connections=ConnectionsInfo(
            current=latest.connections_current,
            available=latest.connections_available,
        ),
        ops_per_second=ops,
        memory=MemoryInfo(
            resident_mb=latest.memory_resident_mb,
            virtual_mb=latest.memory_virtual_mb,
        ),
        cache=CacheInfo(
            used_bytes=latest.wt_cache_used_bytes,
            total_bytes=latest.wt_cache_total_bytes,
            dirty_bytes=latest.wt_cache_dirty_bytes,
            hit_ratio=_cache_hit_ratio(latest),
        ),
        storage=StorageInfo(
            data_size_bytes=latest.data_size_bytes,
            fs_total_bytes=latest.fs_total_bytes,
            fs_used_bytes=latest.fs_used_bytes,
            fs_used_percent=_fs_used_percent(latest),
        ),
        status=cluster.status,
    )


@router.get("", response_model=MetricRangeResponse)
async def get_metrics_range(
    cluster_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role("viewer"))],
    range: str = Query("1h", pattern="^(1h|6h|24h|7d)$"),  # noqa: A002
):
    """Get metrics over a time range with optional downsampling."""
    cluster = await _get_cluster_or_404(db, cluster_id)

    duration = RANGE_DURATIONS[range]
    cutoff = datetime.now(timezone.utc) - duration

    result = await db.execute(
        select(ClusterMetric)
        .where(
            ClusterMetric.cluster_id == cluster.id,
            ClusterMetric.collected_at >= cutoff,
        )
        .order_by(ClusterMetric.collected_at.asc())
    )
    metrics = list(result.scalars().all())

    # Downsample for longer ranges
    if range in DOWNSAMPLE_INTERVALS:
        metrics = _downsample(metrics, DOWNSAMPLE_INTERVALS[range])

    # Build points with per-point ops rates
    points: list[MetricPointResponse] = []
    for i, m in enumerate(metrics):
        ops = OpsPerSecond()
        if i > 0:
            ops = _compute_ops_per_second(m, metrics[i - 1])
        points.append(
            MetricPointResponse(
                collected_at=m.collected_at,
                connections_current=m.connections_current,
                max_replication_lag_seconds=m.max_replication_lag_seconds,
                memory_resident_mb=m.memory_resident_mb,
                fs_used_percent=_fs_used_percent(m),
                ops_per_second=ops,
            )
        )

    return MetricRangeResponse(
        cluster_id=str(cluster.id),
        range=range,
        points=points,
    )


@router.post("/refresh", response_model=MetricLatestResponse)
async def refresh_metrics(
    cluster_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role("operator"))],
):
    """Trigger an immediate metric collection for a cluster."""
    from app.services import monitor_service

    cluster = await _get_cluster_or_404(db, cluster_id)

    try:
        metric = await monitor_service.collect_cluster_metrics(db, cluster)
    except Exception:
        raise HTTPException(status_code=502, detail="Failed to reach MongoDB cluster")

    if metric is None:
        raise HTTPException(
            status_code=502, detail="Failed to collect metrics from cluster"
        )

    await monitor_service.check_thresholds_and_alert(db, cluster, metric)
    await monitor_service.update_cluster_status(db, cluster, metric)
    await db.commit()

    # Fetch latest 2 for ops/sec computation
    result = await db.execute(
        select(ClusterMetric)
        .where(ClusterMetric.cluster_id == cluster.id)
        .order_by(ClusterMetric.collected_at.desc())
        .limit(2)
    )
    rows = result.scalars().all()
    latest = rows[0]
    ops = OpsPerSecond()
    if len(rows) == 2:
        ops = _compute_ops_per_second(rows[0], rows[1])

    return MetricLatestResponse(
        cluster_id=str(cluster.id),
        collected_at=latest.collected_at,
        rs_state=latest.rs_state,
        primary_member=latest.primary_member,
        members_up=latest.members_up,
        members_total=latest.members_total,
        max_replication_lag_seconds=latest.max_replication_lag_seconds,
        connections=ConnectionsInfo(
            current=latest.connections_current,
            available=latest.connections_available,
        ),
        ops_per_second=ops,
        memory=MemoryInfo(
            resident_mb=latest.memory_resident_mb,
            virtual_mb=latest.memory_virtual_mb,
        ),
        cache=CacheInfo(
            used_bytes=latest.wt_cache_used_bytes,
            total_bytes=latest.wt_cache_total_bytes,
            dirty_bytes=latest.wt_cache_dirty_bytes,
            hit_ratio=_cache_hit_ratio(latest),
        ),
        storage=StorageInfo(
            data_size_bytes=latest.data_size_bytes,
            fs_total_bytes=latest.fs_total_bytes,
            fs_used_bytes=latest.fs_used_bytes,
            fs_used_percent=_fs_used_percent(latest),
        ),
        status=cluster.status,
    )
