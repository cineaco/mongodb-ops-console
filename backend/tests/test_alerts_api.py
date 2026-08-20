import uuid
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cluster import Cluster
from app.models.cluster_alert import ClusterAlert
from app.models.user import User


async def _get_token(client: AsyncClient) -> str:
    resp = await client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin-password"},
    )
    assert resp.status_code == 200
    return resp.json()["access_token"]


async def _create_cluster_with_alerts(
    db_session: AsyncSession, admin_user: User
) -> tuple[Cluster, ClusterAlert, ClusterAlert]:
    cluster = Cluster(
        name=f"alert-cluster-{uuid.uuid4().hex[:8]}",
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
    alert1 = ClusterAlert(
        cluster_id=cluster.id,
        metric="replication_lag",
        severity="critical",
        message="Replication lag exceeded threshold",
        threshold_value=10.0,
        actual_value=25.0,
        status="active",
        first_triggered_at=now,
        last_triggered_at=now,
        created_by="poller",
    )
    alert2 = ClusterAlert(
        cluster_id=cluster.id,
        metric="connections",
        severity="warning",
        message="Connection count is high",
        threshold_value=500.0,
        actual_value=650.0,
        status="active",
        first_triggered_at=now,
        last_triggered_at=now,
        created_by="poller",
    )
    db_session.add_all([alert1, alert2])
    await db_session.commit()
    return cluster, alert1, alert2


@pytest.mark.asyncio
async def test_list_cluster_alerts(
    client: AsyncClient, db_session: AsyncSession, admin_user: User
):
    cluster, _, _ = await _create_cluster_with_alerts(db_session, admin_user)
    token = await _get_token(client)

    resp = await client.get(
        f"/api/clusters/{cluster.id}/alerts",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2


@pytest.mark.asyncio
async def test_list_cluster_alerts_filtered(
    client: AsyncClient, db_session: AsyncSession, admin_user: User
):
    cluster, _, _ = await _create_cluster_with_alerts(db_session, admin_user)
    token = await _get_token(client)

    resp = await client.get(
        f"/api/clusters/{cluster.id}/alerts?status=active",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 2

    resp = await client.get(
        f"/api/clusters/{cluster.id}/alerts?status=resolved",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 0


@pytest.mark.asyncio
async def test_resolve_alert(
    client: AsyncClient, db_session: AsyncSession, admin_user: User
):
    cluster, alert1, _ = await _create_cluster_with_alerts(db_session, admin_user)
    token = await _get_token(client)

    resp = await client.patch(
        f"/api/clusters/{cluster.id}/alerts/{alert1.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "resolved"
    assert data["resolved_at"] is not None


@pytest.mark.asyncio
async def test_list_all_alerts(
    client: AsyncClient, db_session: AsyncSession, admin_user: User
):
    await _create_cluster_with_alerts(db_session, admin_user)
    token = await _get_token(client)

    resp = await client.get(
        "/api/alerts",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 2


@pytest.mark.asyncio
async def test_active_alert_count(
    client: AsyncClient, db_session: AsyncSession, admin_user: User
):
    await _create_cluster_with_alerts(db_session, admin_user)
    token = await _get_token(client)

    resp = await client.get(
        "/api/alerts/count",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["active_count"] >= 2
