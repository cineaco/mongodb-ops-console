import asyncio
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_factory
from app.models.cluster import Cluster
from app.models.job import Job
from app.services import job_service

logger = logging.getLogger(__name__)

OPERATION_HANDLERS = {}


def _register_handlers():
    from app.services.operations.restart_ops import restart_node, rolling_restart
    from app.services.operations.user_ops import rotate_admin_password, create_app_user, delete_app_user
    from app.services.operations.backup_ops import pbm_backup, pbm_restore, pbm_list, mongodump_s3
    from app.services.operations.deploy_ops import deploy, rerun

    OPERATION_HANDLERS.update({
        "restart_node": restart_node,
        "rolling_restart": rolling_restart,
        "rotate_admin_password": rotate_admin_password,
        "create_app_user": create_app_user,
        "delete_app_user": delete_app_user,
        "pbm_backup": pbm_backup,
        "pbm_restore": pbm_restore,
        "pbm_list": pbm_list,
        "mongodump_s3": mongodump_s3,
        "deploy": deploy,
        "rerun": rerun,
    })


async def execute_job(db: AsyncSession, job: Job) -> None:
    if not OPERATION_HANDLERS:
        _register_handlers()

    handler = OPERATION_HANDLERS.get(job.operation)
    if not handler:
        await job_service.mark_completed(db, job, success=False, result={"error": f"Unknown operation: {job.operation}"})
        return

    result = await db.execute(select(Cluster).where(Cluster.id == job.cluster_id))
    cluster = result.scalar_one_or_none()
    if not cluster:
        await job_service.mark_completed(db, job, success=False, result={"error": "Cluster not found"})
        return

    await job_service.mark_running(db, job)
    await db.flush()

    try:
        if job.operation in ("deploy", "rerun"):
            op_result = await handler(db, cluster, job.params or {}, job_id=job.id)
        else:
            op_result = await handler(db, cluster, job.params or {})
        success = "error" not in op_result
        await job_service.mark_completed(db, job, success=success, result=op_result)
    except Exception as e:
        logger.error(f"Job {job.id} failed with exception: {e}")
        await job_service.mark_completed(db, job, success=False, result={"error": str(e)})


async def process_pending_jobs() -> None:
    async with async_session_factory() as db:
        job = await job_service.get_next_pending_job(db)
        if not job:
            return
        try:
            await execute_job(db, job)
            await db.commit()
        except Exception as e:
            logger.error(f"Error processing job {job.id}: {e}")
            await db.rollback()


async def mark_stale_on_startup() -> None:
    async with async_session_factory() as db:
        count = await job_service.mark_stale_jobs_failed(db)
        await db.commit()
        if count > 0:
            logger.warning(f"Marked {count} stale running jobs as failed")


async def job_worker_loop() -> None:
    logger.info("Job worker started")
    await mark_stale_on_startup()
    while True:
        try:
            await process_pending_jobs()
        except Exception as e:
            logger.error(f"Job worker error: {e}")
        await asyncio.sleep(2)
