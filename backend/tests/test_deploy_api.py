import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import encrypt
from app.models.cluster import Cluster
from app.models.secret import Secret
from app.models.user import User
from app.services import user_service


async def _login(client: AsyncClient, username: str, password: str) -> str:
    resp = await client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )
    assert resp.status_code == 200
    return resp.json()["access_token"]


async def _create_deployable_cluster(
    db_session: AsyncSession, admin_user: User
) -> Cluster:
    """Create a cluster with an admin credentials secret."""
    admin_pw = b"AdminPass123"
    ct, nonce, tag = encrypt(admin_pw)
    admin_secret = Secret(
        name=f"deploy-admin-{uuid.uuid4().hex[:8]}",
        type="admin_password",
        ciphertext=ct,
        nonce=nonce,
        auth_tag=tag,
        created_by=admin_user.id,
    )
    db_session.add(admin_secret)
    await db_session.flush()

    cluster = Cluster(
        name=f"deploy-cluster-{uuid.uuid4().hex[:8]}",
        topology="pss",
        mongodb_version="8.0",
        mongodb_port=37017,
        replicaset_name="rs0",
        config={},
        status="pending",
        admin_credentials_secret_id=admin_secret.id,
        created_by=admin_user.id,
    )
    db_session.add(cluster)
    await db_session.commit()
    await db_session.refresh(cluster)
    return cluster


@pytest.mark.asyncio
async def test_deploy_creates_job(
    client: AsyncClient, db_session: AsyncSession, admin_user: User
):
    cluster = await _create_deployable_cluster(db_session, admin_user)
    token = await _login(client, "admin", "admin-password")

    resp = await client.post(
        f"/api/clusters/{cluster.id}/ops/deploy",
        headers={"Authorization": f"Bearer {token}"},
        json={"tags": ["install", "config"]},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["operation"] == "deploy"
    assert data["status"] == "pending"


@pytest.mark.asyncio
async def test_rerun_creates_job(
    client: AsyncClient, db_session: AsyncSession, admin_user: User
):
    cluster = await _create_deployable_cluster(db_session, admin_user)
    token = await _login(client, "admin", "admin-password")

    resp = await client.post(
        f"/api/clusters/{cluster.id}/ops/rerun",
        headers={"Authorization": f"Bearer {token}"},
        json={"tags": ["monitoring"]},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["operation"] == "rerun"
    assert data["status"] == "pending"


@pytest.mark.asyncio
async def test_rerun_empty_tags_rejected(
    client: AsyncClient, db_session: AsyncSession, admin_user: User
):
    cluster = await _create_deployable_cluster(db_session, admin_user)
    token = await _login(client, "admin", "admin-password")

    resp = await client.post(
        f"/api/clusters/{cluster.id}/ops/rerun",
        headers={"Authorization": f"Bearer {token}"},
        json={"tags": []},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_deploy_requires_admin(
    client: AsyncClient, db_session: AsyncSession, admin_user: User
):
    cluster = await _create_deployable_cluster(db_session, admin_user)

    # Create operator user
    await user_service.create_user(
        db_session,
        username="operator-deploy",
        password="operator-pass-123",
        role_name="operator",
    )
    await db_session.commit()

    operator_token = await _login(client, "operator-deploy", "operator-pass-123")

    resp = await client.post(
        f"/api/clusters/{cluster.id}/ops/deploy",
        headers={"Authorization": f"Bearer {operator_token}"},
        json={"tags": ["install"]},
    )
    assert resp.status_code == 403
