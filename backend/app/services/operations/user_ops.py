import logging

from pymongo import MongoClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.core.config import settings
from app.core.crypto import decrypt
from app.models.cluster import Cluster
from app.models.cluster_host import ClusterHost
from app.models.secret import Secret

logger = logging.getLogger(__name__)

PRIMARY_ROLES = {"primary", "percona_primary"}


async def _get_primary_uri(db: AsyncSession, cluster: Cluster) -> tuple[str, str]:
    """Build a MongoDB URI targeting the primary node with admin credentials.

    Returns (uri, admin_username).
    """
    # --- admin credentials ---------------------------------------------------
    if cluster.admin_credentials_secret_id is None:
        raise ValueError("Cluster has no admin credentials secret configured")

    result = await db.execute(
        select(Secret).where(Secret.id == cluster.admin_credentials_secret_id)
    )
    secret = result.scalar_one_or_none()
    if secret is None:
        raise ValueError(
            f"Admin credentials secret {cluster.admin_credentials_secret_id} not found"
        )

    creds_raw = decrypt(secret.ciphertext, secret.nonce, secret.auth_tag)
    # Credentials stored as "username:password"
    creds_text = creds_raw.decode()
    if ":" not in creds_text:
        raise ValueError("Admin credentials secret must be in 'username:password' format")
    username, password = creds_text.split(":", 1)

    # --- primary host --------------------------------------------------------
    result = await db.execute(
        select(ClusterHost).where(
            ClusterHost.cluster_id == cluster.id,
            ClusterHost.role.in_(PRIMARY_ROLES),
        )
    )
    host = result.scalar_one_or_none()
    if host is None:
        raise ValueError(f"No primary host found for cluster {cluster.id}")

    uri = (
        f"mongodb://{username}:{password}@{host.ip_address}"
        f":{cluster.mongodb_port}/admin?authSource=admin"
    )
    return uri, username


async def rotate_admin_password(
    db: AsyncSession, cluster: Cluster, params: dict
) -> dict:
    """Rotate the MongoDB admin password on the primary node."""
    new_secret_id = params["new_password_secret_id"]

    # Decrypt new password
    result = await db.execute(select(Secret).where(Secret.id == new_secret_id))
    new_secret = result.scalar_one_or_none()
    if new_secret is None:
        raise ValueError(f"New password secret {new_secret_id} not found")

    new_creds_raw = decrypt(
        new_secret.ciphertext, new_secret.nonce, new_secret.auth_tag
    )
    new_creds_text = new_creds_raw.decode()
    if ":" not in new_creds_text:
        raise ValueError("New credentials secret must be in 'username:password' format")
    _, new_password = new_creds_text.split(":", 1)

    # Get current URI
    uri, admin_username = await _get_primary_uri(db, cluster)

    # Update the password on MongoDB
    def _update():
        client = MongoClient(uri, serverSelectionTimeoutMS=settings.POLLER_TIMEOUT_SECONDS * 1000)
        try:
            client.admin.command("updateUser", admin_username, pwd=new_password)
        finally:
            client.close()

    await run_in_threadpool(_update)

    # Persist the new secret reference
    cluster.admin_credentials_secret_id = new_secret_id
    db.add(cluster)
    await db.commit()

    return {"status": "success", "message": "Admin password rotated successfully"}


async def create_app_user(
    db: AsyncSession, cluster: Cluster, params: dict
) -> dict:
    """Create an application user on the target database."""
    database = params["database"]
    username = params["username"]
    password_secret_id = params["password_secret_id"]
    roles = params.get("roles", [{"role": "readWrite", "db": database}])

    # Decrypt the app password
    result = await db.execute(select(Secret).where(Secret.id == password_secret_id))
    secret = result.scalar_one_or_none()
    if secret is None:
        raise ValueError(f"Password secret {password_secret_id} not found")
    password = decrypt(secret.ciphertext, secret.nonce, secret.auth_tag).decode()

    uri, _ = await _get_primary_uri(db, cluster)

    def _create():
        client = MongoClient(uri, serverSelectionTimeoutMS=settings.POLLER_TIMEOUT_SECONDS * 1000)
        try:
            client[database].command(
                "createUser", username, pwd=password, roles=roles
            )
        finally:
            client.close()

    await run_in_threadpool(_create)

    return {"database": database, "username": username, "roles": roles}


async def delete_app_user(
    db: AsyncSession, cluster: Cluster, params: dict
) -> dict:
    """Drop an application user from the target database."""
    database = params["database"]
    username = params["username"]

    uri, _ = await _get_primary_uri(db, cluster)

    def _drop():
        client = MongoClient(uri, serverSelectionTimeoutMS=settings.POLLER_TIMEOUT_SECONDS * 1000)
        try:
            client[database].command("dropUser", username)
        finally:
            client.close()

    await run_in_threadpool(_drop)

    return {"database": database, "username": username}
