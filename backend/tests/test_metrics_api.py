import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cluster import Cluster
from app.models.cluster_metric import ClusterMetric
from app.models.user import User


async def _get_token(client: AsyncClient) -> str:
    resp = await client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin-password"},
    )
    assert resp.status_code == 200
    return resp.json()["access_token"]


async def _create_cluster_with_metrics(
    db_session: AsyncSession,
    admin_user: User,
    n_metrics: int = 3,
) -> tuple[Cluster, list[ClusterMetric]]:
    """Create a cluster with status='healthy' and N metric rows with 30s intervals."""
    cluster = Cluster(
        name=f"test-cluster-{uuid.uuid4().hex[:8]}",
        topology="pss",
        mongodb_version="8.0",
        mongodb_port=37017,
        replicaset_name="rs0",
        status="healthy",
        created_by=admin_user.id,
    )
    db_session.add(cluster)
    await db_session.flush()

    now = datetime.now(timezone.utc)
    metrics: list[ClusterMetric] = []
    for i in range(n_metrics):
        m = ClusterMetric(
            cluster_id=cluster.id,
            collected_at=now - timedelta(seconds=30 * (n_metrics - 1 - i)),
            rs_state="ok",
            primary_member="mongo1:37017",
            members_up=3,
            members_total=3,
            max_replication_lag_seconds=0.5,
            connections_current=50 + i,
            connections_available=500,
            ops_insert=1000 + i * 100,
            ops_query=2000 + i * 200,
            ops_update=500 + i * 50,
            ops_delete=100 + i * 10,
            memory_resident_mb=256,
            memory_virtual_mb=1024,
            wt_cache_used_bytes=100_000_000,
            wt_cache_total_bytes=200_000_000,
            wt_cache_dirty_bytes=5_000_000,
            data_size_bytes=500_000_000,
            storage_size_bytes=600_000_000,
            index_size_bytes=50_000_000,
            fs_total_bytes=1_000_000_000,
            fs_used_bytes=400_000_000,
        )
        db_session.add(m)
        metrics.append(m)

    await db_session.commit()
    return cluster, metrics


@pytest.mark.asyncio
async def test_get_latest_metrics(
    client: AsyncClient, db_session: AsyncSession, admin_user: User
):
    cluster, _ = await _create_cluster_with_metrics(db_session, admin_user, n_metrics=3)
    token = await _get_token(client)

    resp = await client.get(
        f"/api/clusters/{cluster.id}/metrics/latest",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["cluster_id"] == str(cluster.id)
    assert data["rs_state"] == "ok"
    assert data["members_up"] == 3
    assert data["members_total"] == 3
    assert data["primary_member"] == "mongo1:37017"
    assert data["status"] == "healthy"

    # Connections
    assert data["connections"]["current"] is not None
    assert data["connections"]["available"] == 500

    # Ops per second should be computed
    assert "ops_per_second" in data
    assert data["ops_per_second"]["insert"] is not None

    # Storage
    assert data["storage"]["fs_total_bytes"] == 1_000_000_000
    assert data["storage"]["fs_used_percent"] is not None


@pytest.mark.asyncio
async def test_get_latest_no_metrics(
    client: AsyncClient, db_session: AsyncSession, admin_user: User
):
    # Create cluster with no metrics
    cluster = Cluster(
        name=f"empty-cluster-{uuid.uuid4().hex[:8]}",
        topology="pss",
        mongodb_version="8.0",
        mongodb_port=37017,
        replicaset_name="rs0",
        status="pending",
        created_by=admin_user.id,
    )
    db_session.add(cluster)
    await db_session.commit()

    token = await _get_token(client)
    resp = await client.get(
        f"/api/clusters/{cluster.id}/metrics/latest",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_metrics_range(
    client: AsyncClient, db_session: AsyncSession, admin_user: User
):
    cluster, _ = await _create_cluster_with_metrics(db_session, admin_user, n_metrics=5)
    token = await _get_token(client)

    resp = await client.get(
        f"/api/clusters/{cluster.id}/metrics?range=1h",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["cluster_id"] == str(cluster.id)
    assert data["range"] == "1h"
    assert isinstance(data["points"], list)
    assert len(data["points"]) == 5

    # Each point should have the expected fields
    for pt in data["points"]:
        assert "collected_at" in pt
        assert "connections_current" in pt
        assert "ops_per_second" in pt


@pytest.mark.asyncio
async def test_get_metrics_ops_per_second_computed(
    client: AsyncClient, db_session: AsyncSession, admin_user: User
):
    cluster, _ = await _create_cluster_with_metrics(db_session, admin_user, n_metrics=3)
    token = await _get_token(client)

    resp = await client.get(
        f"/api/clusters/{cluster.id}/metrics/latest",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()

    ops = data["ops_per_second"]
    # With 30s intervals and incrementing counters (100 insert delta, 200 query delta, etc.)
    # ops/sec should be positive
    assert ops["insert"] is not None and ops["insert"] > 0
    assert ops["query"] is not None and ops["query"] > 0
    assert ops["update"] is not None and ops["update"] > 0
    assert ops["delete"] is not None and ops["delete"] > 0
