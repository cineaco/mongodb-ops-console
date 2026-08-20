import os
import shutil
import stat
import tempfile
import uuid

import pytest
import yaml
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import encrypt
from app.models.cluster import Cluster
from app.models.cluster_host import ClusterHost
from app.models.secret import Secret
from app.services.inventory_generator import generate_inventory


async def _setup_cluster_for_inventory(
    db_session: AsyncSession, admin_user,
) -> Cluster:
    """Create a PSS cluster with 3 hosts, SSH key secrets, and an admin password secret."""
    # Create SSH key secret
    ssh_key_plain = b"-----BEGIN RSA PRIVATE KEY-----\nMIItest\n-----END RSA PRIVATE KEY-----"
    ct, nonce, tag = encrypt(ssh_key_plain)
    ssh_secret = Secret(
        name="test-ssh-key",
        type="ssh_key",
        ciphertext=ct,
        nonce=nonce,
        auth_tag=tag,
        created_by=admin_user.id,
    )
    db_session.add(ssh_secret)
    await db_session.flush()

    # Create admin password secret
    admin_pw_plain = b"SuperSecret123"
    ct2, nonce2, tag2 = encrypt(admin_pw_plain)
    admin_secret = Secret(
        name="admin-creds",
        type="admin_password",
        ciphertext=ct2,
        nonce=nonce2,
        auth_tag=tag2,
        created_by=admin_user.id,
    )
    db_session.add(admin_secret)
    await db_session.flush()

    # Create cluster
    cluster = Cluster(
        name="inv-test-cluster",
        topology="pss",
        mongodb_version="8.0",
        mongodb_port=37017,
        replicaset_name="rs0",
        config={"enable_monitoring": True},
        status="pending",
        admin_credentials_secret_id=admin_secret.id,
        created_by=admin_user.id,
    )
    db_session.add(cluster)
    await db_session.flush()

    # Create 3 hosts
    for hostname, ip, role in [
        ("mongo-primary", "10.0.0.1", "primary"),
        ("mongo-secondary", "10.0.0.2", "secondary"),
        ("mongo-secondary2", "10.0.0.3", "secondary2"),
    ]:
        host = ClusterHost(
            cluster_id=cluster.id,
            hostname=hostname,
            ip_address=ip,
            role=role,
            ssh_user="ubuntu",
            ssh_port=22,
            ssh_key_secret_id=ssh_secret.id,
        )
        db_session.add(host)

    await db_session.flush()
    return cluster


@pytest.mark.asyncio
async def test_generate_inventory_creates_hosts_file(db_session, admin_user):
    cluster = await _setup_cluster_for_inventory(db_session, admin_user)
    tmp = tempfile.mkdtemp()
    try:
        job_id = uuid.uuid4()
        hosts_path = await generate_inventory(db_session, cluster, job_id, tmp)

        assert os.path.isfile(hosts_path)
        content = open(hosts_path).read()

        # Group headers
        assert "[primary]" in content
        assert "[secondary]" in content
        assert "[secondary2]" in content
        assert "[mongodb:children]" in content

        # Host lines contain ansible_host=
        assert "ansible_host=10.0.0.1" in content
        assert "ansible_host=10.0.0.2" in content
        assert "ansible_host=10.0.0.3" in content

        # Vars section
        assert "ansible_become=true" in content
    finally:
        shutil.rmtree(tmp)


@pytest.mark.asyncio
async def test_generate_inventory_creates_group_vars(db_session, admin_user):
    cluster = await _setup_cluster_for_inventory(db_session, admin_user)
    tmp = tempfile.mkdtemp()
    try:
        job_id = uuid.uuid4()
        await generate_inventory(db_session, cluster, job_id, tmp)

        all_yml_path = os.path.join(tmp, "group_vars", "all.yml")
        assert os.path.isfile(all_yml_path)

        with open(all_yml_path) as fh:
            data = yaml.safe_load(fh)

        assert data["mongodb_version"] == "8.0"
        assert data["mongodb_port"] == 37017
        assert data["replicaset_name"] == "rs0"
        assert data["admin_password"] == "SuperSecret123"
        # config values merged
        assert data["enable_monitoring"] is True
    finally:
        shutil.rmtree(tmp)


@pytest.mark.asyncio
async def test_generate_inventory_creates_ssh_keys(db_session, admin_user):
    cluster = await _setup_cluster_for_inventory(db_session, admin_user)
    tmp = tempfile.mkdtemp()
    try:
        job_id = uuid.uuid4()
        await generate_inventory(db_session, cluster, job_id, tmp)

        for hostname in ("mongo-primary", "mongo-secondary", "mongo-secondary2"):
            key_path = os.path.join(tmp, "keys", f"{hostname}.pem")
            assert os.path.isfile(key_path), f"Missing key file: {key_path}"
            mode = stat.S_IMODE(os.stat(key_path).st_mode)
            assert mode == 0o400, f"Expected mode 0o400, got {oct(mode)}"

            content = open(key_path).read()
            assert "BEGIN RSA PRIVATE KEY" in content
    finally:
        shutil.rmtree(tmp)


@pytest.mark.asyncio
async def test_generate_inventory_no_hosts_raises(db_session, admin_user):
    # Create a cluster with no hosts
    cluster = Cluster(
        name="empty-cluster",
        topology="pss",
        mongodb_version="7.0",
        mongodb_port=27017,
        replicaset_name="rs0",
        config={},
        status="pending",
        created_by=admin_user.id,
    )
    db_session.add(cluster)
    await db_session.flush()

    tmp = tempfile.mkdtemp()
    try:
        with pytest.raises(ValueError, match="No hosts found"):
            await generate_inventory(db_session, cluster, uuid.uuid4(), tmp)
    finally:
        shutil.rmtree(tmp)
