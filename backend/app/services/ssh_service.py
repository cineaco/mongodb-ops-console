import asyncio
import logging
import asyncssh

logger = logging.getLogger(__name__)


async def connect(host: str, port: int, username: str, private_key_bytes: bytes) -> asyncssh.SSHClientConnection:
    key = asyncssh.import_private_key(private_key_bytes.decode("utf-8"))
    conn = await asyncssh.connect(host, port=port, username=username, client_keys=[key], known_hosts=None, connect_timeout=10)
    return conn


async def run_command(conn: asyncssh.SSHClientConnection, command: str, timeout: int = 60) -> tuple[int, str, str]:
    result = await asyncio.wait_for(conn.run(command, check=False), timeout=timeout)
    exit_code = result.exit_status or 0
    stdout = result.stdout or ""
    stderr = result.stderr or ""
    if len(stderr) > 4096:
        stderr = stderr[:4096] + "\n... (truncated)"
    return exit_code, stdout, stderr


async def disconnect(conn: asyncssh.SSHClientConnection) -> None:
    conn.close()
    await conn.wait_closed()
