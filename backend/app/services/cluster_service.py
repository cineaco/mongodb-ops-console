import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.cluster import Cluster


async def create_cluster(
    db: AsyncSession,
    *,
    name: str,
    description: str | None = None,
    topology: str,
    mongodb_version: str,
    mongodb_port: int = 37017,
    replicaset_name: str = "rs0",
    config: dict | None = None,
    admin_credentials_secret_id: uuid.UUID | None = None,
    created_by: uuid.UUID,
) -> Cluster:
    cluster = Cluster(
        name=name,
        description=description,
        topology=topology,
        mongodb_version=mongodb_version,
        mongodb_port=mongodb_port,
        replicaset_name=replicaset_name,
        config=config or {},
        admin_credentials_secret_id=admin_credentials_secret_id,
        created_by=created_by,
    )
    db.add(cluster)
    await db.flush()
    return cluster


async def list_clusters(db: AsyncSession) -> list[Cluster]:
    result = await db.execute(select(Cluster).order_by(Cluster.created_at.desc()))
    return list(result.scalars().all())


async def get_cluster(db: AsyncSession, cluster_id: uuid.UUID) -> Cluster | None:
    result = await db.execute(select(Cluster).where(Cluster.id == cluster_id))
    return result.scalar_one_or_none()


async def update_cluster(db: AsyncSession, cluster: Cluster, **fields) -> Cluster:
    for key, value in fields.items():
        if value is None:
            continue
        if key == "config":
            # MERGE into existing config, not replace
            merged = dict(cluster.config or {})
            merged.update(value)
            cluster.config = merged
        else:
            setattr(cluster, key, value)
    await db.flush()
    return cluster


async def delete_cluster(db: AsyncSession, cluster: Cluster) -> None:
    await db.delete(cluster)
    await db.flush()
