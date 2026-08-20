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


@pytest.mark.asyncio
async def test_create_and_list_secret(client: AsyncClient, admin_user):
    token = await _login_as_admin(client)

    # Create a secret
    resp = await client.post(
        "/api/secrets",
        json={
            "name": "deploy-key",
            "type": "ssh_key",
            "plaintext": "ssh-rsa AAAAB3... user@host",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "deploy-key"
    assert data["type"] == "ssh_key"
    assert "id" in data
    assert "created_at" in data
    assert "created_by" in data
    # Plaintext and ciphertext must NEVER be returned
    assert "plaintext" not in data
    assert "ciphertext" not in data

    # List secrets
    resp = await client.get(
        "/api/secrets",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    secrets = resp.json()
    assert len(secrets) >= 1
    assert secrets[0]["name"] == "deploy-key"
    assert "plaintext" not in secrets[0]
    assert "ciphertext" not in secrets[0]


@pytest.mark.asyncio
async def test_delete_secret(client: AsyncClient, admin_user):
    token = await _login_as_admin(client)

    # Create a secret
    resp = await client.post(
        "/api/secrets",
        json={
            "name": "temp-key",
            "type": "admin_password",
            "plaintext": "super-secret-password",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    secret_id = resp.json()["id"]

    # Delete the secret
    resp = await client.delete(
        f"/api/secrets/{secret_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_viewer_cannot_access_secrets(client: AsyncClient, db_session: AsyncSession, admin_user):
    # Create a viewer user
    viewer = await user_service.create_user(
        db_session,
        username="viewer1",
        password="viewer-pass-123",
        role_name="viewer",
    )
    await db_session.commit()

    # Login as viewer
    resp = await client.post(
        "/api/auth/login",
        json={"username": "viewer1", "password": "viewer-pass-123"},
    )
    assert resp.status_code == 200
    viewer_token = resp.json()["access_token"]

    # Try to list secrets -> 403
    resp = await client.get(
        "/api/secrets",
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert resp.status_code == 403
