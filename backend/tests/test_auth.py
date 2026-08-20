import pytest
from httpx import AsyncClient

from app.models.user import User


pytestmark = pytest.mark.asyncio


async def test_login_success(client: AsyncClient, admin_user: User):
    resp = await client.post("/api/auth/login", json={"username": "admin", "password": "admin-password"})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


async def test_login_wrong_password(client: AsyncClient, admin_user: User):
    resp = await client.post("/api/auth/login", json={"username": "admin", "password": "wrong"})
    assert resp.status_code == 401


async def test_login_nonexistent_user(client: AsyncClient):
    resp = await client.post("/api/auth/login", json={"username": "nobody", "password": "whatever"})
    assert resp.status_code == 401


async def test_me_with_valid_token(client: AsyncClient, admin_user: User):
    login_resp = await client.post("/api/auth/login", json={"username": "admin", "password": "admin-password"})
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]

    me_resp = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_resp.status_code == 200
    data = me_resp.json()
    assert data["username"] == "admin"
    assert data["role"] == "admin"
    assert data["disabled"] is False


async def test_me_with_invalid_token(client: AsyncClient):
    resp = await client.get("/api/auth/me", headers={"Authorization": "Bearer invalid-token"})
    assert resp.status_code in (401, 403)


async def test_refresh_token_flow(client: AsyncClient, admin_user: User):
    login_resp = await client.post("/api/auth/login", json={"username": "admin", "password": "admin-password"})
    assert login_resp.status_code == 200
    refresh_token = login_resp.json()["refresh_token"]

    refresh_resp = await client.post("/api/auth/refresh", json={"refresh_token": refresh_token})
    assert refresh_resp.status_code == 200
    data = refresh_resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    # New refresh token should be different from the old one (old was revoked)
    assert data["refresh_token"] != refresh_token


async def test_logout_revokes_refresh_token(client: AsyncClient, admin_user: User):
    login_resp = await client.post("/api/auth/login", json={"username": "admin", "password": "admin-password"})
    assert login_resp.status_code == 200
    tokens = login_resp.json()
    access_token = tokens["access_token"]
    refresh_token = tokens["refresh_token"]

    # Logout
    logout_resp = await client.post(
        "/api/auth/logout",
        json={"refresh_token": refresh_token},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert logout_resp.status_code == 200

    # Try to refresh with the revoked token — should fail
    refresh_resp = await client.post("/api/auth/refresh", json={"refresh_token": refresh_token})
    assert refresh_resp.status_code == 401
