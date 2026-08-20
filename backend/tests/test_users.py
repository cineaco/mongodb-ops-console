import pytest
import pytest_asyncio
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
async def test_create_user_as_admin(client: AsyncClient, admin_user):
    token = await _login_as_admin(client)
    resp = await client.post(
        "/api/users",
        json={
            "username": "operator1",
            "password": "operator-pass-123",
            "role": "operator",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["username"] == "operator1"
    assert data["role"] == "operator"
    assert data["disabled"] is False


@pytest.mark.asyncio
async def test_list_users_as_admin(client: AsyncClient, admin_user):
    token = await _login_as_admin(client)
    resp = await client.get(
        "/api/users",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1


@pytest.mark.asyncio
async def test_viewer_cannot_create_user(client: AsyncClient, db_session: AsyncSession, admin_user):
    # Create a viewer user directly via the service
    viewer = await user_service.create_user(
        db_session,
        username="viewer1",
        password="viewer-pass-123",
        role_name="viewer",
    )
    await db_session.commit()

    # Login as the viewer
    resp = await client.post(
        "/api/auth/login",
        json={"username": "viewer1", "password": "viewer-pass-123"},
    )
    assert resp.status_code == 200
    viewer_token = resp.json()["access_token"]

    # Attempt to create a user as viewer -> 403
    resp = await client.post(
        "/api/users",
        json={
            "username": "should-fail",
            "password": "password-123",
            "role": "viewer",
        },
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_update_user_role(client: AsyncClient, admin_user):
    token = await _login_as_admin(client)

    # Create an operator user
    resp = await client.post(
        "/api/users",
        json={
            "username": "op-to-update",
            "password": "operator-pass-123",
            "role": "operator",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    user_id = resp.json()["id"]

    # Update role to viewer
    resp = await client.patch(
        f"/api/users/{user_id}",
        json={"role": "viewer"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "viewer"


@pytest.mark.asyncio
async def test_delete_user(client: AsyncClient, admin_user):
    token = await _login_as_admin(client)

    # Create a user to delete
    resp = await client.post(
        "/api/users",
        json={
            "username": "to-delete",
            "password": "delete-pass-123",
            "role": "viewer",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    user_id = resp.json()["id"]

    # Delete the user
    resp = await client.delete(
        f"/api/users/{user_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 204
