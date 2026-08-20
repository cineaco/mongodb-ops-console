import pytest
from httpx import AsyncClient


async def _login_as_admin(client: AsyncClient) -> str:
    resp = await client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin-password"},
    )
    assert resp.status_code == 200
    return resp.json()["access_token"]


async def _setup_cluster_and_secret(client: AsyncClient, token: str) -> tuple[str, str]:
    """Create an SSH key secret and a PSS cluster, return (cluster_id, secret_id)."""
    # Create secret
    resp = await client.post(
        "/api/secrets",
        json={
            "name": "ssh-key-for-hosts",
            "type": "ssh_key",
            "plaintext": "ssh-rsa AAAAB3... user@host",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    secret_id = resp.json()["id"]

    # Create cluster
    resp = await client.post(
        "/api/clusters",
        json={
            "name": "host-test-cluster",
            "topology": "pss",
            "mongodb_version": "8.0",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    cluster_id = resp.json()["id"]

    return cluster_id, secret_id


@pytest.mark.asyncio
async def test_create_and_list_host(client: AsyncClient, admin_user):
    token = await _login_as_admin(client)
    cluster_id, secret_id = await _setup_cluster_and_secret(client, token)

    # Create a primary host
    resp = await client.post(
        f"/api/clusters/{cluster_id}/hosts",
        json={
            "hostname": "mongo-primary-1",
            "ip_address": "10.21.32.10",
            "role": "primary",
            "ssh_key_secret_id": secret_id,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["hostname"] == "mongo-primary-1"
    assert data["ip_address"] == "10.21.32.10"
    assert data["role"] == "primary"
    assert data["ssh_user"] == "ubuntu"
    assert data["ssh_port"] == 22
    assert data["cluster_id"] == cluster_id
    assert data["ssh_key_secret_id"] == secret_id

    # List hosts for cluster
    resp = await client.get(
        f"/api/clusters/{cluster_id}/hosts",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    hosts = resp.json()
    assert len(hosts) == 1
    assert hosts[0]["hostname"] == "mongo-primary-1"


@pytest.mark.asyncio
async def test_update_host(client: AsyncClient, admin_user):
    token = await _login_as_admin(client)
    cluster_id, secret_id = await _setup_cluster_and_secret(client, token)

    # Create host
    resp = await client.post(
        f"/api/clusters/{cluster_id}/hosts",
        json={
            "hostname": "mongo-secondary-1",
            "ip_address": "10.21.32.11",
            "role": "secondary",
            "ssh_key_secret_id": secret_id,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    host_id = resp.json()["id"]

    # Update ip_address
    resp = await client.patch(
        f"/api/clusters/{cluster_id}/hosts/{host_id}",
        json={"ip_address": "10.21.32.99"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["ip_address"] == "10.21.32.99"


@pytest.mark.asyncio
async def test_delete_host(client: AsyncClient, admin_user):
    token = await _login_as_admin(client)
    cluster_id, secret_id = await _setup_cluster_and_secret(client, token)

    # Create host
    resp = await client.post(
        f"/api/clusters/{cluster_id}/hosts",
        json={
            "hostname": "mongo-arbiter-1",
            "ip_address": "10.21.32.12",
            "role": "arbiter",
            "ssh_key_secret_id": secret_id,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    host_id = resp.json()["id"]

    # Delete host
    resp = await client.delete(
        f"/api/clusters/{cluster_id}/hosts/{host_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 204
