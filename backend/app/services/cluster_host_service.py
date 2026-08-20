import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.cluster_host import ClusterHost


async def create_host(
    db: AsyncSession,
    *,
    cluster_id: uuid.UUID,
    hostname: str,
    ip_address: str,
    role: str,
    ssh_user: str = "ubuntu",
    ssh_port: int = 22,
    ssh_key_secret_id: uuid.UUID,
) -> ClusterHost:
    host = ClusterHost(
        cluster_id=cluster_id,
        hostname=hostname,
        ip_address=ip_address,
        role=role,
        ssh_user=ssh_user,
        ssh_port=ssh_port,
        ssh_key_secret_id=ssh_key_secret_id,
    )
    db.add(host)
    await db.flush()
    return host


async def list_hosts(db: AsyncSession, cluster_id: uuid.UUID) -> list[ClusterHost]:
    result = await db.execute(
        select(ClusterHost)
        .where(ClusterHost.cluster_id == cluster_id)
        .order_by(ClusterHost.created_at)
    )
    return list(result.scalars().all())


async def get_host(db: AsyncSession, host_id: uuid.UUID) -> ClusterHost | None:
    result = await db.execute(select(ClusterHost).where(ClusterHost.id == host_id))
    return result.scalar_one_or_none()


async def update_host(db: AsyncSession, host: ClusterHost, **fields) -> ClusterHost:
    for key, value in fields.items():
        if value is None:
            continue
        setattr(host, key, value)
    await db.flush()
    return host


async def delete_host(db: AsyncSession, host: ClusterHost) -> None:
    await db.delete(host)
    await db.flush()
