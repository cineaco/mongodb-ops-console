import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cluster import Cluster
from app.models.user import User
from app.services import user_service


async def _login(client: AsyncClient, username: str, password: str) -> str:
    resp = await client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )
    assert resp.status_code == 200
    return resp.json()["access_token"]


async def _create_test_cluster(db_session: AsyncSession, admin_user: User) -> Cluster:
    cluster = Cluster(
        name="test-cluster-jobs",
        topology="pss",
        mongodb_version="8.0",
        mongodb_port=37017,
        replicaset_name="rs0",
        config={},
        status="healthy",
        created_by=admin_user.id,
    )
    db_session.add(cluster)
    await db_session.commit()
    await db_session.refresh(cluster)
    return cluster


@pytest.mark.asyncio
async def test_create_job_via_convenience_endpoint(
    client: AsyncClient, db_session: AsyncSession, admin_user: User
):
    cluster = await _create_test_cluster(db_session, admin_user)
    token = await _login(client, "admin", "admin-password")

    resp = await client.post(
        f"/api/clusters/{cluster.id}/ops/pbm-list",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "job_id" in data
    assert data["operation"] == "pbm_list"
    assert data["status"] == "pending"


@pytest.mark.asyncio
async def test_get_job(
    client: AsyncClient, db_session: AsyncSession, admin_user: User
):
    cluster = await _create_test_cluster(db_session, admin_user)
    token = await _login(client, "admin", "admin-password")

    create_resp = await client.post(
        f"/api/clusters/{cluster.id}/ops/pbm-backup",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert create_resp.status_code == 201
    job_id = create_resp.json()["job_id"]

    resp = await client.get(
        f"/api/jobs/{job_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["operation"] == "pbm_backup"
    assert data["id"] == job_id


@pytest.mark.asyncio
async def test_list_cluster_jobs(
    client: AsyncClient, db_session: AsyncSession, admin_user: User
):
    cluster = await _create_test_cluster(db_session, admin_user)
    token = await _login(client, "admin", "admin-password")

    # Create two jobs
    await client.post(
        f"/api/clusters/{cluster.id}/ops/pbm-list",
        headers={"Authorization": f"Bearer {token}"},
    )
    await client.post(
        f"/api/clusters/{cluster.id}/ops/pbm-backup",
        headers={"Authorization": f"Bearer {token}"},
    )

    resp = await client.get(
        f"/api/clusters/{cluster.id}/jobs",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    jobs = resp.json()
    assert len(jobs) >= 2


@pytest.mark.asyncio
async def test_cancel_pending_job(
    client: AsyncClient, db_session: AsyncSession, admin_user: User
):
    cluster = await _create_test_cluster(db_session, admin_user)
    token = await _login(client, "admin", "admin-password")

    create_resp = await client.post(
        f"/api/clusters/{cluster.id}/ops/pbm-list",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert create_resp.status_code == 201
    job_id = create_resp.json()["job_id"]

    resp = await client.post(
        f"/api/jobs/{job_id}/cancel",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"


@pytest.mark.asyncio
async def test_admin_only_operation_requires_admin(
    client: AsyncClient, db_session: AsyncSession, admin_user: User
):
    cluster = await _create_test_cluster(db_session, admin_user)

    # Create operator user
    await user_service.create_user(
        db_session,
        username="operator1",
        password="operator-pass-123",
        role_name="operator",
    )
    await db_session.commit()

    operator_token = await _login(client, "operator1", "operator-pass-123")

    # Operator tries rolling-restart (admin only) -> 403
    resp = await client.post(
        f"/api/clusters/{cluster.id}/ops/rolling-restart",
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert resp.status_code == 403

    # Operator tries pbm-list (operator+) -> 201
    resp = await client.post(
        f"/api/clusters/{cluster.id}/ops/pbm-list",
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert resp.status_code == 201
