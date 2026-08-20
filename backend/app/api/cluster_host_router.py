import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.cluster_host import HostCreate, HostResponse, HostUpdate
from app.core.database import get_db
from app.core.dependencies import require_role
from app.models.user import User
from app.services import audit_service, cluster_host_service, cluster_service

router = APIRouter(prefix="/api/clusters/{cluster_id}/hosts", tags=["cluster-hosts"])


def _host_to_response(h) -> HostResponse:
    return HostResponse(
        id=str(h.id),
        cluster_id=str(h.cluster_id),
        hostname=h.hostname,
        ip_address=h.ip_address,
        role=h.role,
        ssh_user=h.ssh_user,
        ssh_port=h.ssh_port,
        ssh_key_secret_id=str(h.ssh_key_secret_id),
        created_at=h.created_at,
    )


async def _get_cluster_or_404(db: AsyncSession, cluster_id: uuid.UUID):
    cluster = await cluster_service.get_cluster(db, cluster_id)
    if cluster is None:
        raise HTTPException(status_code=404, detail="Cluster not found")
    return cluster


@router.get("", response_model=list[HostResponse])
async def list_hosts(
    cluster_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role("viewer"))],
):
    await _get_cluster_or_404(db, cluster_id)
    hosts = await cluster_host_service.list_hosts(db, cluster_id)
    return [_host_to_response(h) for h in hosts]


@router.post("", response_model=HostResponse, status_code=201)
async def create_host(
    cluster_id: uuid.UUID,
    body: HostCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role("operator"))],
):
    await _get_cluster_or_404(db, cluster_id)
    host = await cluster_host_service.create_host(
        db,
        cluster_id=cluster_id,
        hostname=body.hostname,
        ip_address=body.ip_address,
        role=body.role,
        ssh_user=body.ssh_user,
        ssh_port=body.ssh_port,
        ssh_key_secret_id=uuid.UUID(body.ssh_key_secret_id),
    )
    await audit_service.record(
        db,
        action="create",
        user_id=current_user.id,
        username=current_user.username,
        resource_type="host",
        resource_id=str(host.id),
    )
    await db.commit()
    return _host_to_response(host)


@router.patch("/{host_id}", response_model=HostResponse)
async def update_host(
    cluster_id: uuid.UUID,
    host_id: uuid.UUID,
    body: HostUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role("operator"))],
):
    await _get_cluster_or_404(db, cluster_id)
    host = await cluster_host_service.get_host(db, host_id)
    if host is None or host.cluster_id != cluster_id:
        raise HTTPException(status_code=404, detail="Host not found")
    fields = body.model_dump(exclude_unset=True)
    if "ssh_key_secret_id" in fields and fields["ssh_key_secret_id"] is not None:
        fields["ssh_key_secret_id"] = uuid.UUID(fields["ssh_key_secret_id"])
    host = await cluster_host_service.update_host(db, host, **fields)
    await audit_service.record(
        db,
        action="update",
        user_id=current_user.id,
        username=current_user.username,
        resource_type="host",
        resource_id=str(host.id),
    )
    await db.commit()
    return _host_to_response(host)


@router.delete("/{host_id}", status_code=204)
async def delete_host(
    cluster_id: uuid.UUID,
    host_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role("operator"))],
):
    await _get_cluster_or_404(db, cluster_id)
    host = await cluster_host_service.get_host(db, host_id)
    if host is None or host.cluster_id != cluster_id:
        raise HTTPException(status_code=404, detail="Host not found")
    await cluster_host_service.delete_host(db, host)
    await audit_service.record(
        db,
        action="delete",
        user_id=current_user.id,
        username=current_user.username,
        resource_type="host",
        resource_id=str(host_id),
    )
    await db.commit()
