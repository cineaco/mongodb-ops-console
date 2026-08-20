import uuid
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.deploy import DeployRequest, RerunRequest
from app.api.schemas.job import (
    CreateUserRequest,
    DeleteUserRequest,
    JobCreatedResponse,
    JobResponse,
    MongodumpS3Request,
    PbmRestoreRequest,
    RestartNodeRequest,
    RotatePasswordRequest,
)
from app.core.database import get_db
from app.core.dependencies import require_role
from app.models.user import User
from app.services import audit_service, job_service
from app.services.cluster_service import get_cluster

router = APIRouter(tags=["jobs"])


def _job_to_response(j) -> JobResponse:
    return JobResponse(
        id=str(j.id),
        cluster_id=str(j.cluster_id),
        operation=j.operation,
        status=j.status,
        params=j.params or {},
        result=j.result,
        started_at=j.started_at,
        completed_at=j.completed_at,
        created_at=j.created_at,
        created_by=str(j.created_by),
    )


def _job_to_created_response(j) -> JobCreatedResponse:
    return JobCreatedResponse(
        job_id=str(j.id),
        operation=j.operation,
        status=j.status,
        created_at=j.created_at,
    )


async def _create_op_job(
    cluster_id: uuid.UUID,
    operation: str,
    params: dict,
    request: Request,
    db: AsyncSession,
    user: User,
) -> JobCreatedResponse:
    cluster = await get_cluster(db, cluster_id)
    if cluster is None:
        raise HTTPException(status_code=404, detail="Cluster not found")

    job = await job_service.create_job(
        db,
        cluster_id=cluster_id,
        operation=operation,
        params=params,
        created_by=user.id,
    )

    await audit_service.record(
        db,
        action=f"job.{operation}",
        user_id=user.id,
        username=user.username,
        resource_type="job",
        resource_id=str(job.id),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    await db.commit()
    return _job_to_created_response(job)


# ---- Generic job endpoints ----


@router.get("/api/clusters/{cluster_id}/jobs", response_model=list[JobResponse])
async def list_cluster_jobs(
    cluster_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role("viewer"))],
    status: Optional[str] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
):
    jobs = await job_service.list_jobs(db, cluster_id=cluster_id, status=status, limit=limit)
    return [_job_to_response(j) for j in jobs]


@router.get("/api/jobs/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role("viewer"))],
):
    job = await job_service.get_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return _job_to_response(job)


@router.post("/api/jobs/{job_id}/cancel", response_model=JobResponse)
async def cancel_job(
    job_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role("operator"))],
):
    job = await job_service.get_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    cancelled = await job_service.cancel_job(db, job)
    if not cancelled:
        raise HTTPException(status_code=409, detail="Job is not in pending state")
    await db.commit()
    return _job_to_response(job)


# ---- Convenience operation endpoints ----


@router.post(
    "/api/clusters/{cluster_id}/ops/restart-node",
    response_model=JobCreatedResponse,
    status_code=201,
)
async def restart_node(
    cluster_id: uuid.UUID,
    body: RestartNodeRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role("operator"))],
):
    return await _create_op_job(
        cluster_id, "restart_node", body.model_dump(), request, db, current_user
    )


@router.post(
    "/api/clusters/{cluster_id}/ops/rolling-restart",
    response_model=JobCreatedResponse,
    status_code=201,
)
async def rolling_restart(
    cluster_id: uuid.UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role("admin"))],
):
    return await _create_op_job(
        cluster_id, "rolling_restart", {}, request, db, current_user
    )


@router.post(
    "/api/clusters/{cluster_id}/ops/rotate-password",
    response_model=JobCreatedResponse,
    status_code=201,
)
async def rotate_password(
    cluster_id: uuid.UUID,
    body: RotatePasswordRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role("admin"))],
):
    return await _create_op_job(
        cluster_id, "rotate_admin_password", body.model_dump(), request, db, current_user
    )


@router.post(
    "/api/clusters/{cluster_id}/ops/create-user",
    response_model=JobCreatedResponse,
    status_code=201,
)
async def create_user_op(
    cluster_id: uuid.UUID,
    body: CreateUserRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role("operator"))],
):
    return await _create_op_job(
        cluster_id, "create_app_user", body.model_dump(), request, db, current_user
    )


@router.post(
    "/api/clusters/{cluster_id}/ops/delete-user",
    response_model=JobCreatedResponse,
    status_code=201,
)
async def delete_user_op(
    cluster_id: uuid.UUID,
    body: DeleteUserRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role("operator"))],
):
    return await _create_op_job(
        cluster_id, "delete_app_user", body.model_dump(), request, db, current_user
    )


@router.post(
    "/api/clusters/{cluster_id}/ops/pbm-backup",
    response_model=JobCreatedResponse,
    status_code=201,
)
async def pbm_backup(
    cluster_id: uuid.UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role("operator"))],
):
    return await _create_op_job(
        cluster_id, "pbm_backup", {}, request, db, current_user
    )


@router.post(
    "/api/clusters/{cluster_id}/ops/pbm-restore",
    response_model=JobCreatedResponse,
    status_code=201,
)
async def pbm_restore(
    cluster_id: uuid.UUID,
    body: PbmRestoreRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role("admin"))],
):
    return await _create_op_job(
        cluster_id, "pbm_restore", body.model_dump(), request, db, current_user
    )


@router.post(
    "/api/clusters/{cluster_id}/ops/pbm-list",
    response_model=JobCreatedResponse,
    status_code=201,
)
async def pbm_list(
    cluster_id: uuid.UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role("operator"))],
):
    return await _create_op_job(
        cluster_id, "pbm_list", {}, request, db, current_user
    )


@router.post(
    "/api/clusters/{cluster_id}/ops/mongodump-s3",
    response_model=JobCreatedResponse,
    status_code=201,
)
async def mongodump_s3(
    cluster_id: uuid.UUID,
    body: MongodumpS3Request,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role("operator"))],
):
    return await _create_op_job(
        cluster_id, "mongodump_s3", body.model_dump(), request, db, current_user
    )


@router.post(
    "/api/clusters/{cluster_id}/ops/deploy",
    response_model=JobCreatedResponse,
    status_code=201,
)
async def op_deploy(
    cluster_id: uuid.UUID,
    body: DeployRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role("admin"))],
):
    return await _create_op_job(
        cluster_id, "deploy", body.model_dump(), request, db, current_user
    )


@router.post(
    "/api/clusters/{cluster_id}/ops/rerun",
    response_model=JobCreatedResponse,
    status_code=201,
)
async def op_rerun(
    cluster_id: uuid.UUID,
    body: RerunRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role("admin"))],
):
    return await _create_op_job(
        cluster_id, "rerun", body.model_dump(), request, db, current_user
    )
