import pytest
from app.models.cluster import Cluster
from app.services import job_service
from app.services.job_worker import execute_job


@pytest.mark.asyncio
async def test_mark_stale_jobs(db_session, admin_user):
    cluster = Cluster(
        name="stale-cluster",
        topology="pss",
        mongodb_version="7.0",
        mongodb_port=37017,
        replicaset_name="rs0",
        config={},
        created_by=admin_user.id,
    )
    db_session.add(cluster)
    await db_session.flush()

    job = await job_service.create_job(
        db_session,
        cluster_id=cluster.id,
        operation="restart_node",
        params={},
        created_by=admin_user.id,
    )
    await job_service.mark_running(db_session, job)
    assert job.status == "running"

    count = await job_service.mark_stale_jobs_failed(db_session)
    assert count == 1

    await db_session.refresh(job)
    assert job.status == "failed"
    assert job.result == {"error": "interrupted by restart"}


@pytest.mark.asyncio
async def test_execute_job_unknown_operation(db_session, admin_user):
    cluster = Cluster(
        name="unknown-op-cluster",
        topology="pss",
        mongodb_version="7.0",
        mongodb_port=37017,
        replicaset_name="rs0",
        config={},
        created_by=admin_user.id,
    )
    db_session.add(cluster)
    await db_session.flush()

    job = await job_service.create_job(
        db_session,
        cluster_id=cluster.id,
        operation="nonexistent_op",
        params={},
        created_by=admin_user.id,
    )

    await execute_job(db_session, job)

    assert job.status == "failed"
    assert "Unknown operation" in job.result["error"]
