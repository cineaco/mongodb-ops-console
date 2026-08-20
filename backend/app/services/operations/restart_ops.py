import asyncio
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import decrypt
from app.models.cluster_host import ClusterHost
from app.models.secret import Secret
from app.services import ssh_service

logger = logging.getLogger(__name__)

PRIMARY_ROLES = {"primary", "percona_primary"}


async def _get_host_ssh_info(db: AsyncSession, host_id) -> tuple[ClusterHost, bytes]:
    """Look up a host and decrypt its SSH key."""
    result = await db.execute(select(ClusterHost).where(ClusterHost.id == host_id))
    host = result.scalar_one_or_none()
    if host is None:
        raise ValueError(f"Host {host_id} not found")

    result = await db.execute(select(Secret).where(Secret.id == host.ssh_key_secret_id))
    secret = result.scalar_one_or_none()
    if secret is None:
        raise ValueError(f"Secret {host.ssh_key_secret_id} not found for host {host_id}")

    key_bytes = decrypt(secret.ciphertext, secret.nonce, secret.auth_tag)
    return host, key_bytes


async def restart_node(db: AsyncSession, cluster, params: dict) -> dict:
    """Restart mongod on a single node via SSH."""
    host, key_bytes = await _get_host_ssh_info(db, params["host_id"])

    conn = None
    try:
        conn = await ssh_service.connect(
            host.ip_address, host.ssh_port, host.ssh_user, key_bytes
        )

        # Restart mongod
        exit_code, stdout, stderr = await ssh_service.run_command(
            conn, "sudo systemctl restart mongod", timeout=30
        )
        if exit_code != 0:
            return {
                "status": "error",
                "host": host.hostname,
                "message": f"Restart command failed (exit {exit_code}): {stderr}",
            }

        # Wait for mongod to come up
        await asyncio.sleep(10)

        # Verify mongod is active
        exit_code, stdout, stderr = await ssh_service.run_command(
            conn, "systemctl is-active mongod", timeout=10
        )
        if "active" in stdout:
            return {
                "status": "success",
                "host": host.hostname,
                "message": "mongod restarted and active",
            }
        else:
            return {
                "status": "error",
                "host": host.hostname,
                "message": f"mongod not active after restart: {stdout.strip()}",
            }
    finally:
        if conn is not None:
            await ssh_service.disconnect(conn)


async def rolling_restart(db: AsyncSession, cluster, params: dict) -> dict:
    """Rolling restart: secondaries first, then step-down + restart primary."""
    result = await db.execute(
        select(ClusterHost).where(ClusterHost.cluster_id == cluster.id)
    )
    hosts = list(result.scalars().all())
    if not hosts:
        return {"status": "error", "message": "No hosts found for cluster"}

    primary_hosts = [h for h in hosts if h.role in PRIMARY_ROLES]
    secondary_hosts = [h for h in hosts if h.role not in PRIMARY_ROLES]

    results = []

    # Restart secondaries first
    for host in secondary_hosts:
        node_result = await restart_node(db, cluster, {"host_id": host.id})
        results.append(node_result)
        if node_result["status"] == "error":
            return {
                "status": "error",
                "message": f"Failed on secondary {host.hostname}",
                "results": results,
            }

    # Restart primary: step-down, wait for election, then restart
    for host in primary_hosts:
        # Step-down via PyMongo
        try:
            from pymongo import MongoClient

            _, key_bytes = await _get_host_ssh_info(db, host.id)
            mongo_uri = f"mongodb://{host.ip_address}:{cluster.mongodb_port}"
            mongo_client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
            try:
                mongo_client.admin.command("replSetStepDown", 60)
            except Exception:
                # stepDown often raises an error as the connection is dropped
                pass
            finally:
                mongo_client.close()

            await asyncio.sleep(15)
        except ImportError:
            logger.warning("pymongo not available; skipping stepdown for %s", host.hostname)

        node_result = await restart_node(db, cluster, {"host_id": host.id})
        results.append(node_result)
        if node_result["status"] == "error":
            return {
                "status": "error",
                "message": f"Failed on primary {host.hostname}",
                "results": results,
            }

    return {"status": "success", "results": results}
