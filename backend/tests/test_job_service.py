import pytest
from app.models.cluster import Cluster
from app.services import job_service


@pytest.mark.asyncio
async def test_create_job(db_session, admin_user):
    cluster = Cluster(
        name="c1",
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
        params={"node": "primary"},
        created_by=admin_user.id,
    )
    assert job.status == "pending"
    assert job.operation == "restart_node"
    assert job.cluster_id == cluster.id


@pytest.mark.asyncio
async def test_get_next_pending(db_session, admin_user):
    cluster = Cluster(
        name="c2",
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
        operation="pbm_backup",
        params={},
        created_by=admin_user.id,
    )

    pending = await job_service.get_next_pending_job(db_session)
    assert pending is not None
    assert pending.id == job.id


@pytest.mark.asyncio
async def test_mark_running_and_completed(db_session, admin_user):
    cluster = Cluster(
        name="c3",
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
    assert job.status == "pending"

    await job_service.mark_running(db_session, job)
    assert job.status == "running"
    assert job.started_at is not None

    await job_service.mark_completed(
        db_session, job, success=True, result={"ok": True}
    )
    assert job.status == "success"
    assert job.completed_at is not None
    assert job.result == {"ok": True}


@pytest.mark.asyncio
async def test_cancel_pending_job(db_session, admin_user):
    cluster = Cluster(
        name="c4",
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
        operation="pbm_list",
        params={},
        created_by=admin_user.id,
    )
    cancelled = await job_service.cancel_job(db_session, job)
    assert cancelled is True
    assert job.status == "cancelled"
    assert job.completed_at is not None


@pytest.mark.asyncio
async def test_cannot_cancel_running_job(db_session, admin_user):
    cluster = Cluster(
        name="c5",
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
        operation="rolling_restart",
        params={},
        created_by=admin_user.id,
    )
    await job_service.mark_running(db_session, job)

    cancelled = await job_service.cancel_job(db_session, job)
    assert cancelled is False
    assert job.status == "running"


@pytest.mark.asyncio
async def test_list_jobs_filtered(db_session, admin_user):
    cluster_a = Cluster(
        name="cA",
        topology="pss",
        mongodb_version="7.0",
        mongodb_port=37017,
        replicaset_name="rs0",
        config={},
        created_by=admin_user.id,
    )
    cluster_b = Cluster(
        name="cB",
        topology="psa",
        mongodb_version="7.0",
        mongodb_port=37017,
        replicaset_name="rs0",
        config={},
        created_by=admin_user.id,
    )
    db_session.add_all([cluster_a, cluster_b])
    await db_session.flush()

    await job_service.create_job(
        db_session,
        cluster_id=cluster_a.id,
        operation="restart_node",
        params={},
        created_by=admin_user.id,
    )
    await job_service.create_job(
        db_session,
        cluster_id=cluster_b.id,
        operation="pbm_backup",
        params={},
        created_by=admin_user.id,
    )

    jobs_a = await job_service.list_jobs(db_session, cluster_id=cluster_a.id)
    assert len(jobs_a) == 1
    assert jobs_a[0].cluster_id == cluster_a.id

    all_jobs = await job_service.list_jobs(db_session)
    assert len(all_jobs) == 2
