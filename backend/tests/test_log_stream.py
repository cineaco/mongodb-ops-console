import uuid
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cluster import Cluster
from app.models.job import Job
from app.models.user import User


async def _login(client: AsyncClient, username: str, password: str) -> str:
    resp = await client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )
    assert resp.status_code == 200
    return resp.json()["access_token"]


async def _create_test_cluster(db_session: AsyncSession, admin_user: User) -> Cluster:
    cluster = Cluster(
        name="test-cluster-logs",
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
async def test_stream_completed_job_log(
    client: AsyncClient, db_session: AsyncSession, admin_user: User
):
    cluster = await _create_test_cluster(db_session, admin_user)
    token = await _login(client, "admin", "admin-password")

    job = Job(
        cluster_id=cluster.id,
        operation="deploy",
        status="success",
        params={},
        result={"log": "PLAY [test] ***\nDone.", "exit_code": 0, "message": "ok"},
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
        created_by=admin_user.id,
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)

    resp = await client.get(
        f"/api/jobs/{job.id}/logs",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]
    body = resp.text
    assert "PLAY [test]" in body
    assert "Done." in body


@pytest.mark.asyncio
async def test_stream_nonexistent_job_returns_404(
    client: AsyncClient, admin_user: User
):
    token = await _login(client, "admin", "admin-password")
    random_id = uuid.uuid4()

    resp = await client.get(
        f"/api/jobs/{random_id}/logs",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_stream_pending_job_returns_404(
    client: AsyncClient, db_session: AsyncSession, admin_user: User
):
    cluster = await _create_test_cluster(db_session, admin_user)
    token = await _login(client, "admin", "admin-password")

    job = Job(
        cluster_id=cluster.id,
        operation="deploy",
        status="pending",
        params={},
        created_by=admin_user.id,
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)

    resp = await client.get(
        f"/api/jobs/{job.id}/logs",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404
