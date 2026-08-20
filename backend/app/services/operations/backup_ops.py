import asyncio
import json
import logging
import time

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import decrypt
from app.models.cluster import Cluster
from app.models.cluster_host import ClusterHost
from app.models.secret import Secret
from app.services import ssh_service

logger = logging.getLogger(__name__)

PRIMARY_ROLES = {"primary", "percona_primary"}

# Polling / timeout defaults (seconds)
_POLL_INTERVAL = 5
_BACKUP_TIMEOUT = 30 * 60   # 30 minutes
_RESTORE_TIMEOUT = 60 * 60  # 60 minutes


async def _get_any_host_ssh(
    db: AsyncSession, cluster: Cluster
) -> tuple[ClusterHost, bytes]:
    """Get any host from the cluster and decrypt its SSH key."""
    result = await db.execute(
        select(ClusterHost).where(ClusterHost.cluster_id == cluster.id)
    )
    host = result.scalars().first()
    if host is None:
        raise ValueError(f"No hosts found for cluster {cluster.id}")

    result = await db.execute(
        select(Secret).where(Secret.id == host.ssh_key_secret_id)
    )
    secret = result.scalar_one_or_none()
    if secret is None:
        raise ValueError(
            f"SSH key secret {host.ssh_key_secret_id} not found for host {host.hostname}"
        )

    key_bytes = decrypt(secret.ciphertext, secret.nonce, secret.auth_tag)
    return host, key_bytes


async def pbm_backup(
    db: AsyncSession, cluster: Cluster, params: dict
) -> dict:
    """Start a PBM backup and poll until completion."""
    host, key_bytes = await _get_any_host_ssh(db, cluster)

    conn = None
    try:
        conn = await ssh_service.connect(
            host.ip_address, host.ssh_port, host.ssh_user, key_bytes
        )

        # Start backup
        exit_code, stdout, stderr = await ssh_service.run_command(
            conn, "sudo pbm backup", timeout=30
        )
        if exit_code != 0:
            return {
                "status": "error",
                "message": f"pbm backup failed (exit {exit_code}): {stderr or stdout}",
            }

        # Parse backup name from stdout (e.g. "Starting backup '2024-01-01T00:00:00Z'...")
        backup_name = stdout.strip()

        # Poll until done
        start = time.monotonic()
        while (time.monotonic() - start) < _BACKUP_TIMEOUT:
            await asyncio.sleep(_POLL_INTERVAL)
            exit_code, stdout, stderr = await ssh_service.run_command(
                conn, "sudo pbm status", timeout=30
            )
            if "done" in stdout.lower():
                duration = int(time.monotonic() - start)
                return {
                    "status": "success",
                    "message": "Backup completed successfully",
                    "backup_name": backup_name,
                    "duration_seconds": duration,
                }

        return {
            "status": "error",
            "message": "Backup timed out waiting for completion",
        }
    finally:
        if conn is not None:
            await ssh_service.disconnect(conn)


async def pbm_restore(
    db: AsyncSession, cluster: Cluster, params: dict
) -> dict:
    """Restore from a PBM backup using a point-in-time timestamp."""
    timestamp = params["timestamp"]
    host, key_bytes = await _get_any_host_ssh(db, cluster)

    conn = None
    try:
        conn = await ssh_service.connect(
            host.ip_address, host.ssh_port, host.ssh_user, key_bytes
        )

        # Start restore
        exit_code, stdout, stderr = await ssh_service.run_command(
            conn, f"sudo pbm restore --time={timestamp}", timeout=60
        )
        if exit_code != 0:
            return {
                "status": "error",
                "message": f"pbm restore failed (exit {exit_code}): {stderr or stdout}",
            }

        # Poll until done
        start = time.monotonic()
        while (time.monotonic() - start) < _RESTORE_TIMEOUT:
            await asyncio.sleep(_POLL_INTERVAL)
            exit_code, stdout, stderr = await ssh_service.run_command(
                conn, "sudo pbm status", timeout=30
            )
            if "done" in stdout.lower():
                duration = int(time.monotonic() - start)
                return {
                    "status": "success",
                    "message": "Restore completed successfully",
                    "restored_to": timestamp,
                    "duration_seconds": duration,
                }

        return {
            "status": "error",
            "message": "Restore timed out waiting for completion",
        }
    finally:
        if conn is not None:
            await ssh_service.disconnect(conn)


async def pbm_list(
    db: AsyncSession, cluster: Cluster, params: dict
) -> dict:
    """List PBM backups, attempting JSON output first then plain text fallback."""
    host, key_bytes = await _get_any_host_ssh(db, cluster)

    conn = None
    try:
        conn = await ssh_service.connect(
            host.ip_address, host.ssh_port, host.ssh_user, key_bytes
        )

        # Try JSON output first
        exit_code, stdout, stderr = await ssh_service.run_command(
            conn, "sudo pbm list --output=json", timeout=30
        )
        if exit_code == 0:
            try:
                backups = json.loads(stdout)
                return {
                    "status": "success",
                    "message": "Backups retrieved",
                    "backups": backups,
                }
            except json.JSONDecodeError:
                pass

        # Fallback to plain text
        exit_code, stdout, stderr = await ssh_service.run_command(
            conn, "sudo pbm list", timeout=30
        )
        if exit_code != 0:
            return {
                "status": "error",
                "message": f"pbm list failed (exit {exit_code}): {stderr or stdout}",
            }

        return {
            "status": "success",
            "message": "Backups retrieved",
            "backups": stdout.strip(),
        }
    finally:
        if conn is not None:
            await ssh_service.disconnect(conn)


async def mongodump_s3(
    db: AsyncSession, cluster: Cluster, params: dict
) -> dict:
    """Run mongodump and stream the archive directly to S3."""
    s3_bucket = params["s3_bucket"]
    s3_prefix = params.get("s3_prefix", "backups")
    s3_region = params.get("s3_region", "us-east-1")
    s3_auth_method = params.get("s3_auth_method", "iam_role")
    s3_credential_secret_id = params.get("s3_credential_secret_id")

    # Build MongoDB URI from admin credentials
    if cluster.admin_credentials_secret_id is None:
        raise ValueError("Cluster has no admin credentials secret configured")

    result = await db.execute(
        select(Secret).where(Secret.id == cluster.admin_credentials_secret_id)
    )
    admin_secret = result.scalar_one_or_none()
    if admin_secret is None:
        raise ValueError("Admin credentials secret not found")

    creds_raw = decrypt(
        admin_secret.ciphertext, admin_secret.nonce, admin_secret.auth_tag
    )
    creds_text = creds_raw.decode()
    if ":" not in creds_text:
        raise ValueError("Admin credentials must be in 'username:password' format")
    username, password = creds_text.split(":", 1)

    # Get primary host for URI
    result = await db.execute(
        select(ClusterHost).where(
            ClusterHost.cluster_id == cluster.id,
            ClusterHost.role.in_(PRIMARY_ROLES),
        )
    )
    primary = result.scalar_one_or_none()
    if primary is None:
        raise ValueError(f"No primary host found for cluster {cluster.id}")

    uri = (
        f"mongodb://{username}:{password}@{primary.ip_address}"
        f":{cluster.mongodb_port}/admin?authSource=admin"
    )

    # Build env prefix for S3 credentials
    env_prefix = ""
    if s3_auth_method == "secret":
        if s3_credential_secret_id is None:
            raise ValueError("s3_credential_secret_id required when s3_auth_method is 'secret'")
        result = await db.execute(
            select(Secret).where(Secret.id == s3_credential_secret_id)
        )
        s3_secret = result.scalar_one_or_none()
        if s3_secret is None:
            raise ValueError(f"S3 credential secret {s3_credential_secret_id} not found")
        s3_creds = decrypt(
            s3_secret.ciphertext, s3_secret.nonce, s3_secret.auth_tag
        ).decode()
        if ":" not in s3_creds:
            raise ValueError("S3 credentials must be in 'ACCESS_KEY:SECRET_KEY' format")
        access_key, secret_key = s3_creds.split(":", 1)
        env_prefix = f"AWS_ACCESS_KEY_ID={access_key} AWS_SECRET_ACCESS_KEY={secret_key} AWS_DEFAULT_REGION={s3_region} "

    # Use any host (preferably the one we already have SSH to)
    host, key_bytes = await _get_any_host_ssh(db, cluster)

    timestamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    s3_path = f"s3://{s3_bucket}/{s3_prefix}/{timestamp}.archive"
    cmd = (
        f'{env_prefix}mongodump --uri="{uri}" --archive'
        f" | aws s3 cp - {s3_path}"
    )

    conn = None
    start = time.monotonic()
    try:
        conn = await ssh_service.connect(
            host.ip_address, host.ssh_port, host.ssh_user, key_bytes
        )

        exit_code, stdout, stderr = await ssh_service.run_command(
            conn, cmd, timeout=_BACKUP_TIMEOUT
        )
        duration = int(time.monotonic() - start)

        if exit_code != 0:
            return {
                "status": "error",
                "message": f"mongodump to S3 failed (exit {exit_code}): {stderr or stdout}",
            }

        return {
            "status": "success",
            "message": "mongodump to S3 completed",
            "s3_path": s3_path,
            "duration_seconds": duration,
        }
    finally:
        if conn is not None:
            await ssh_service.disconnect(conn)
