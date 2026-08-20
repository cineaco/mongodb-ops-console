import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from app.services import ssh_service


@pytest.mark.asyncio
async def test_connect():
    fake_key = MagicMock()
    fake_conn = AsyncMock()

    with patch("app.services.ssh_service.asyncssh.import_private_key", return_value=fake_key) as mock_import, \
         patch("app.services.ssh_service.asyncssh.connect", new_callable=AsyncMock, return_value=fake_conn) as mock_connect:

        conn = await ssh_service.connect("10.0.0.1", 22, "ubuntu", b"-----BEGIN KEY-----\nfake\n-----END KEY-----")

        mock_import.assert_called_once_with("-----BEGIN KEY-----\nfake\n-----END KEY-----")
        mock_connect.assert_called_once_with(
            "10.0.0.1",
            port=22,
            username="ubuntu",
            client_keys=[fake_key],
            known_hosts=None,
            connect_timeout=10,
        )
        assert conn is fake_conn


@pytest.mark.asyncio
async def test_run_command():
    mock_result = MagicMock()
    mock_result.exit_status = 0
    mock_result.stdout = "hello\n"
    mock_result.stderr = ""

    mock_conn = AsyncMock()
    mock_conn.run = MagicMock(return_value=mock_result)

    with patch("app.services.ssh_service.asyncio.wait_for", new_callable=AsyncMock, return_value=mock_result):
        exit_code, stdout, stderr = await ssh_service.run_command(mock_conn, "echo hello")

    assert exit_code == 0
    assert stdout == "hello\n"
    assert stderr == ""


@pytest.mark.asyncio
async def test_disconnect():
    mock_conn = AsyncMock()
    mock_conn.close = MagicMock()
    mock_conn.wait_closed = AsyncMock()

    await ssh_service.disconnect(mock_conn)

    mock_conn.close.assert_called_once()
    mock_conn.wait_closed.assert_awaited_once()
