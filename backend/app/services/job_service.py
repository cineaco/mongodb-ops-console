import uuid
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import Job

ADMIN_ONLY_OPERATIONS = {"rolling_restart", "rotate_admin_password", "pbm_restore", "deploy", "rerun"}
ALL_OPERATIONS = {
    "restart_node",
    "rolling_restart",
    "rotate_admin_password",
    "create_app_user",
    "delete_app_user",
    "pbm_backup",
    "pbm_restore",
    "pbm_list",
    "mongodump_s3",
    "deploy",
    "rerun",
}


async def create_job(
    db: AsyncSession,
    *,
    cluster_id: uuid.UUID,
    operation: str,
    params: dict | None = None,
    created_by: uuid.UUID,
) -> Job:
    job = Job(
        cluster_id=cluster_id,
        operation=operation,
        status="pending",
        params=params or {},
        created_by=created_by,
    )
    db.add(job)
    await db.flush()
    return job


async def get_job(db: AsyncSession, job_id: uuid.UUID) -> Job | None:
    result = await db.execute(select(Job).where(Job.id == job_id))
    return result.scalar_one_or_none()


async def list_jobs(
    db: AsyncSession,
    *,
    cluster_id: uuid.UUID | None = None,
    status: str | None = None,
    limit: int = 20,
) -> list[Job]:
    stmt = select(Job)
    if cluster_id is not None:
        stmt = stmt.where(Job.cluster_id == cluster_id)
    if status is not None:
        stmt = stmt.where(Job.status == status)
    stmt = stmt.order_by(Job.created_at.desc()).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_next_pending_job(db: AsyncSession) -> Job | None:
    stmt = (
        select(Job)
        .where(Job.status == "pending")
        .order_by(Job.created_at.asc())
        .limit(1)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def mark_running(db: AsyncSession, job: Job) -> None:
    job.status = "running"
    job.started_at = datetime.now(timezone.utc)
    await db.flush()


async def mark_completed(
    db: AsyncSession, job: Job, *, success: bool, result: dict | None = None
) -> None:
    job.status = "success" if success else "failed"
    job.result = result
    job.completed_at = datetime.now(timezone.utc)
    await db.flush()


async def cancel_job(db: AsyncSession, job: Job) -> bool:
    if job.status != "pending":
        return False
    job.status = "cancelled"
    job.completed_at = datetime.now(timezone.utc)
    await db.flush()
    return True


async def mark_stale_jobs_failed(db: AsyncSession) -> int:
    stmt = (
        update(Job)
        .where(Job.status == "running")
        .values(
            status="failed",
            result={"error": "interrupted by restart"},
            completed_at=datetime.now(timezone.utc),
        )
    )
    result = await db.execute(stmt)
    await db.flush()
    return result.rowcount
