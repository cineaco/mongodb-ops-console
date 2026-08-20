import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cluster import Cluster
from app.models.cluster_alert import ClusterAlert
from app.models.cluster_metric import ClusterMetric
from app.services import alert_service, monitor_service


def _make_cluster(**overrides) -> Cluster:
    defaults = dict(
        name=f"test-cluster-{uuid.uuid4().hex[:8]}",
        topology="pss",
        mongodb_version="7.0",
        mongodb_port=37017,
        replicaset_name="rs0",
        config={},
        created_by=uuid.uuid4(),
    )
    defaults.update(overrides)
    return Cluster(**defaults)


def _make_metric(cluster_id: uuid.UUID, **overrides) -> ClusterMetric:
    defaults = dict(
        cluster_id=cluster_id,
        rs_state="ok",
        primary_member="host1:37017",
        members_up=3,
        members_total=3,
        max_replication_lag_seconds=0.5,
        connections_current=50,
        connections_available=800,
        memory_resident_mb=512,
        memory_virtual_mb=2048,
        wt_cache_dirty_bytes=100,
        wt_cache_total_bytes=10000,
        fs_used_bytes=30_000_000_000,
        fs_total_bytes=100_000_000_000,
    )
    defaults.update(overrides)
    return ClusterMetric(**defaults)


# -----------------------------------------------------------------------
# 1. get_effective_thresholds — defaults
# -----------------------------------------------------------------------


def test_get_effective_thresholds_defaults():
    cluster = _make_cluster(config={})
    thresholds = monitor_service.get_effective_thresholds(cluster)

    assert thresholds["replication_lag_warning"] == 5.0
    assert thresholds["replication_lag_critical"] == 10.0
    assert thresholds["connections_warning"] == 500
    assert thresholds["connections_critical"] == 800
    assert thresholds["disk_usage_warning"] == 70
    assert thresholds["disk_usage_critical"] == 85
    assert thresholds["memory_warning"] == 80
    assert thresholds["memory_critical"] == 90
    assert thresholds["cache_dirty_warning"] == 20
    assert thresholds["member_down_critical"] == 1


# -----------------------------------------------------------------------
# 2. get_effective_thresholds — with overrides
# -----------------------------------------------------------------------


def test_get_effective_thresholds_with_overrides():
    cluster = _make_cluster(
        config={
            "alert_thresholds": {
                "replication_lag_warning": 3.0,
                "disk_usage_critical": 95,
            }
        }
    )
    thresholds = monitor_service.get_effective_thresholds(cluster)

    # Overridden values
    assert thresholds["replication_lag_warning"] == 3.0
    assert thresholds["disk_usage_critical"] == 95

    # Non-overridden values keep defaults
    assert thresholds["replication_lag_critical"] == 10.0
    assert thresholds["connections_warning"] == 500


# -----------------------------------------------------------------------
# 3. check_thresholds creates alert when lag exceeds critical
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_check_thresholds_creates_alert(db_session: AsyncSession):
    cluster = _make_cluster()
    db_session.add(cluster)
    await db_session.flush()

    metric = _make_metric(cluster.id, max_replication_lag_seconds=12.0)
    db_session.add(metric)
    await db_session.flush()

    await monitor_service.check_thresholds_and_alert(db_session, cluster, metric)

    alert = await alert_service.get_active_alert(db_session, cluster.id, "replication_lag")
    assert alert is not None
    assert alert.severity == "critical"
    assert alert.actual_value == 12.0
    assert alert.status == "active"


# -----------------------------------------------------------------------
# 4. check_thresholds resolves alert when value returns to normal
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_check_thresholds_resolves_alert(db_session: AsyncSession):
    cluster = _make_cluster()
    db_session.add(cluster)
    await db_session.flush()

    # First: create an alert with high lag
    metric_high = _make_metric(cluster.id, max_replication_lag_seconds=12.0)
    db_session.add(metric_high)
    await db_session.flush()
    await monitor_service.check_thresholds_and_alert(db_session, cluster, metric_high)

    alert = await alert_service.get_active_alert(db_session, cluster.id, "replication_lag")
    assert alert is not None
    assert alert.status == "active"

    # Now: check with normal lag — should resolve
    metric_normal = _make_metric(cluster.id, max_replication_lag_seconds=1.0)
    db_session.add(metric_normal)
    await db_session.flush()
    await monitor_service.check_thresholds_and_alert(db_session, cluster, metric_normal)

    resolved = await alert_service.get_active_alert(db_session, cluster.id, "replication_lag")
    assert resolved is None


# -----------------------------------------------------------------------
# 5. update_cluster_status — healthy
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_cluster_status_healthy(db_session: AsyncSession):
    cluster = _make_cluster(status="pending")
    db_session.add(cluster)
    await db_session.flush()

    metric = _make_metric(cluster.id, rs_state="ok")
    db_session.add(metric)
    await db_session.flush()

    await monitor_service.update_cluster_status(db_session, cluster, metric)
    assert cluster.status == "healthy"


# -----------------------------------------------------------------------
# 6. update_cluster_status — failed
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_cluster_status_failed(db_session: AsyncSession):
    cluster = _make_cluster(status="healthy")
    db_session.add(cluster)
    await db_session.flush()

    metric = _make_metric(cluster.id, rs_state="error")
    db_session.add(metric)
    await db_session.flush()

    await monitor_service.update_cluster_status(db_session, cluster, metric)
    assert cluster.status == "failed"
