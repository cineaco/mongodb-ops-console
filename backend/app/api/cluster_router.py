import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.cluster import ClusterCreate, ClusterResponse, ClusterUpdate
from app.core.database import get_db
from app.core.dependencies import require_role
from app.models.user import User
from app.services import audit_service, cluster_service

router = APIRouter(prefix="/api/clusters", tags=["clusters"])


def _cluster_to_response(c) -> ClusterResponse:
    return ClusterResponse(
        id=str(c.id),
        name=c.name,
        description=c.description,
        topology=c.topology,
        mongodb_version=c.mongodb_version,
        mongodb_port=c.mongodb_port,
        replicaset_name=c.replicaset_name,
        config=c.config or {},
        status=c.status,
        admin_credentials_secret_id=str(c.admin_credentials_secret_id) if c.admin_credentials_secret_id else None,
        last_deployed_at=c.last_deployed_at,
        last_deployed_by=str(c.last_deployed_by) if c.last_deployed_by else None,
        created_at=c.created_at,
        created_by=str(c.created_by),
    )


@router.get("", response_model=list[ClusterResponse])
async def list_clusters(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role("viewer"))],
):
    clusters = await cluster_service.list_clusters(db)
    return [_cluster_to_response(c) for c in clusters]


@router.post("", response_model=ClusterResponse, status_code=201)
async def create_cluster(
    body: ClusterCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role("operator"))],
):
    secret_id = uuid.UUID(body.admin_credentials_secret_id) if body.admin_credentials_secret_id else None
    cluster = await cluster_service.create_cluster(
        db,
        name=body.name,
        description=body.description,
        topology=body.topology,
        mongodb_version=body.mongodb_version,
        mongodb_port=body.mongodb_port,
        replicaset_name=body.replicaset_name,
        config=body.config,
        admin_credentials_secret_id=secret_id,
        created_by=current_user.id,
    )
    await audit_service.record(
        db,
        action="create",
        user_id=current_user.id,
        username=current_user.username,
        resource_type="cluster",
        resource_id=str(cluster.id),
    )
    await db.commit()
    return _cluster_to_response(cluster)


@router.get("/{cluster_id}", response_model=ClusterResponse)
async def get_cluster(
    cluster_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role("viewer"))],
):
    cluster = await cluster_service.get_cluster(db, cluster_id)
    if cluster is None:
        raise HTTPException(status_code=404, detail="Cluster not found")
    return _cluster_to_response(cluster)


@router.patch("/{cluster_id}", response_model=ClusterResponse)
async def update_cluster(
    cluster_id: uuid.UUID,
    body: ClusterUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role("operator"))],
):
    cluster = await cluster_service.get_cluster(db, cluster_id)
    if cluster is None:
        raise HTTPException(status_code=404, detail="Cluster not found")
    fields = body.model_dump(exclude_unset=True)
    # Convert admin_credentials_secret_id string to UUID if present
    if "admin_credentials_secret_id" in fields and fields["admin_credentials_secret_id"] is not None:
        fields["admin_credentials_secret_id"] = uuid.UUID(fields["admin_credentials_secret_id"])
    cluster = await cluster_service.update_cluster(db, cluster, **fields)
    await audit_service.record(
        db,
        action="update",
        user_id=current_user.id,
        username=current_user.username,
        resource_type="cluster",
        resource_id=str(cluster.id),
    )
    await db.commit()
    return _cluster_to_response(cluster)


@router.delete("/{cluster_id}", status_code=204)
async def delete_cluster(
    cluster_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role("admin"))],
):
    cluster = await cluster_service.get_cluster(db, cluster_id)
    if cluster is None:
        raise HTTPException(status_code=404, detail="Cluster not found")
    await cluster_service.delete_cluster(db, cluster)
    await audit_service.record(
        db,
        action="delete",
        user_id=current_user.id,
        username=current_user.username,
        resource_type="cluster",
        resource_id=str(cluster_id),
    )
    await db.commit()
