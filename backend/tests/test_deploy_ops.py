import uuid

import pytest
from unittest.mock import patch, AsyncMock

from app.core.crypto import encrypt
from app.models.cluster import Cluster
from app.models.cluster_host import ClusterHost
from app.models.secret import Secret
from app.services.operations.deploy_ops import deploy, rerun


async def _setup_deployable_cluster(db_session, admin_user):
    """Create a standalone cluster with 1 host, SSH key secret, and admin password secret."""
    # SSH key secret
    key_bytes = b"-----BEGIN OPENSSH PRIVATE KEY-----\nfake\n-----END OPENSSH PRIVATE KEY-----"
    ct, nonce, tag = encrypt(key_bytes)
    ssh_secret = Secret(
        name=f"deploy-ssh-{uuid.uuid4().hex[:8]}",
        type="ssh_key",
        ciphertext=ct,
        nonce=nonce,
        auth_tag=tag,
        created_by=admin_user.id,
    )
    db_session.add(ssh_secret)
    await db_session.flush()

    # Admin password secret
    admin_pw = b"AdminPass123"
    ct2, nonce2, tag2 = encrypt(admin_pw)
    admin_secret = Secret(
        name=f"deploy-admin-{uuid.uuid4().hex[:8]}",
        type="admin_password",
        ciphertext=ct2,
        nonce=nonce2,
        auth_tag=tag2,
        created_by=admin_user.id,
    )
    db_session.add(admin_secret)
    await db_session.flush()

    cluster = Cluster(
        name=f"deploy-cluster-{uuid.uuid4().hex[:8]}",
        topology="standalone",
        mongodb_version="8.0",
        mongodb_port=37017,
        replicaset_name="rs0",
        config={},
        status="pending",
        admin_credentials_secret_id=admin_secret.id,
        created_by=admin_user.id,
    )
    db_session.add(cluster)
    await db_session.flush()

    host = ClusterHost(
        cluster_id=cluster.id,
        hostname="mongo-standalone",
        ip_address="10.0.0.10",
        role="primary",
        ssh_user="ubuntu",
        ssh_port=22,
        ssh_key_secret_id=ssh_secret.id,
    )
    db_session.add(host)
    await db_session.commit()

    return cluster


@pytest.mark.asyncio
async def test_deploy_success(db_session, admin_user):
    cluster = await _setup_deployable_cluster(db_session, admin_user)

    with patch("app.services.operations.deploy_ops._run_ansible_playbook", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = (0, "PLAY RECAP ... ok=5\n")

        result = await deploy(db_session, cluster, {}, job_id=uuid.uuid4())

    assert "message" in result
    assert "successfully" in result["message"]
    assert result["exit_code"] == 0
    assert cluster.status == "healthy"
    assert cluster.last_deployed_at is not None


@pytest.mark.asyncio
async def test_deploy_failure(db_session, admin_user):
    cluster = await _setup_deployable_cluster(db_session, admin_user)

    with patch("app.services.operations.deploy_ops._run_ansible_playbook", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = (2, "fatal: UNREACHABLE\n")

        result = await deploy(db_session, cluster, {}, job_id=uuid.uuid4())

    assert "error" in result
    assert result["exit_code"] == 2
    assert cluster.status == "failed"


@pytest.mark.asyncio
async def test_rerun_no_tags_returns_error(db_session, admin_user):
    cluster = await _setup_deployable_cluster(db_session, admin_user)

    result = await rerun(db_session, cluster, {"tags": []})

    assert "error" in result
    assert "tags" in result["error"]
