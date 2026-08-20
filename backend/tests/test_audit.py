import pytest
from httpx import AsyncClient


async def _login(client: AsyncClient, username: str = "admin", password: str = "admin-password"):
    resp = await client.post("/api/auth/login", json={"username": username, "password": password})
    return resp


async def _auth_header(client: AsyncClient) -> dict:
    resp = await _login(client)
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_login_creates_audit_entry(client: AsyncClient, admin_user):
    headers = await _auth_header(client)
    resp = await client.get("/api/audit-logs", headers=headers)
    assert resp.status_code == 200
    logs = resp.json()
    login_entries = [e for e in logs if e["action"] == "login"]
    assert len(login_entries) >= 1
    assert login_entries[0]["username"] == "admin"


@pytest.mark.asyncio
async def test_failed_login_creates_audit_entry(client: AsyncClient, admin_user):
    # Attempt a login with the wrong password
    await _login(client, password="wrong-password")

    # Login correctly to get a token
    headers = await _auth_header(client)
    resp = await client.get("/api/audit-logs", params={"action": "login_failed"}, headers=headers)
    assert resp.status_code == 200
    logs = resp.json()
    assert len(logs) >= 1
    assert logs[0]["username"] == "admin"


@pytest.mark.asyncio
async def test_create_user_creates_audit_entry(client: AsyncClient, admin_user):
    headers = await _auth_header(client)
    await client.post(
        "/api/users",
        json={"username": "newuser", "password": "Secret123!", "role": "viewer"},
        headers=headers,
    )
    resp = await client.get(
        "/api/audit-logs",
        params={"resource_type": "user", "action": "create"},
        headers=headers,
    )
    assert resp.status_code == 200
    logs = resp.json()
    assert len(logs) >= 1
    assert logs[0]["resource_type"] == "user"
    assert logs[0]["action"] == "create"


@pytest.mark.asyncio
async def test_audit_log_pagination(client: AsyncClient, admin_user):
    headers = await _auth_header(client)
    # First page with limit=1
    resp = await client.get("/api/audit-logs", params={"limit": 1}, headers=headers)
    assert resp.status_code == 200
    page1 = resp.json()
    assert len(page1) <= 1

    if len(page1) == 1:
        cursor = page1[0]["id"]
        resp2 = await client.get(
            "/api/audit-logs", params={"limit": 1, "cursor": cursor}, headers=headers
        )
        assert resp2.status_code == 200
        page2 = resp2.json()
        # If there are more entries, the second page should have different entries
        if len(page2) == 1:
            assert page2[0]["id"] < cursor
