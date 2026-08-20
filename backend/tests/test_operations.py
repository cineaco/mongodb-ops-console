import uuid

import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from app.core.crypto import encrypt
from app.models.cluster import Cluster
from app.models.cluster_host import ClusterHost
from app.models.secret import Secret
from app.services.operations.backup_ops import pbm_list, pbm_backup
from app.services.operations.restart_ops import restart_node
from app.services.operations.user_ops import create_app_user, delete_app_user


async def _setup_cluster_and_host(db_session, admin_user):
    """Create a cluster, SSH key secret, and host for testing."""
    key_bytes = b"-----BEGIN OPENSSH PRIVATE KEY-----\nfake\n-----END OPENSSH PRIVATE KEY-----"
    ciphertext, nonce, auth_tag = encrypt(key_bytes)

    secret = Secret(
        name="test-ssh-key",
        type="ssh_key",
        ciphertext=ciphertext,
        nonce=nonce,
        auth_tag=auth_tag,
        created_by=admin_user.id,
    )
    db_session.add(secret)
    await db_session.flush()

    cluster = Cluster(
        name=f"test-cluster-{uuid.uuid4().hex[:8]}",
        topology="pss",
        mongodb_version="8.0",
        mongodb_port=37017,
        replicaset_name="rs0",
        status="deployed",
        created_by=admin_user.id,
    )
    db_session.add(cluster)
    await db_session.flush()

    host = ClusterHost(
        cluster_id=cluster.id,
        hostname="mongo-node-1",
        ip_address="10.0.0.1",
        role="primary",
        ssh_user="ubuntu",
        ssh_port=22,
        ssh_key_secret_id=secret.id,
    )
    db_session.add(host)
    await db_session.commit()

    return cluster, host


@pytest.mark.asyncio
async def test_restart_node_success(db_session, admin_user):
    cluster, host = await _setup_cluster_and_host(db_session, admin_user)

    mock_conn = AsyncMock()

    with patch("app.services.operations.restart_ops.ssh_service") as mock_ssh, \
         patch("app.services.operations.restart_ops.asyncio.sleep", new_callable=AsyncMock):
        mock_ssh.connect = AsyncMock(return_value=mock_conn)
        mock_ssh.run_command = AsyncMock(
            side_effect=[
                (0, "ok\n", ""),          # restart command
                (0, "active\n", ""),      # is-active check
            ]
        )
        mock_ssh.disconnect = AsyncMock()

        result = await restart_node(db_session, cluster, {"host_id": host.id})

    assert result["status"] == "success"
    assert result["host"] == "mongo-node-1"
    assert "active" in result["message"]
    mock_ssh.connect.assert_awaited_once()
    assert mock_ssh.run_command.await_count == 2
    mock_ssh.disconnect.assert_awaited_once()


@pytest.mark.asyncio
async def test_restart_node_failure(db_session, admin_user):
    cluster, host = await _setup_cluster_and_host(db_session, admin_user)

    mock_conn = AsyncMock()

    with patch("app.services.operations.restart_ops.ssh_service") as mock_ssh, \
         patch("app.services.operations.restart_ops.asyncio.sleep", new_callable=AsyncMock):
        mock_ssh.connect = AsyncMock(return_value=mock_conn)
        mock_ssh.run_command = AsyncMock(
            return_value=(1, "", "Failed to restart mongod.service")
        )
        mock_ssh.disconnect = AsyncMock()

        result = await restart_node(db_session, cluster, {"host_id": host.id})

    assert result["status"] == "error"
    assert result["host"] == "mongo-node-1"
    assert "exit 1" in result["message"]
    mock_ssh.disconnect.assert_awaited_once()


# ---------------------------------------------------------------------------
# Helpers for user-ops tests
# ---------------------------------------------------------------------------

async def _setup_cluster_with_admin_creds(db_session, admin_user):
    """Create a cluster with admin credentials secret and a primary host."""
    # Admin credentials secret (username:password format)
    admin_creds = b"admin:SuperSecret123"
    ct, nonce, tag = encrypt(admin_creds)
    admin_secret = Secret(
        name="admin-creds",
        type="mongo_credentials",
        ciphertext=ct,
        nonce=nonce,
        auth_tag=tag,
        created_by=admin_user.id,
    )
    db_session.add(admin_secret)
    await db_session.flush()

    # SSH key secret (needed for host FK)
    key_bytes = b"-----BEGIN OPENSSH PRIVATE KEY-----\nfake\n-----END OPENSSH PRIVATE KEY-----"
    ct2, nonce2, tag2 = encrypt(key_bytes)
    ssh_secret = Secret(
        name=f"ssh-key-{uuid.uuid4().hex[:8]}",
        type="ssh_key",
        ciphertext=ct2,
        nonce=nonce2,
        auth_tag=tag2,
        created_by=admin_user.id,
    )
    db_session.add(ssh_secret)
    await db_session.flush()

    cluster = Cluster(
        name=f"user-ops-cluster-{uuid.uuid4().hex[:8]}",
        topology="pss",
        mongodb_version="8.0",
        mongodb_port=37017,
        replicaset_name="rs0",
        status="deployed",
        admin_credentials_secret_id=admin_secret.id,
        created_by=admin_user.id,
    )
    db_session.add(cluster)
    await db_session.flush()

    host = ClusterHost(
        cluster_id=cluster.id,
        hostname="mongo-primary-1",
        ip_address="10.0.0.1",
        role="primary",
        ssh_user="ubuntu",
        ssh_port=22,
        ssh_key_secret_id=ssh_secret.id,
    )
    db_session.add(host)
    await db_session.commit()

    return cluster, admin_secret


@pytest.mark.asyncio
async def test_create_app_user(db_session, admin_user):
    cluster, _ = await _setup_cluster_with_admin_creds(db_session, admin_user)

    # App password secret
    app_pwd = b"appUserPass456"
    ct, nonce, tag = encrypt(app_pwd)
    app_secret = Secret(
        name=f"app-pwd-{uuid.uuid4().hex[:8]}",
        type="mongo_password",
        ciphertext=ct,
        nonce=nonce,
        auth_tag=tag,
        created_by=admin_user.id,
    )
    db_session.add(app_secret)
    await db_session.commit()

    with patch("app.services.operations.user_ops.MongoClient") as MockClient:
        mock_client = MagicMock()
        MockClient.return_value = mock_client

        result = await create_app_user(
            db_session,
            cluster,
            {
                "database": "myapp",
                "username": "app_reader",
                "password_secret_id": app_secret.id,
                "roles": [{"role": "readWrite", "db": "myapp"}],
            },
        )

    assert result["username"] == "app_reader"
    assert result["database"] == "myapp"
    mock_client["myapp"].command.assert_called_once()
    mock_client.close.assert_called_once()


@pytest.mark.asyncio
async def test_delete_app_user(db_session, admin_user):
    cluster, _ = await _setup_cluster_with_admin_creds(db_session, admin_user)

    with patch("app.services.operations.user_ops.MongoClient") as MockClient:
        mock_client = MagicMock()
        MockClient.return_value = mock_client

        result = await delete_app_user(
            db_session,
            cluster,
            {"database": "myapp", "username": "app_reader"},
        )

    assert result["username"] == "app_reader"
    assert result["database"] == "myapp"
    mock_client["myapp"].command.assert_called_once_with("dropUser", "app_reader")
    mock_client.close.assert_called_once()


# ---------------------------------------------------------------------------
# Backup-ops tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pbm_list(db_session, admin_user):
    cluster, host = await _setup_cluster_and_host(db_session, admin_user)

    mock_conn = AsyncMock()
    json_output = '{"snapshots": [{"name": "2024-01-01T00:00:00Z"}]}'

    with patch("app.services.operations.backup_ops.ssh_service") as mock_ssh:
        mock_ssh.connect = AsyncMock(return_value=mock_conn)
        mock_ssh.run_command = AsyncMock(return_value=(0, json_output, ""))
        mock_ssh.disconnect = AsyncMock()

        result = await pbm_list(db_session, cluster, {})

    assert result["status"] == "success"
    assert "backups" in result
    assert result["backups"]["snapshots"][0]["name"] == "2024-01-01T00:00:00Z"
    mock_ssh.disconnect.assert_awaited_once()


@pytest.mark.asyncio
async def test_pbm_backup_failure(db_session, admin_user):
    cluster, host = await _setup_cluster_and_host(db_session, admin_user)

    mock_conn = AsyncMock()

    with patch("app.services.operations.backup_ops.ssh_service") as mock_ssh:
        mock_ssh.connect = AsyncMock(return_value=mock_conn)
        mock_ssh.run_command = AsyncMock(
            return_value=(1, "pbm: command not found", "")
        )
        mock_ssh.disconnect = AsyncMock()

        result = await pbm_backup(db_session, cluster, {})

    assert result["status"] == "error"
    assert "pbm: command not found" in result["message"]
    mock_ssh.disconnect.assert_awaited_once()
