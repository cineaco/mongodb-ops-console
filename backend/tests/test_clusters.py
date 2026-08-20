import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.services import user_service


async def _login_as_admin(client: AsyncClient) -> str:
    resp = await client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin-password"},
    )
    assert resp.status_code == 200
    return resp.json()["access_token"]


async def _create_cluster(client: AsyncClient, token: str, **overrides) -> dict:
    payload = {
        "name": "test-cluster",
        "topology": "pss",
        "mongodb_version": "8.0",
        "config": {"backup_enabled": False},
    }
    payload.update(overrides)
    resp = await client.post(
        "/api/clusters",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    return resp


@pytest.mark.asyncio
async def test_create_cluster(client: AsyncClient, admin_user):
    token = await _login_as_admin(client)
    resp = await _create_cluster(client, token)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "test-cluster"
    assert data["topology"] == "pss"
    assert data["mongodb_version"] == "8.0"
    assert data["mongodb_port"] == 37017
    assert data["replicaset_name"] == "rs0"
    assert data["status"] == "pending"
    assert data["config"] == {"backup_enabled": False}
    assert "id" in data
    assert "created_at" in data
    assert "created_by" in data


@pytest.mark.asyncio
async def test_list_and_get_cluster(client: AsyncClient, admin_user):
    token = await _login_as_admin(client)
    create_resp = await _create_cluster(client, token)
    assert create_resp.status_code == 201
    cluster_id = create_resp.json()["id"]

    # List clusters
    resp = await client.get(
        "/api/clusters",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    clusters = resp.json()
    assert len(clusters) >= 1
    assert any(c["id"] == cluster_id for c in clusters)

    # Get by ID
    resp = await client.get(
        f"/api/clusters/{cluster_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == cluster_id
    assert resp.json()["name"] == "test-cluster"


@pytest.mark.asyncio
async def test_update_cluster_config_merges(client: AsyncClient, admin_user):
    token = await _login_as_admin(client)
    create_resp = await _create_cluster(client, token, config={"backup_enabled": False})
    assert create_resp.status_code == 201
    cluster_id = create_resp.json()["id"]

    # Update with new config key — should MERGE, not replace
    resp = await client.patch(
        f"/api/clusters/{cluster_id}",
        json={"config": {"enable_monitoring": True}},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    config = resp.json()["config"]
    assert config["backup_enabled"] is False
    assert config["enable_monitoring"] is True


@pytest.mark.asyncio
async def test_delete_cluster_requires_admin(
    client: AsyncClient, db_session: AsyncSession, admin_user
):
    token = await _login_as_admin(client)
    create_resp = await _create_cluster(client, token)
    assert create_resp.status_code == 201
    cluster_id = create_resp.json()["id"]

    # Create operator user
    await user_service.create_user(
        db_session,
        username="operator1",
        password="operator-pass-123",
        role_name="operator",
    )
    await db_session.commit()

    # Login as operator
    resp = await client.post(
        "/api/auth/login",
        json={"username": "operator1", "password": "operator-pass-123"},
    )
    assert resp.status_code == 200
    operator_token = resp.json()["access_token"]

    # Operator tries to delete -> 403
    resp = await client.delete(
        f"/api/clusters/{cluster_id}",
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert resp.status_code == 403

    # Admin deletes -> 204
    resp = await client.delete(
        f"/api/clusters/{cluster_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 204
